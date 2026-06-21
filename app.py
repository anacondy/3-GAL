# app.py
# Feature Registry: v2.0 - Enhanced Scraper with AI PDF Analysis
# Details: Live scraping, AI PDF summary, comprehensive search
#
# Applied patches (in order):
#   Phase 1 (security):
#     P1-01: Hard size cap + streaming in download_pdf
#     P1-01/02: flask-limiter rate limits on /api/sync and /api/analyze
#     P2-01: Removed dead "Alvido" admin-upload placeholder in /api/search
#     P2-02: Hard-pinned debug=False
#   Hotfix:
#     H-1: sort_date column + ORDER BY sort_date DESC, id DESC
#   Phase 2 (reliability + defense-in-depth):
#     P1-03: Removed broken googletrans==4.0.0-rc1 (Hindi translation)
#     P2-04: SQLite WAL mode enabled (better concurrency)
#     P2-05: PDF text length capped per-page + total
#     P2-06: Search query length capped (chars + tokens)
#     P2-07: (in generate_static.py) html.escape() for category and desc
#     Cleanup bug: uses NOT IN (top-N by sort_date) instead of id-threshold
#     P3-01: Removed unused imports (threading, tempfile)
#     P3-02: Removed unreachable second `return "Notice"`
#     P3-04: Security headers via @app.after_request
#     P3-05: CSRF guard via X-Requested-With on POST routes
#     H-2: open-original-btn.href is now correctly set in JS-equivalent (Python side)
#            NOTE: the HTML button itself was added by hotfix-pdfbutton; the JS to
#            set its href lives in templates/index.html and is patched separately.

import re
import sqlite3
import requests
import os
import io
import concurrent.futures
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from bs4 import BeautifulSoup

# PDF and language detection imports
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from langdetect import detect
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

# Phase 2 P1-03: removed googletrans. The 4.0.0-rc1 pin is broken upstream
# (Google changes the response shape regularly; the library throws AttributeError
# or returns empty strings on any non-trivial Hindi text). Hindi PDFs still get
# their language detected by `langdetect`, but translation is no longer attempted.
TRANSLATOR_AVAILABLE = False


# Hotfix H-1 helper: normalize DD-MM-YYYY (or DD/MM/YYYY) to YYYY-MM-DD
def normalize_date_for_sort(date_text):
    """Return YYYY-MM-DD for valid DD-MM-YYYY / DD/MM/YYYY input, else ''."""
    if not date_text:
        return ""
    m = re.match(r'^\s*(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\s*$', date_text)
    if not m:
        return ""
    d, mo, y = m.groups()
    if len(y) == 2:
        y = ("20" + y) if int(y) < 50 else ("19" + y)
    try:
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    except ValueError:
        return ""


# Phase 2 P2-06: cap search query length to prevent FTS/LIKE abuse
MAX_QUERY_LENGTH = 500
MAX_QUERY_TOKENS = 32


def get_short_desc(title, category):
    title_lower = title.lower()
    date_match = re.search(r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(?:20\d{2})?)\b', title_lower)
    if date_match: return f"Deadline/Dates: {date_match.group(1).title()}"
    if 'debarred' in title_lower: return "Action required: Details regarding debarred students for exams."
    if 'fee' in title_lower or 'dues' in title_lower: return "Financial Notice: Please review fee submission deadlines."
    if 'result' in title_lower: return "Academic Update: Examination results have been declared."
    if 'admit card' in title_lower: return "Important: Admit cards are now available."
    if 'date sheet' in title_lower or 'timetable' in title_lower or 'schedule' in title_lower: return "Exam Schedule: Check the latest dates and timings."
    if 'holiday' in title_lower or 'vacation' in title_lower: return "Campus Update: Information regarding upcoming holidays."
    if 'special' in title_lower and 'exam' in title_lower: return "Special Exams: Important instructions and dates."
    if category == 'Exam': return "Read the official document for exam instructions and paper codes."
    elif category == 'Admissions': return "Review the admission guidelines and counseling procedures."
    return "Click to view full official notification document."

