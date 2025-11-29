# app.py
# Feature Registry: v2.0 - Enhanced Scraper with AI PDF Analysis & Translation
# Details: Live scraping, AI PDF summary, Hindi translation, comprehensive search

import re
import sqlite3
import requests
import os
import io
import tempfile
import threading
import concurrent.futures
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup

# PDF and translation imports
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

try:
    from googletrans import Translator
    translator = Translator()
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False

app = Flask(__name__)

# --- Configuration ---
DB_FILE = "galgotias_cache.db"
BASE_URL = "https://www.galgotiasuniversity.edu.in"
EXAM_URL = f"{BASE_URL}/p/announcements/examination-announcement"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Request timeout settings
REQUEST_TIMEOUT = 15
PDF_DOWNLOAD_TIMEOUT = 30

# Thread pool for async operations
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_text TEXT,
            title TEXT,
            url TEXT UNIQUE,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pdf_summary TEXT,
            category TEXT,
            translated_title TEXT
        )
    ''')
    # Create FTS (Full-Text Search) table for comprehensive search
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS announcements_fts USING fts5(
            title, date_text, pdf_summary, translated_title, category,
            content='announcements', content_rowid='id'
        )
    ''')
    # Create triggers to keep FTS in sync
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
    conn.commit()
    conn.close()


def save_announcement(date_text, title, url, pdf_summary=None, category=None, translated_title=None):
    """Save announcement with optional PDF summary and category."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        # Check if record exists
        c.execute("SELECT id FROM announcements WHERE url = ?", (url,))
        existing = c.fetchone()
        
        if existing:
            # Update existing record with new summary data
            if pdf_summary or category or translated_title:
                c.execute("""
                    UPDATE announcements 
                    SET pdf_summary = COALESCE(?, pdf_summary),
                        category = COALESCE(?, category),
                        translated_title = COALESCE(?, translated_title)
                    WHERE url = ?
                """, (pdf_summary, category, translated_title, url))
        else:
            # Insert new record
            c.execute("""
                INSERT INTO announcements (date_text, title, url, pdf_summary, category, translated_title)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (date_text, title, url, pdf_summary, category, translated_title))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()


def comprehensive_search(query):
    """Enhanced search with support for various query patterns."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    results = []
    
    # Normalize query
    query = query.strip()
    
    if not query:
        # Return all records if no query
        c.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT 100")
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # Strategy 1: Try FTS5 search for complex queries
    try:
        # Build FTS query - handle various patterns
        fts_query = build_fts_query(query)
        c.execute("""
            SELECT a.* FROM announcements a
            INNER JOIN announcements_fts fts ON a.id = fts.rowid
            WHERE announcements_fts MATCH ?
            ORDER BY a.id DESC LIMIT 100
        """, (fts_query,))
        rows = c.fetchall()
        results = [dict(row) for row in rows]
    except Exception as e:
        print(f"FTS search failed: {e}")
    
    # Strategy 2: Fall back to LIKE-based search
    if not results:
        # Parse query for date patterns
        date_patterns = extract_date_patterns(query)
        text_parts = extract_text_parts(query)
        
        # Build flexible LIKE query
        conditions = []
        params = []
        
        for text in text_parts:
            search_term = f"%{text}%"
            conditions.append("(title LIKE ? OR date_text LIKE ? OR pdf_summary LIKE ? OR translated_title LIKE ?)")
            params.extend([search_term, search_term, search_term, search_term])
        
        for date in date_patterns:
            conditions.append("date_text LIKE ?")
            params.append(f"%{date}%")
        
        if conditions:
            query_sql = f"SELECT * FROM announcements WHERE {' AND '.join(conditions)} ORDER BY id DESC LIMIT 100"
            c.execute(query_sql, params)
            rows = c.fetchall()
            results = [dict(row) for row in rows]
    
    conn.close()
    return results


def build_fts_query(query):
    """Build FTS5 query from user input."""
    # Handle special patterns
    tokens = query.split()
    fts_tokens = []
    
    for token in tokens:
        # Escape FTS special characters
        token = token.replace('"', '').replace("'", "")
        if token:
            fts_tokens.append(f'"{token}"*')
    
    return ' OR '.join(fts_tokens) if fts_tokens else query


def extract_date_patterns(query):
    """Extract date patterns from query (various formats)."""
    patterns = []
    
    # DD-MM-YYYY or DD/MM/YYYY
    matches = re.findall(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', query)
    patterns.extend(matches)
    
    # Year only (e.g., 2024)
    year_matches = re.findall(r'\b(20\d{2})\b', query)
    patterns.extend(year_matches)
    
    # Month patterns (Jan, Feb, etc.)
    month_matches = re.findall(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b', query, re.I)
    patterns.extend(month_matches)
    
    return patterns


def extract_text_parts(query):
    """Extract text parts from query, removing dates."""
    # Remove date patterns
    cleaned = re.sub(r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b', ' ', query)
    cleaned = re.sub(r'\b20\d{2}\b', ' ', cleaned)
    
    # Split into words
    words = [w.strip() for w in cleaned.split() if len(w.strip()) > 1]
    return words


# --- PDF Analysis Functions ---
def download_pdf(url):
    """Download PDF from URL and return as bytes."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=PDF_DOWNLOAD_TIMEOUT, stream=True)
        response.raise_for_status()
        
        # Check if it's a PDF
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and not url.lower().endswith('.pdf'):
            return None
        
        return io.BytesIO(response.content)
    except Exception as e:
        print(f"PDF download error: {e}")
        return None


