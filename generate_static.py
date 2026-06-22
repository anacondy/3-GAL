#!/usr/bin/env python3
"""
Generate static HTML site with live data from Galgotias University.

Phase 2 patch: html.escape() on category and desc fields (XSS prevention).
Phase 3 patch: All configuration imported from config.py (single source of truth).
"""

import os
import re
import json
import html
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Phase 3 P3-07: centralize all configuration in config.py
from config import (
    BASE_URL, EXAM_URL, HEADERS, MAX_ANNOUNCEMENTS,
)


def parse_date_for_sorting(date_text):
    try:
        if '-' in date_text or '/' in date_text:
            separator = '-' if '-' in date_text else '/'
            parts = date_text.split(separator)
            if len(parts) == 3:
                try:
                    return datetime.strptime(date_text, f'%d{separator}%m{separator}%Y')
                except:
                    pass
                try:
                    return datetime.strptime(date_text, f'%d{separator}%m{separator}%y')
                except:
                    pass
        try:
            return datetime.strptime(date_text, '%d %B %Y')
        except:
            pass
        try:
            return datetime.strptime(date_text, '%d %b %Y')
        except:
            pass
    except:
        pass
    return datetime.now()


def fetch_announcements():
    print("--- [SYSTEM] FETCHING LIVE DATA... ---")
    announcements = []
    try:
        resp = requests.get(EXAM_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        pdf_links = soup.find_all("a", href=re.compile(r"\.pdf", re.I))
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
                        announcements.append({
                            "date_text": date_text,
                            "title": title,
                            "url": href,
                            "category": categorize_title(title),
                            "desc": get_short_desc(title, categorize_title(title)),
                        })
                        continue
            title = link.get_text(" ", strip=True)
            title = re.sub(r'\s+', ' ', title)
            if re.search(r'view\s*detail|download|click\s*here', title, re.IGNORECASE):
                if parent:
                    title = re.sub(r'\s+', ' ', parent.get_text(" ", strip=True))[:100]
                    title = re.sub(r'View\s*Detail', '', title, flags=re.IGNORECASE).strip()
            date_text = datetime.now().strftime("%d-%m-%Y")
            announcements.append({
                "date_text": date_text,
                "title": title,
                "url": href,
                "category": categorize_title(title),
                "desc": get_short_desc(title, categorize_title(title)),
            })
        announcements.sort(key=lambda x: parse_date_for_sorting(x.get('date_text', '')), reverse=True)
        if len(announcements) > MAX_ANNOUNCEMENTS:
            print(f"--- [CLEANUP] Limiting announcements from {len(announcements)} to {MAX_ANNOUNCEMENTS} (keeping most recent) ---")
            announcements = announcements[:MAX_ANNOUNCEMENTS]
        print(f"--- [SYSTEM] FETCHED {len(announcements)} ANNOUNCEMENTS ---")
        return announcements
    except Exception as e:
        print(f"--- [ERROR] FETCH FAILED: {e} ---")
        return []


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

def categorize_title(title):
    title_lower = title.lower()
    if any(kw in title_lower for kw in ['result', 'marks', 'grade', 'cgpa', 'transcript']): return "Result"
    if any(kw in title_lower for kw in ['fee', 'payment', 'dues', 'scholarship', 'financial', 'fine']): return "Fees"
    if any(kw in title_lower for kw in ['holiday', 'vacation', 'closure']): return "Holiday"
    if any(kw in title_lower for kw in ['event', 'festival', 'celebration', 'cultural']): return "Event"
    if any(kw in title_lower for kw in ['admission', 'intake', 'enrollment', 'counseling']): return "Admissions"
    if any(kw in title_lower for kw in ['exam', 'examination', 'paper code', 'date sheet', 'timetable', 'hall ticket', 'admit card', 'debarred']): return "Exam"
    if any(kw in title_lower for kw in ['academic calendar', 'session']): return "Calendar"
    return "Notice"


def generate_full_static_html(announcements):
    cards_html = ""
    if announcements:
        for item in announcements:
            title_esc = html.escape(item['title'])
            url_esc = html.escape(item['url'], quote=True)
            date_text_esc = html.escape(item['date_text'])
            category_esc = html.escape(item.get('category', '') or '')
            desc_esc = html.escape(item.get('desc', get_short_desc(title_esc, item.get('category', ''))))
            category_html = f'<span class="card-category">{category_esc}</span>' if item.get('category') else ''
            cards_html += f'''
            <div class="exam-card" data-url="{url_esc}" onclick="openPdf(this.dataset.url)">
                <div class="card-header">
                    <div>
                        <div class="card-date">{date_text_esc}</div>
                        <div class="card-title">{title_esc}</div>
                        <div class="card-desc" style="font-size:0.85rem; color:var(--text-graffiti); margin-top:8px; border-top:1px dashed rgba(140,140,115,0.2); padding-top:8px;">{desc_esc}</div>
                    </div>
                    {category_html}
                </div>
            </div>
            '''
    else:
        cards_html = '<div style="text-align:center; color: #666; margin-top: 20px;">[ NO RECORDS FOUND - CHECK BACK LATER ]</div>'

    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    html_doc = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#0f0f0f">
    <meta name="description" content="Galgotias University Examination Announcements - Live Updates">
    <title>DESTINY // EXAMS - Galgotias University</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Special+Elite&display=swap" rel="stylesheet">
    <style>
        :root {{ --bg-color: #0f0f0f; --glass-panel: rgba(30, 28, 20, 0.7); --text-primary: #dcdcdc; --text-accent: #c5b358; --text-graffiti: #8c8c73; --border-color: #3e3b32; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html {{ scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }}
        body {{ background-color: var(--bg-color); color: var(--text-primary); font-family: 'Special Elite', monospace; overflow-x: hidden; min-height: 100vh; display: flex; flex-direction: column; align-items: center; }}
        #particle-canvas {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1; background: radial-gradient(circle at center, rgba(40,35,30,0.2) 0%, rgba(0,0,0,0.95) 100%); }}
        .container {{ width: 90%; max-width: 1000px; margin-top: 5vh; display: flex; flex-direction: column; gap: 20px; z-index: 10; padding-bottom: 20px; }}
        header {{ text-align: center; position: relative; margin-bottom: 20px; }}
        h1 {{ font-family: 'Oswald', sans-serif; font-size: 4rem; color: var(--text-primary); text-transform: uppercase; letter-spacing: 5px; text-shadow: 0 0 20px rgba(197, 179, 88, 0.3); }}
        .last-updated {{ font-size: 0.8rem; color: var(--text-graffiti); margin-top: 5px; }}
        #search-input {{ width: 100%; background: rgba(0, 0, 0, 0.5); border: 2px solid var(--text-accent); color: var(--text-accent); padding: 15px 20px; font-family: 'Special Elite', monospace; font-size: 1.2rem; outline: none; text-transform: uppercase; }}
        #search-input:focus {{ border-color: #e5d388; box-shadow: 0 0 10px rgba(197, 179, 88, 0.3); }}
        .results-container {{ flex-grow: 1; border-top: 1px solid var(--border-color); padding-right: 10px; }}
        .exam-card {{ background: var(--glass-panel); backdrop-filter: blur(5px); border-left: 4px solid var(--border-color); margin-bottom: 15px; padding: 20px; cursor: pointer; transition: all 0.2s ease; }}
        .exam-card:hover {{ border-left-color: var(--text-accent); background: rgba(50, 45, 30, 0.8); transform: translateX(5px); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }}
        .card-date {{ font-size: 0.9rem; color: var(--text-graffiti); margin-bottom: 5px; font-weight: bold; }}
        .card-title {{ font-size: 1.2rem; color: var(--text-primary); }}
        .card-category {{ font-size: 0.75rem; color: var(--text-accent); background: rgba(197, 179, 88, 0.15); padding: 3px 8px; border-radius: 3px; }}
        #pdf-modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 100; justify-content: center; align-items: center; flex-direction: column; }}
        .modal-controls {{ display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; justify-content: center; }}
        #pdf-frame {{ width: 85%; height: 80%; border: 1px solid var(--text-accent); background: #fff; }}
        .pdf-loading {{ display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: var(--text-accent); font-family: 'Oswald', sans-serif; font-size: 1.2rem; text-transform: uppercase; z-index: 101; }}
        .pdf-loading.active {{ display: block; }}
        .pdf-loading::after {{ content: ''; display: inline-block; width: 20px; height: 20px; border: 2px solid var(--text-graffiti); border-top-color: var(--text-accent); border-radius: 50%; margin-left: 10px; animation: spin 1s linear infinite; vertical-align: middle; }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .close-btn {{ background: transparent; color: var(--text-primary); border: 1px solid var(--text-accent); padding: 8px 20px; cursor: pointer; font-family: 'Oswald', sans-serif; font-size: 1.1rem; }}
        .close-btn:hover {{ background: var(--text-accent); color: var(--bg-color); }}
        .stats {{ text-align: center; font-size: 0.9rem; color: var(--text-graffiti); padding: 10px; background: rgba(0,0,0,0.3); margin-bottom: 10px; }}
        @media screen and (max-width: 480px) {{ h1 {{ font-size: 2.2rem; letter-spacing: 2px; }} .container {{ width: 95%; margin-top: 2vh; gap: 15px; }} #search-input {{ padding: 12px 15px; font-size: 1rem; }} .exam-card {{ padding: 15px; margin-bottom: 10px; }} .card-title {{ font-size: 1rem; }} .card-date {{ font-size: 0.8rem; }} #pdf-frame {{ width: 95%; height: 70%; }} .close-btn {{ padding: 6px 15px; font-size: 0.9rem; }} }}
        @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }} #particle-canvas {{ display: none; }} }}
    </style>
</head>
<body>
    <canvas id="particle-canvas"></canvas>
    <div id="pdf-modal">
        <div class="modal-controls">
            <button class="close-btn" onclick="closePdf()">[ CLOSE FILE ]</button>
        </div>
        <div class="pdf-loading" id="pdf-loading">Loading PDF</div>
        <iframe id="pdf-frame" loading="lazy"></iframe>
    </div>
    <div class="container">
        <header>
            <h1>Examination</h1>
            <div class="last-updated">Last Updated: {html.escape(last_updated)}</div>
        </header>
        <div class="search-wrapper">
            <input type="text" id="search-input" placeholder="SEARCH ANNOUNCEMENTS..." autocomplete="off" spellcheck="false">
        </div>
        <div class="stats">📢 {len(announcements)} announcements loaded (max {MAX_ANNOUNCEMENTS})</div>
        <div class="results-container" id="results-list">{cards_html}</div>
    </div>
    <script>
        const allCards = document.querySelectorAll('.exam-card');
        document.getElementById('search-input').addEventListener('input', function(e) {{
            const query = e.target.value.toLowerCase();
            allCards.forEach(card => {{ const text = card.textContent.toLowerCase(); card.style.display = text.includes(query) ? 'block' : 'none'; }});
        }});
        function openPdf(url) {{
            const pdfFrame = document.getElementById('pdf-frame');
            const pdfLoading = document.getElementById('pdf-loading');
            pdfLoading.classList.add('active');
            const googleDocsUrl = 'https://docs.google.com/viewer?url=' + encodeURIComponent(url) + '&embedded=true';
            pdfFrame.src = googleDocsUrl;
            pdfFrame.onload = function() {{ pdfLoading.classList.remove('active'); }};
            document.getElementById('pdf-modal').style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }}
        function closePdf() {{
            document.getElementById('pdf-modal').style.display = 'none';
            document.getElementById('pdf-frame').src = '';
            document.getElementById('pdf-loading').classList.remove('active');
            document.body.style.overflow = '';
        }}
        document.addEventListener('keydown', (e) => {{ if(e.key === 'Escape') closePdf(); }});
    </script>
</body>
</html>'''
    return html_doc


def generate_static_html(announcements):
    return generate_full_static_html(announcements)


def main():
    print("=" * 50)
    print("3-GAL Static Site Generator")
    print("=" * 50)
    output_dir = os.environ.get("OUTPUT_DIR", "static_site")
    os.makedirs(output_dir, exist_ok=True)
    announcements = fetch_announcements()
    html_content = generate_static_html(announcements)
    output_path = os.path.join(output_dir, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"--- [SUCCESS] Generated {output_path} ---")
    print(f"--- [INFO] Total announcements: {len(announcements)} ---")
    json_path = os.path.join(output_dir, "data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(), "count": len(announcements), "announcements": announcements}, f, indent=2)
    print(f"--- [SUCCESS] Generated {json_path} ---")


if __name__ == "__main__":
    main()