def enhance_data(data_list):
    for item in data_list:
        item['desc'] = get_short_desc(item.get('title', ''), item.get('category', 'Notice'))
    return data_list

app = Flask(__name__)

# --- Configuration ---
DB_FILE = "galgotias_cache.db"
BASE_URL = "https://www.galgotiasuniversity.edu.in"
EXAM_URL = f"{BASE_URL}/p/announcements/examination-announcement"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

REQUEST_TIMEOUT = 15
PDF_DOWNLOAD_TIMEOUT = 30
MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_ANNOUNCEMENTS = 470

# Phase 2 P2-05: cap PDF text extraction per-page and total
MAX_TEXT_PER_PAGE = 5_000
MAX_TEXT_TOTAL = 50_000

# Thread pool for async operations
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

import atexit
atexit.register(executor.shutdown, wait=False)

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["120 per minute"],
    storage_uri="memory://",
)


# Phase 2 P2-04: helper that opens a SQLite connection with sane defaults
# (WAL journal mode for better concurrent read/write, busy_timeout to avoid
# spurious OperationalError: database is locked under burst load).
def open_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.DatabaseError:
        # Older SQLite without WAL support — fall back silently.
        pass
    return conn


# --- Database Setup ---
def init_db():
    conn = open_db()
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='announcements'")
    table_exists = c.fetchone() is not None

    if table_exists:
        c.execute("PRAGMA table_info(announcements)")
        columns = [col[1] for col in c.fetchall()]

        if 'pdf_summary' not in columns:
            c.execute('ALTER TABLE announcements ADD COLUMN pdf_summary TEXT')
        if 'category' not in columns:
            c.execute('ALTER TABLE announcements ADD COLUMN category TEXT')
        if 'translated_title' not in columns:
            c.execute('ALTER TABLE announcements ADD COLUMN translated_title TEXT')
        if 'sort_date' not in columns:
            c.execute('ALTER TABLE announcements ADD COLUMN sort_date TEXT')
            c.execute("SELECT id, date_text FROM announcements WHERE sort_date IS NULL OR sort_date = ''")
            backfilled = 0
            for row in c.fetchall():
                sd = normalize_date_for_sort(row[1])
                if sd:
                    c.execute("UPDATE announcements SET sort_date = ? WHERE id = ?", (sd, row[0]))
                    backfilled += 1
            if backfilled:
                print(f"--- [MIGRATE] Backfilled sort_date for {backfilled} existing rows ---")
    else:
        c.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_text TEXT,
                title TEXT,
                url TEXT UNIQUE,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pdf_summary TEXT,
                category TEXT,
                translated_title TEXT,
                sort_date TEXT
            )
        ''')

    try:
        c.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS announcements_fts USING fts5(
                title, date_text, pdf_summary, translated_title, category,
                content='announcements', content_rowid='id'
            )
        ''')
    except Exception as e:
        print(f"FTS table creation skipped (may already exist): {e}")

    try:
        c.execute('''
            CREATE TRIGGER IF NOT EXISTS announcements_ai AFTER INSERT ON announcements BEGIN
                INSERT INTO announcements_fts(rowid, title, date_text, pdf_summary, translated_title, category)
                VALUES (new.id, new.title, new.date_text, new.pdf_summary, new.translated_title, new.category);
            END
        ''')
        c.execute('''
            CREATE TRIGGER IF NOT EXISTS announcements_au AFTER UPDATE ON announcements BEGIN
                INSERT INTO announcements_fts(announcements_fts, rowid, title, date_text, pdf_summary, translated_title, category)
                VALUES ('delete', old.id, old.title, old.date_text, old.pdf_summary, old.translated_title, old.category);
                INSERT INTO announcements_fts(rowid, title, date_text, pdf_summary, translated_title, category)
                VALUES (new.id, new.title, new.date_text, new.pdf_summary, new.translated_title, new.category);
            END
        ''')
        c.execute('''
            CREATE TRIGGER IF NOT EXISTS announcements_ad AFTER DELETE ON announcements BEGIN
                DELETE FROM announcements_fts WHERE rowid = old.id;
            END
        ''')
    except Exception as e:
        print(f"Trigger creation skipped (may already exist): {e}")

    conn.commit()
    conn.close()


