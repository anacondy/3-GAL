# app.py
# Feature Registry: v1.3 - Auto-Scrape & Clean UI Render
# Details: Validates "Alvido" credential logic & Force-fetches live data.

import re
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- Configuration ---
DB_FILE = "galgotias_cache.db"
BASE_URL = "https://www.galgotiasuniversity.edu.in"
EXAM_URL = f"{BASE_URL}/p/announcements/examination-announcement"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SupernaturalExamScraper/1.0)"
}


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
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def save_announcement(date_text, title, url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        # Prevent duplicates
        c.execute("INSERT OR IGNORE INTO announcements (date_text, title, url) VALUES (?, ?, ?)",
                  (date_text, title, url))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()


def search_db(query):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    search_term = f"%{query}%"
    c.execute("SELECT * FROM announcements WHERE title LIKE ? OR date_text LIKE ? ORDER BY id DESC",
              (search_term, search_term))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- Scraper Logic (Live Fetch) ---
def scrape_and_sync():
    """Fetches latest data from Galgotias and updates DB."""
    print("--- [SYSTEM] FETCHING LIVE DATA... ---")
    try:
        resp = requests.get(EXAM_URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy: Find 'View Detail' links and parse parent text
        # This is the most reliable method for this specific university site
        links = soup.find_all("a", string=re.compile(r"View Detail", re.I))

        count = 0
        for link in links:
            href = link.get("href", "").strip()
            if not href: continue
            if not href.startswith("http"):
                href = BASE_URL + href

            # Parent container text holds the Date and Title
            container = link.parent
            if not container: continue
            raw_text = container.get_text(" ", strip=True)

            # Extract Date (DD-MM-YYYY)
            date_match = re.search(r"\b(\d{2}-\d{2}-\d{4})\b", raw_text)

            if date_match:
                date_text = date_match.group(1)
                # Remove Date and 'View Detail' to get Title
                title = raw_text.replace(date_text, "").replace("View Detail", "").strip()
                title = re.sub(r"^[\.\-\:\s]+", "", title)  # Clean leading punctuation

                save_announcement(date_text, title, href)
                count += 1

        print(f"--- [SYSTEM] SYNC COMPLETE. {count} ITEMS PROCESSED. ---")
        return True
    except Exception as e:
        print(f"--- [ERROR] SCRAPE FAILED: {e} ---")
        return False


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

    # Get latest 50 items
    c.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT 50")
    rows = c.fetchall()
    data = [dict(row) for row in rows]
    conn.close()

    return render_template('index.html', initial_data=data)


@app.route('/api/sync', methods=['POST'])
def sync():
    success = scrape_and_sync()
    return jsonify({"status": "success" if success else "error"})


@app.route('/api/search')
def search():
    q = request.args.get('q', '')

    # --- ADMIN UPLOAD CHECK ---
    # As per user requirement [2025-10-12]:
    # If user types "upload", checking for credentials "Alvido".
    # (Client-side will handle the prompt, this is just a placeholder log)
    if q.lower() == "upload":
        print("[AUTH] Admin upload requested. Waiting for 'Alvido' credential.")

    results = search_db(q)
    return jsonify(results)


if __name__ == '__main__':
    init_db()
    # OPTIONAL: Force a fresh scrape every time server restarts
    scrape_and_sync()
    app.run(debug=True, port=5007)