def extract_pdf_text(pdf_bytes):
    """Extract text from PDF bytes."""
    if not PDF_AVAILABLE or pdf_bytes is None:
        return None
    
    try:
        with pdfplumber.open(pdf_bytes) as pdf:
            text = ""
            for page in pdf.pages[:10]:  # Limit to first 10 pages for performance
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return None


def detect_language(text):
    """Detect language of text."""
    if not LANGDETECT_AVAILABLE or not text:
        return 'en'
    
    try:
        return detect(text[:1000])  # Use first 1000 chars for detection
    except Exception:
        return 'en'


def translate_text(text, target='en'):
    """Translate text to target language."""
    if not TRANSLATOR_AVAILABLE or not text:
        return text
    
    try:
        # Split into chunks if too long (Google Translate limit)
        max_chars = 4500
        if len(text) <= max_chars:
            result = translator.translate(text, dest=target)
            return result.text
        
        # Translate in chunks
        chunks = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
        translated_chunks = []
        for chunk in chunks[:5]:  # Limit chunks for performance
            result = translator.translate(chunk, dest=target)
            translated_chunks.append(result.text)
        return ' '.join(translated_chunks)
    except Exception as e:
        print(f"Translation error: {e}")
        return text


def categorize_document(text):
    """Categorize document based on content."""
    if not text:
        return "General Notice"
    
    text_lower = text.lower()
    
    # Category patterns
    categories = {
        "Examination": ['exam', 'examination', 'paper code', 'paper-code', 'answer sheet', 'question paper', 
                       'time table', 'timetable', 'date sheet', 'datesheet', 'hall ticket', 'admit card',
                       'semester', 'internal', 'external', 'mid-term', 'end-term', 'practical', 'viva'],
        "Academic Calendar": ['academic calendar', 'holiday', 'vacation', 'session', 'semester start',
                             'semester end', 'registration', 'enrollment'],
        "Result": ['result', 'marks', 'grade', 'cgpa', 'sgpa', 'transcript', 'marksheet'],
        "Fee Notice": ['fee', 'payment', 'dues', 'scholarship', 'financial', 'refund'],
        "Admission": ['admission', 'intake', 'enrollment', 'counseling', 'merit list'],
        "Uniform/Dress Code": ['uniform', 'dress code', 'dress-code', 'attire', 'id card'],
        "Event": ['event', 'festival', 'function', 'celebration', 'cultural', 'sports'],
        "Assignment/Project": ['assignment', 'project', 'submission', 'deadline', 'thesis', 'dissertation'],
        "Internship/Placement": ['internship', 'placement', 'job', 'recruitment', 'campus drive', 'interview'],
        "Important Dates": ['important date', 'last date', 'deadline', 'schedule', 'timing']
    }
    
    for category, keywords in categories.items():
        if any(kw in text_lower for kw in keywords):
            return category
    
    return "General Notice"