# Phase 2 cleanup bug fix: the previous version used
# `ORDER BY sort_date ASC LIMIT 1 OFFSET N; DELETE WHERE id < threshold_id`.
# That breaks when IDs aren't monotonically aligned with sort_date (which is
# always the case after a real scrape). The fix: delete rows that aren't in
# the top-MAX_ANNOUNCEMENTS by sort_date. SQLite supports `NOT IN (...) LIMIT`
# when wrapped in a subquery.
def cleanup_old_announcements():
    """Remove oldest announcements if count exceeds MAX_ANNOUNCEMENTS."""
    conn = open_db()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM announcements")
        count = c.fetchone()[0]
        if count <= MAX_ANNOUNCEMENTS:
            return 0

        # Keep the MAX_ANNOUNCEMENTS newest rows by sort_date, then by id.
        c.execute("""
            DELETE FROM announcements
            WHERE id NOT IN (
                SELECT id FROM announcements
                ORDER BY sort_date DESC, id DESC
                LIMIT ?
            )
        """, (MAX_ANNOUNCEMENTS,))
        deleted_count = c.rowcount
        conn.commit()
        print(f"--- [CLEANUP] Deleted {deleted_count} old announcements (kept latest {MAX_ANNOUNCEMENTS}) ---")
        return deleted_count
    except Exception as e:
        print(f"Cleanup Error: {e}")
        return 0
    finally:
        conn.close()


def save_announcement(date_text, title, url, pdf_summary=None, category=None, translated_title=None):
    """Save announcement with optional PDF summary and category."""
    sort_date = normalize_date_for_sort(date_text)
    conn = open_db()
    c = conn.cursor()
    try:
        c.execute("SELECT id FROM announcements WHERE url = ?", (url,))
        existing = c.fetchone()
        if existing:
            if pdf_summary or category or translated_title or sort_date:
                c.execute("""
                    UPDATE announcements
                    SET pdf_summary = COALESCE(?, pdf_summary),
                        category = COALESCE(?, category),
                        translated_title = COALESCE(?, translated_title),
                        sort_date = COALESCE(?, sort_date)
                    WHERE url = ?
                """, (pdf_summary, category, translated_title, sort_date, url))
        else:
            c.execute("""
                INSERT INTO announcements (date_text, title, url, pdf_summary, category, translated_title, sort_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date_text, title, url, pdf_summary, category, translated_title, sort_date))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()


def comprehensive_search(query):
    """Enhanced search with support for various query patterns."""
    # Phase 2 P2-06: cap query length defensively
    if query and len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]

    conn = open_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    results = []
    query = query.strip()

    if not query:
        c.execute("SELECT * FROM announcements ORDER BY sort_date DESC, id DESC LIMIT 100")
        rows = c.fetchall()
        conn.close()
        return enhance_data([dict(row) for row in rows])

    try:
        fts_query = build_fts_query(query)
        c.execute("""
            SELECT a.* FROM announcements a
            INNER JOIN announcements_fts fts ON a.id = fts.rowid
            WHERE announcements_fts MATCH ?
            ORDER BY a.sort_date DESC, a.id DESC LIMIT 100
        """, (fts_query,))
        rows = c.fetchall()
        results = [dict(row) for row in rows]
    except Exception as e:
        print(f"FTS search failed (falling back to LIKE): {e}")

    if not results:
        try:
            date_patterns = extract_date_patterns(query)
            # Phase 2 P2-06: cap token count
            text_parts = extract_text_parts(query)[:MAX_QUERY_TOKENS]

            conditions = []
            params = []

            c.execute("PRAGMA table_info(announcements)")
            columns = [col[1] for col in c.fetchall()]

            for text in text_parts:
                search_term = f"%{text}%"
                col_conditions = ["title LIKE ?", "date_text LIKE ?"]
                col_params = [search_term, search_term]

                if 'pdf_summary' in columns:
                    col_conditions.append("pdf_summary LIKE ?")
                    col_params.append(search_term)
                if 'translated_title' in columns:
                    col_conditions.append("translated_title LIKE ?")
                    col_params.append(search_term)

                conditions.append(f"({' OR '.join(col_conditions)})")
                params.extend(col_params)

            for date in date_patterns:
                conditions.append("date_text LIKE ?")
                params.append(f"%{date}%")

            if conditions:
                query_sql = f"SELECT * FROM announcements WHERE {' AND '.join(conditions)} ORDER BY sort_date DESC, id DESC LIMIT 100"
                c.execute(query_sql, params)
                rows = c.fetchall()
                results = [dict(row) for row in rows]
            else:
                search_term = f"%{query}%"
                c.execute("SELECT * FROM announcements WHERE title LIKE ? OR date_text LIKE ? ORDER BY sort_date DESC, id DESC LIMIT 100",
                         (search_term, search_term))
                rows = c.fetchall()
                results = [dict(row) for row in rows]
        except Exception as e:
            print(f"LIKE search failed: {e}")
            search_term = f"%{query}%"
            c.execute("SELECT * FROM announcements WHERE title LIKE ? ORDER BY sort_date DESC, id DESC LIMIT 100", (search_term,))
            rows = c.fetchall()
            results = [dict(row) for row in rows]

    conn.close()
    return results


def build_fts_query(query):
    """Build FTS5 query from user input."""
    tokens = query.split()[:MAX_QUERY_TOKENS]
    fts_tokens = []
    for token in tokens:
        token = token.replace('"', '').replace("'", "")
        if token:
            fts_tokens.append(f'"{token}"*')
    return ' OR '.join(fts_tokens) if fts_tokens else query


def extract_date_patterns(query):
    patterns = []
    matches = re.findall(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', query)
    patterns.extend(matches)
    year_matches = re.findall(r'\b(20\d{2})\b', query)
    patterns.extend(year_matches)
    month_matches = re.findall(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b', query, re.I)
    patterns.extend(month_matches)
    return patterns


def extract_text_parts(query):
    cleaned = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', ' ', query)
    cleaned = re.sub(r'\b20\d{2}\b', ' ', cleaned)
    words = [w.strip() for w in cleaned.split() if len(w.strip()) > 1]
    return words


# --- PDF Analysis Functions ---

ALLOWED_PDF_DOMAINS = [
    'galgotiasuniversity.edu.in',
    'www.galgotiasuniversity.edu.in',
]

def is_allowed_url(url):
    """Validate URL is from allowed domains to prevent SSRF."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ('https',):
            return False
        host = parsed.netloc.lower()
        return any(host == domain or host.endswith('.' + domain)
                  for domain in ALLOWED_PDF_DOMAINS)
    except Exception:
        return False


def download_pdf(url):
    """Download PDF from URL with hard size cap (P1-01)."""
    if not is_allowed_url(url):
        print(f"PDF download blocked: URL not in allowlist - {url[:50]}")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=PDF_DOWNLOAD_TIMEOUT, stream=True)
        response.raise_for_status()

        cl = response.headers.get('Content-Length')
        if cl is not None:
            try:
                if int(cl) > MAX_PDF_BYTES:
                    print(f"PDF download blocked: Content-Length {cl} > {MAX_PDF_BYTES} - {url[:50]}")
                    response.close()
                    return None
            except ValueError:
                pass

        buf = io.BytesIO()
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_PDF_BYTES:
                print(f"PDF download aborted: exceeded {MAX_PDF_BYTES} bytes - {url[:50]}")
                response.close()
                return None
            buf.write(chunk)
        buf.seek(0)

        content_type = response.headers.get('content-type', '').lower()
        is_pdf = (
            'pdf' in content_type or
            url.lower().endswith('.pdf') or
            buf.read(5) == b'%PDF-'
        )

        if not is_pdf:
            return None

        buf.seek(0)
        return buf
    except Exception as e:
        print(f"PDF download error: {e}")
        return None