def extract_key_info(text):
    """Extract key information from PDF text."""
    if not text:
        return {}
    
    info = {}
    text_lower = text.lower()
    
    # Extract paper codes (various formats)
    paper_codes = re.findall(r'\b([A-Z]{2,4}[-\s]?\d{3,4}[-\s]?[A-Z]?)\b', text, re.I)
    if paper_codes:
        info['paper_codes'] = list(set(paper_codes[:10]))
    
    # Extract dates
    dates = re.findall(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', text)
    dates += re.findall(r'\b(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})\b', text, re.I)
    if dates:
        info['dates'] = list(set(dates[:20]))
    
    # Extract times
    times = re.findall(r'\b(\d{1,2}[:\.]?\d{2}\s*(?:am|pm|AM|PM)?)\b', text)
    if times:
        info['times'] = list(set(times[:10]))
    
    # Extract subject names (common patterns)
    subjects = re.findall(r'\b(mathematics|physics|chemistry|english|computer|science|programming|data\s+structure|algorithm|database|network|software|operating\s+system)\b', text_lower)
    if subjects:
        info['subjects'] = list(set(subjects[:10]))
    
    return info


def generate_pdf_summary(text, key_info, category):
    """Generate a concise summary of the PDF content."""
    if not text:
        return "Unable to extract content from PDF."
    
    summary_parts = []
    
    # Add category
    summary_parts.append(f"Type: {category}")
    
    # Add key info
    if key_info.get('paper_codes'):
        summary_parts.append(f"Paper Codes: {', '.join(key_info['paper_codes'][:5])}")
    
    if key_info.get('dates'):
        summary_parts.append(f"Dates: {', '.join(key_info['dates'][:5])}")
    
    if key_info.get('times'):
        summary_parts.append(f"Times: {', '.join(key_info['times'][:3])}")
    
    if key_info.get('subjects'):
        summary_parts.append(f"Subjects: {', '.join(key_info['subjects'][:5])}")
    
    # Add brief content summary (first 200 chars)
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
            
            # Detect language and translate if Hindi
            lang = detect_language(text)
            translated_text = None
            if lang == 'hi':
                translated_text = translate_text(text, 'en')
            
            # Categorize and extract info
            analysis_text = translated_text or text
            category = categorize_document(analysis_text)
            key_info = extract_key_info(analysis_text)
            summary = generate_pdf_summary(analysis_text, key_info, category)
            
            # Update database
            conn = sqlite3.connect(DB_FILE)
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

        # Strategy 1: Find 'View Detail' links and parse parent text
        links = soup.find_all("a", string=re.compile(r"View Detail", re.I))
        
        # Strategy 2: Also look for direct PDF links
        pdf_links = soup.find_all("a", href=re.compile(r"\.pdf", re.I))

        count = 0
        urls_to_analyze = []
        
        for link in links:
            href = link.get("href", "").strip()
            if not href:
                continue
            if not href.startswith("http"):
                href = BASE_URL + href

            # Parent container text holds the Date and Title
            container = link.parent
            if not container:
                continue
            raw_text = container.get_text(" ", strip=True)

            # Extract Date (DD-MM-YYYY or other formats)
            date_match = re.search(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b", raw_text)
            
            if not date_match:
                # Try alternate date format
                date_match = re.search(r"\b(\d{1,2}\s+\w+\s+\d{4})\b", raw_text)

            if date_match:
                date_text = date_match.group(1)
                # Remove Date and 'View Detail' to get Title
                title = raw_text.replace(date_text, "").replace("View Detail", "").strip()
                title = re.sub(r"^[\.\-\:\s]+", "", title)  # Clean leading punctuation

                save_announcement(date_text, title, href)
                urls_to_analyze.append(href)
                count += 1

        # Also process direct PDF links
        for link in pdf_links:
            href = link.get("href", "").strip()
            if not href:
                continue
            if not href.startswith("http"):
                href = BASE_URL + href
            
            # Get title from link text or parent
            title = link.get_text(strip=True) or "PDF Document"
            if title in ["View Detail", "Download", "Click Here"]:
                parent = link.parent
                if parent:
                    title = parent.get_text(" ", strip=True)[:100]
            
            # Use current date if not found
            date_text = datetime.now().strftime("%d-%m-%Y")
            
            save_announcement(date_text, title, href)
            urls_to_analyze.append(href)
            count += 1

        # Trigger async PDF analysis for new URLs
        if analyze_pdfs and PDF_AVAILABLE:
            for url in urls_to_analyze[:20]:  # Limit to 20 for performance
                analyze_pdf_async(url)

        print(f"--- [SYSTEM] SYNC COMPLETE. {count} ITEMS PROCESSED. ---")
        return True, count
    except Exception as e:
        print(f"--- [ERROR] SCRAPE FAILED: {e} ---")
        return False, 0


# --- Routes ---

@app.route('/')
def index():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Check if DB is empty, if so, scrape immediately
    c.execute("SELECT COUNT(*) FROM announcements")
    if c.fetchone()[0] == 0:
        scrape_and_sync()

    # Get latest 100 items with all fields
    c.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT 100")
    rows = c.fetchall()
    data = [dict(row) for row in rows]
    conn.close()

    return render_template('index.html', initial_data=data)


@app.route('/api/sync', methods=['POST'])
def sync():
    success, count = scrape_and_sync()
    return jsonify({
        "status": "success" if success else "error",
        "count": count,
        "message": f"Synchronized {count} announcements" if success else "Sync failed"
    })


@app.route('/api/search')
def search():
    q = request.args.get('q', '')

    # --- ADMIN UPLOAD CHECK ---
    # As per user requirement [2025-10-12]:
    # If user types "upload", checking for credentials "Alvido".
    # (Client-side will handle the prompt, this is just a placeholder log)
    if q.lower() == "upload":
        print("[AUTH] Admin upload requested. Waiting for 'Alvido' credential.")

    # Use comprehensive search
    results = comprehensive_search(q)
    return jsonify(results)


@app.route('/api/analyze', methods=['POST'])
def analyze_pdf():
    """Analyze a specific PDF and return summary."""
    data = request.get_json() or {}
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    # Check if we already have analysis
    conn = sqlite3.connect(DB_FILE)
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
    
    # Perform new analysis
    try:
        pdf_bytes = download_pdf(url)
        if not pdf_bytes:
            return jsonify({"error": "Could not download PDF"}), 400
        
        text = extract_pdf_text(pdf_bytes)
        if not text:
            return jsonify({"error": "Could not extract text from PDF"}), 400
        
        # Detect language and translate if Hindi
        lang = detect_language(text)
        translated_text = None
        if lang == 'hi':
            translated_text = translate_text(text, 'en')
        
        # Categorize and extract info
        analysis_text = translated_text or text
        category = categorize_document(analysis_text)
        key_info = extract_key_info(analysis_text)
        summary = generate_pdf_summary(analysis_text, key_info, category)
        
        # Update database
        conn = sqlite3.connect(DB_FILE)
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
            "translated": lang == 'hi',
            "cached": False
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/data')
def get_data():
    """Get all announcements data with optional filtering."""
    category = request.args.get('category', '')
    limit = min(int(request.args.get('limit', 100)), 500)
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if category:
        c.execute("SELECT * FROM announcements WHERE category = ? ORDER BY id DESC LIMIT ?", 
                  (category, limit))
    else:
        c.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT ?", (limit,))
    
    rows = c.fetchall()
    data = [dict(row) for row in rows]
    conn.close()
    
    return jsonify(data)


@app.route('/api/categories')
def get_categories():
    """Get list of all categories."""
    conn = sqlite3.connect(DB_FILE)
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
        "translation_support": TRANSLATOR_AVAILABLE,
        "language_detection": LANGDETECT_AVAILABLE
    })


if __name__ == '__main__':
    init_db()
    # OPTIONAL: Force a fresh scrape every time server restarts
    scrape_and_sync(analyze_pdfs=False)  # Don't analyze on startup for faster load
    app.run(debug=True, port=5007, threaded=True)