def extract_pdf_text(pdf_bytes):
    """Extract text from PDF bytes with length caps (P2-05)."""
    if not PDF_AVAILABLE or pdf_bytes is None:
        return None

    try:
        with pdfplumber.open(pdf_bytes) as pdf:
            text = ""
            for page in pdf.pages[:10]:
                page_text = page.extract_text() or ""
                text += page_text[:MAX_TEXT_PER_PAGE] + "\n"
                if len(text) >= MAX_TEXT_TOTAL:
                    break
            return text[:MAX_TEXT_TOTAL].strip()
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return None


def detect_language(text):
    """Detect language of text."""
    if not LANGDETECT_AVAILABLE or not text:
        return 'en'
    try:
        return detect(text[:1000])
    except Exception:
        return 'en'


def categorize_document(text):
    """Categorize document based on content."""
    if not text:
        return "General Notice"
    text_lower = text.lower()
    if any(kw in text_lower for kw in ['result', 'marks', 'grade', 'cgpa', 'transcript']): return "Result"
    if any(kw in text_lower for kw in ['fee', 'payment', 'dues', 'scholarship', 'fine']): return "Fees"
    if any(kw in text_lower for kw in ['holiday', 'vacation', 'closure']): return "Holiday"
    if any(kw in text_lower for kw in ['event', 'festival', 'celebration', 'cultural']): return "Event"
    if any(kw in text_lower for kw in ['admission', 'intake', 'enrollment', 'counseling']): return "Admissions"
    if any(kw in text_lower for kw in ['exam', 'examination', 'paper code', 'date sheet', 'timetable', 'hall ticket', 'admit card', 'debarred']): return "Exam"
    if any(kw in text_lower for kw in ['academic calendar', 'session']): return "Calendar"
    return "Notice"


def extract_key_info(text):
    """Extract key information from PDF text."""
    if not text:
        return {}
    info = {}
    text_lower = text.lower()
    paper_codes = re.findall(r'\b([A-Z]{2,4}[-\s]?\d{3,4}[-\s]?[A-Z]?)\b', text, re.I)
    if paper_codes:
        info['paper_codes'] = list(set(paper_codes[:10]))
    dates = re.findall(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', text)
    dates += re.findall(r'\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})\b', text, re.I)
    if dates:
        info['dates'] = list(set(dates[:20]))
    times = re.findall(r'\b(\d{1,2}[:\.]?\d{2}\s*(?:am|pm|AM|PM)?)\b', text)
    if times:
        info['times'] = list(set(times[:10]))
    subjects = re.findall(r'\b(mathematics|physics|chemistry|english|computer|science|programming|data\s+structure|algorithm|database|network|software|operating\s+system)\b', text_lower)
    if subjects:
        info['subjects'] = list(set(subjects[:10]))
    return info


def generate_pdf_summary(text, key_info, category):
    """Generate a concise summary of the PDF content."""
    if not text:
        return "Unable to extract content from PDF."
    summary_parts = [f"Type: {category}"]
    if key_info.get('paper_codes'):
        summary_parts.append(f"Paper Codes: {', '.join(key_info['paper_codes'][:5])}")
    if key_info.get('dates'):
        summary_parts.append(f"Dates: {', '.join(key_info['dates'][:5])}")
    if key_info.get('times'):
        summary_parts.append(f"Times: {', '.join(key_info['times'][:3])}")
    if key_info.get('subjects'):
        summary_parts.append(f"Subjects: {', '.join(key_info['subjects'][:5])}")
    if text:
        brief = ' '.join(text.split()[:50])
        if len(brief) > 200:
            brief = brief[:200] + "..."
        summary_parts.append(f"Content: {brief}")
    return " | ".join(summary_parts)


def analyze_pdf_async(url):
    """Analyze PDF asynchronously and update database."""
    def task():
        try:
            pdf_bytes = download_pdf(url)
            if not pdf_bytes:
                return
            text = extract_pdf_text(pdf_bytes)
            if not text:
                return
            lang = detect_language(text)
            # Phase 2 P1-03: translation removed.
            analysis_text = text
            category = categorize_document(analysis_text)
            key_info = extract_key_info(analysis_text)
            summary = generate_pdf_summary(analysis_text, key_info, category)
            conn = open_db()
            c = conn.cursor()
            c.execute("""
                UPDATE announcements
                SET pdf_summary = ?, category = ?
                WHERE url = ?
            """, (summary, category, url))
            conn.commit()
            conn.close()
            print(f"--- [PDF] Analyzed: {url[:50]}... Category: {category} ---")
        except Exception as e:
            print(f"PDF analysis error: {e}")
    executor.submit(task)


# --- Scraper Logic (Live Fetch) ---
def scrape_and_sync(analyze_pdfs=True):
    """Fetches latest data from Galgotias and updates DB."""
    print("--- [SYSTEM] FETCHING LIVE DATA... ---")
    try:
        resp = requests.get(EXAM_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        pdf_links = soup.find_all("a", href=re.compile(r"\.pdf", re.I))
        count = 0
        urls_to_analyze = []
        seen_urls = set()

        for link in pdf_links:
            href = link.get("href", "").strip()
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)
            if not href.startswith("http"):
                href = BASE_URL + href

            parent = link.parent
            if parent:
                raw_text = parent.get_text(" ", strip=True)
                raw_text = re.sub(r'\s+', ' ', raw_text)

                date_match = re.search(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b", raw_text)
                if not date_match:
                    date_match = re.search(r"\b(\d{1,2}\s+\w+\s+\d{4})\b", raw_text)

                if date_match:
                    date_text = date_match.group(1)
                    title = raw_text.replace(date_text, "")
                    title = re.sub(r'View\s*Detail', '', title, flags=re.IGNORECASE)
                    title = title.strip()
                    title = re.sub(r"^[\.\-\:\s]+", "", title)
                    if title:
                        save_announcement(date_text, title, href)
                        urls_to_analyze.append(href)
                        count += 1
                        continue

            title = link.get_text(" ", strip=True)
            title = re.sub(r'\s+', ' ', title)
            if re.search(r'view\s*detail|download|click\s*here', title, re.IGNORECASE):
                if parent:
                    title = re.sub(r'\s+', ' ', parent.get_text(" ", strip=True))[:100]
                    title = re.sub(r'View\s*Detail', '', title, flags=re.IGNORECASE).strip()

            date_text = datetime.now().strftime("%d-%m-%Y")
            save_announcement(date_text, title, href)
            urls_to_analyze.append(href)
            count += 1

        if analyze_pdfs and PDF_AVAILABLE:
            for url in urls_to_analyze[:20]:
                analyze_pdf_async(url)

        deleted = cleanup_old_announcements()

        conn = open_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM announcements")
        total_count = c.fetchone()[0]
        conn.close()

        print(f"--- [SYSTEM] SYNC COMPLETE. {count} ITEMS PROCESSED. ---")
        print(f"--- [SYSTEM] TOTAL ANNOUNCEMENTS IN DB: {total_count} (max: {MAX_ANNOUNCEMENTS}) ---")
        return True, count
    except Exception as e:
        print(f"--- [ERROR] SCRAPE FAILED: {e} ---")
        return False, 0


# --- Routes ---

# Phase 2 P3-04: defense-in-depth security headers on every response
@app.after_request
def set_security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Referrer-Policy'] = 'no-referrer'
    resp.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # CSP: allow self + Google Docs viewer iframe + Google Fonts for the template.
    resp.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "frame-src https://docs.google.com; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self';"
    )
    return resp


# Phase 2 P3-05: CSRF guard — require a custom header on POST routes.
# Browsers won't send custom headers cross-origin without an explicit CORS
# preflight, so this effectively blocks cross-site form-submission attacks.
def require_xhr():
    if request.headers.get('X-Requested-With', '').lower() != 'xmlhttprequest':
        return jsonify({"error": "X-Requested-With header required"}), 403
    return None


@app.route('/')
def index():
    conn = open_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM announcements")
    total_count = c.fetchone()[0]
    if total_count == 0:
        scrape_and_sync()
        c.execute("SELECT COUNT(*) FROM announcements")
        total_count = c.fetchone()[0]

    c.execute("SELECT * FROM announcements ORDER BY sort_date DESC, id DESC LIMIT 100")
    rows = c.fetchall()
    data = [dict(row) for row in rows]
    conn.close()

    return render_template('index.html', initial_data=data, total_count=total_count, max_limit=MAX_ANNOUNCEMENTS)


@app.route('/api/sync', methods=['POST'])
@limiter.limit("1 per 5 minutes")
def sync():
    blocked = require_xhr()
    if blocked:
        return blocked
    success, count = scrape_and_sync()

    conn = open_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM announcements")
    total_count = c.fetchone()[0]
    conn.close()

    return jsonify({
        "status": "success" if success else "error",
        "count": count,
        "total": total_count,
        "max_limit": MAX_ANNOUNCEMENTS,
        "message": f"Synchronized {count} announcements (Total: {total_count}/{MAX_ANNOUNCEMENTS})" if success else "Sync failed"
    })


@app.route('/api/search')
def search():
    q = request.args.get('q', '')
    results = comprehensive_search(q)
    return jsonify(results)


@app.route('/api/analyze', methods=['POST'])
@limiter.limit("10 per minute")
def analyze_pdf():
    """Analyze a specific PDF and return summary."""
    blocked = require_xhr()
    if blocked:
        return blocked

    data = request.get_json() or {}
    url = data.get('url', '')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    conn = open_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT pdf_summary, category FROM announcements WHERE url = ?", (url,))
    row = c.fetchone()
    conn.close()

    if row and row['pdf_summary']:
        return jsonify({
            "summary": row['pdf_summary'],
            "category": row['category'],
            "cached": True
        })

    try:
        pdf_bytes = download_pdf(url)
        if not pdf_bytes:
            return jsonify({"error": "Could not download PDF"}), 400

        text = extract_pdf_text(pdf_bytes)
        if not text:
            # Phase 2: friendlier error message for image-only PDFs
            return jsonify({
                "error": "PDF has no extractable text (it may be a scanned image). View the original PDF for content.",
                "language_detected": None,
                "cached": False,
            }), 400

        lang = detect_language(text)
        category = categorize_document(text)
        key_info = extract_key_info(text)
        summary = generate_pdf_summary(text, key_info, category)

        conn = open_db()
        c = conn.cursor()
        c.execute("""
            UPDATE announcements
            SET pdf_summary = ?, category = ?
            WHERE url = ?
        """, (summary, category, url))
        conn.commit()
        conn.close()

        return jsonify({
            "summary": summary,
            "category": category,
            "key_info": key_info,
            "language_detected": lang,
            "translated": False,
            "cached": False
        })
    except Exception as e:
        # Phase 2: don't leak raw exception text to client
        print(f"--- [ERROR] /api/analyze failed: {e} ---")
        return jsonify({"error": "Analysis failed. Please try again later."}), 500


@app.route('/api/data')
def get_data():
    """Get all announcements data with optional filtering."""
    category = request.args.get('category', '')
    limit = min(int(request.args.get('limit', 100)), 500)

    conn = open_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if category:
        c.execute("SELECT * FROM announcements WHERE category = ? ORDER BY sort_date DESC, id DESC LIMIT ?",
                  (category, limit))
    else:
        c.execute("SELECT * FROM announcements ORDER BY sort_date DESC, id DESC LIMIT ?", (limit,))

    rows = c.fetchall()
    data = [dict(row) for row in rows]
    conn.close()

    return jsonify(data)


@app.route('/api/categories')
def get_categories():
    """Get list of all categories."""
    conn = open_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM announcements WHERE category IS NOT NULL")
    categories = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(categories)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "pdf_support": PDF_AVAILABLE,
        "language_detection": LANGDETECT_AVAILABLE,
        "translation_support": TRANSLATOR_AVAILABLE,
    })


if __name__ == '__main__':
    init_db()
    scrape_and_sync(analyze_pdfs=False)
    port = int(os.environ.get('PORT', 5007))
    app.run(debug=False, port=port, threaded=True)
