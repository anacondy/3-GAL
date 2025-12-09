#!/usr/bin/env python3
"""
Generate static HTML site with live data from Galgotias University.
This script fetches announcements, processes them, and generates a static site
for deployment to GitHub Pages.
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Configuration
BASE_URL = "https://www.galgotiasuniversity.edu.in"
EXAM_URL = f"{BASE_URL}/p/announcements/examination-announcement"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
OUTPUT_DIR = "static_site"

# Maximum number of announcements to keep
# When this limit is reached, oldest announcements will be automatically removed
MAX_ANNOUNCEMENTS = 470


def fetch_announcements():
    """Fetch announcements from the university website."""
    print("--- [SYSTEM] FETCHING LIVE DATA... ---")
    announcements = []
    
    try:
        resp = requests.get(EXAM_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy 1: Find 'View Detail' links
        links = soup.find_all("a", string=re.compile(r"View Detail", re.I))

        for link in links:
            href = link.get("href", "").strip()
            if not href:
                continue
            if not href.startswith("http"):
                href = BASE_URL + href

            container = link.parent
            if not container:
                continue
            raw_text = container.get_text(" ", strip=True)

            date_match = re.search(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b", raw_text)
            if not date_match:
                date_match = re.search(r"\b(\d{1,2}\s+\w+\s+\d{4})\b", raw_text)

            if date_match:
                date_text = date_match.group(1)
                title = raw_text.replace(date_text, "").replace("View Detail", "").strip()
                title = re.sub(r"^[\.\-\:\s]+", "", title)

                announcements.append({
                    "date_text": date_text,
                    "title": title,
                    "url": href,
                    "category": categorize_title(title)
                })

        # Strategy 2: Also look for direct PDF links
        pdf_links = soup.find_all("a", href=re.compile(r"\.pdf", re.I))
        for link in pdf_links:
            href = link.get("href", "").strip()
            if not href:
                continue
            if not href.startswith("http"):
                href = BASE_URL + href
            
            # Check if we already have this URL
            if any(a["url"] == href for a in announcements):
                continue
            
            title = link.get_text(strip=True) or "PDF Document"
            if title in ["View Detail", "Download", "Click Here"]:
                parent = link.parent
                if parent:
                    title = parent.get_text(" ", strip=True)[:100]
            
            date_text = datetime.now().strftime("%d-%m-%Y")
            
            announcements.append({
                "date_text": date_text,
                "title": title,
                "url": href,
                "category": categorize_title(title)
            })

        # Apply MAX_ANNOUNCEMENTS limit - keep only the most recent ones
        if len(announcements) > MAX_ANNOUNCEMENTS:
            print(f"--- [CLEANUP] Limiting announcements from {len(announcements)} to {MAX_ANNOUNCEMENTS} (keeping most recent) ---")
            announcements = announcements[:MAX_ANNOUNCEMENTS]

        print(f"--- [SYSTEM] FETCHED {len(announcements)} ANNOUNCEMENTS ---")
        return announcements
        
    except Exception as e:
        print(f"--- [ERROR] FETCH FAILED: {e} ---")
        return []


def categorize_title(title):
    """Categorize announcement based on title."""
    title_lower = title.lower()
    
    categories = {
        "Examination": ['exam', 'examination', 'paper code', 'time table', 'datesheet', 'hall ticket', 'admit card'],
        "Result": ['result', 'marks', 'grade', 'cgpa', 'transcript'],
        "Academic Calendar": ['academic calendar', 'holiday', 'vacation', 'session'],
        "Fee Notice": ['fee', 'payment', 'dues', 'scholarship'],
        "Admission": ['admission', 'intake', 'enrollment', 'counseling'],
    }
    
    for category, keywords in categories.items():
        if any(kw in title_lower for kw in keywords):
            return category
    
    return "General Notice"


def generate_static_html(announcements):
    """Generate static HTML file with the announcements."""
    
    # Generate card HTML
    cards_html = ""
    if announcements:
        for item in announcements:
            category_html = f'<span class="card-category">{item.get("category", "")}</span>' if item.get("category") else ''
            cards_html += f'''
            <div class="exam-card" data-url="{item['url']}">
                <div class="card-header">
                    <div>
                        <div class="card-date">{item['date_text']}</div>
                        <div class="card-title">{item['title']}</div>
                    </div>
                    {category_html}
                </div>
            </div>
            '''
    else:
        cards_html = '<div style="text-align:center; color: #666; margin-top: 20px;">[ NO RECORDS FOUND ]</div>'
    
    # Generate a complete static page
    html_content = generate_full_static_html(announcements)
    
    return html_content


def generate_full_static_html(announcements):
    """Generate a complete static HTML page with all features from PR #2."""
    
    # Generate announcement cards
    cards_html = ""
    if announcements:
        for item in announcements:
            category_html = f'<span class="card-category">{item.get("category", "")}</span>' if item.get("category") else ''
            # Escape special characters in title and URL for HTML and JavaScript
            title = item['title'].replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            date_text = item['date_text']
            
            cards_html += f'''
            <div class="exam-card" data-url="{item['url'].replace('"', '&quot;')}" onclick="openPdf(this.dataset.url)">
                <div class="card-header">
                    <div>
                        <div class="card-date">{date_text}</div>
                        <div class="card-title">{title}</div>
                    </div>
                    {category_html}
                </div>
            </div>
            '''
    else:
        cards_html = '<div style="text-align:center; color: #666; margin-top: 20px;">[ NO RECORDS FOUND - CHECK BACK LATER ]</div>'

    # Last updated timestamp
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    html = f'''<!DOCTYPE html>
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
        :root {{
            --bg-color: #0f0f0f;
            --glass-panel: rgba(30, 28, 20, 0.7);
            --text-primary: #dcdcdc;
            --text-accent: #c5b358;
            --text-graffiti: #8c8c73;
            --border-color: #3e3b32;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html {{ scroll-behavior: smooth; -webkit-text-size-adjust: 100%; }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Special Elite', monospace;
            overflow-x: hidden;
            min-height: 100vh;
            display: flex; flex-direction: column; align-items: center;
            -webkit-font-smoothing: antialiased;
            touch-action: pan-x pan-y;
        }}
        #particle-canvas {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            z-index: -1;
            background: radial-gradient(circle at center, rgba(40,35,30,0.2) 0%, rgba(0,0,0,0.95) 100%);
        }}
        .container {{
            width: 90%; max-width: 1000px; margin-top: 5vh; min-height: 90vh;
            display: flex; flex-direction: column; gap: 20px; z-index: 10;
            padding-bottom: 20px;
        }}
        header {{ text-align: center; position: relative; margin-bottom: 20px; }}
        h1 {{
            font-family: 'Oswald', sans-serif; font-size: 4rem;
            color: var(--text-primary); text-transform: uppercase;
            letter-spacing: 5px;
            text-shadow: 0 0 20px rgba(197, 179, 88, 0.3);
        }}
        .graffiti-tag {{
            position: absolute; top: -10px; right: 10%;
            font-family: 'Special Elite', cursive;
            color: var(--text-graffiti); font-size: 1.2rem;
            transform: rotate(15deg); opacity: 0.8;
        }}
        .last-updated {{
            font-size: 0.8rem; color: var(--text-graffiti);
            margin-top: 5px;
        }}
        .search-wrapper {{ position: relative; width: 100%; }}
        #search-input {{
            width: 100%; background: rgba(0, 0, 0, 0.5);
            border: 2px solid var(--text-accent); color: var(--text-accent);
            padding: 15px 20px; font-family: 'Special Elite', monospace;
            font-size: 1.2rem; outline: none; text-transform: uppercase;
        }}
        #search-input:focus {{
            border-color: #e5d388;
            box-shadow: 0 0 10px rgba(197, 179, 88, 0.3);
        }}
        .results-container {{
            flex-grow: 1; overflow-y: auto;
            border-top: 1px solid var(--border-color); padding-right: 10px;
        }}
        .results-container::-webkit-scrollbar {{ width: 6px; }}
        .results-container::-webkit-scrollbar-thumb {{ background: var(--text-graffiti); border-radius: 3px; }}
        .exam-card {{
            background: var(--glass-panel); backdrop-filter: blur(5px);
            border-left: 4px solid var(--border-color);
            margin-bottom: 15px; padding: 20px;
            cursor: pointer;
            transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
        }}
        .exam-card:hover {{
            border-left-color: var(--text-accent);
            background: rgba(50, 45, 30, 0.8);
            transform: translateX(5px);
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 10px;
        }}
        .card-date {{ font-size: 0.9rem; color: var(--text-graffiti); margin-bottom: 5px; font-weight: bold; }}
        .card-title {{ font-size: 1.2rem; color: var(--text-primary); }}
        .card-category {{
            font-size: 0.75rem;
            color: var(--text-accent);
            background: rgba(197, 179, 88, 0.15);
            padding: 3px 8px;
            border-radius: 3px;
            white-space: nowrap;
        }}
        
        /* PDF Modal */
        #pdf-modal {{
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.95); z-index: 100;
            justify-content: center; align-items: center; flex-direction: column;
        }}
        .modal-controls {{
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        #pdf-frame {{ width: 85%; height: 80%; border: 1px solid var(--text-accent); background: #fff; touch-action: auto; }}
        /* PDF Loading Indicator */
        .pdf-loading {{
            display: none;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: var(--text-accent);
            font-family: 'Oswald', sans-serif;
            font-size: 1.2rem;
            text-transform: uppercase;
            z-index: 101;
        }}
        .pdf-loading.active {{ display: block; }}
        .pdf-loading::after {{
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid var(--text-graffiti);
            border-top-color: var(--text-accent);
            border-radius: 50%;
            margin-left: 10px;
            animation: spin 1s linear infinite;
            vertical-align: middle;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .close-btn {{
            background: transparent; color: var(--text-primary);
            border: 1px solid var(--text-accent); padding: 8px 20px; cursor: pointer;
            font-family: 'Oswald', sans-serif; font-size: 1.1rem;
            transition: all 0.2s ease;
        }}
        .close-btn:hover {{
            background: var(--text-accent);
            color: var(--bg-color);
        }}
        .stats {{
            text-align: center;
            font-size: 0.9rem;
            color: var(--text-graffiti);
            padding: 10px;
            background: rgba(0,0,0,0.3);
            margin-bottom: 10px;
        }}
        
        /* Responsive - Mobile devices */
        @media screen and (max-width: 480px) {{
            h1 {{ font-size: 2.2rem; letter-spacing: 2px; }}
            .graffiti-tag {{ font-size: 0.9rem; right: 5%; }}
            .container {{ width: 95%; margin-top: 2vh; gap: 15px; }}
            #search-input {{ padding: 12px 15px; font-size: 1rem; }}
            .exam-card {{ padding: 15px; margin-bottom: 10px; }}
            .card-title {{ font-size: 1rem; }}
            .card-date {{ font-size: 0.8rem; }}
            #pdf-frame {{ width: 95%; height: 70%; }}
            .close-btn {{ padding: 6px 15px; font-size: 0.9rem; }}
        }}

        /* Tablets */
        @media screen and (min-width: 481px) and (max-width: 768px) {{
            h1 {{ font-size: 3rem; }}
            .container {{ width: 92%; }}
            #search-input {{ font-size: 1.1rem; }}
            .card-title {{ font-size: 1.1rem; }}
            #pdf-frame {{ width: 90%; }}
        }}

        /* Large screens / Desktop */
        @media screen and (min-width: 1200px) {{
            .container {{ max-width: 1100px; }}
            h1 {{ font-size: 4.5rem; }}
            .card-title {{ font-size: 1.3rem; }}
            .card-date {{ font-size: 1rem; }}
            #search-input {{ font-size: 1.3rem; padding: 18px 25px; }}
        }}

        /* Extra large / Wide screens */
        @media screen and (min-width: 1600px) {{
            .container {{ max-width: 1300px; }}
            h1 {{ font-size: 5rem; letter-spacing: 8px; }}
            .graffiti-tag {{ font-size: 1.5rem; }}
            .card-title {{ font-size: 1.5rem; }}
            .card-date {{ font-size: 1.1rem; }}
            #search-input {{ font-size: 1.5rem; padding: 20px 30px; }}
            .exam-card {{ padding: 25px; margin-bottom: 20px; }}
            .close-btn {{ font-size: 1.3rem; padding: 10px 25px; }}
        }}

        /* Ultra-wide screens */
        @media screen and (min-width: 2000px) {{
            .container {{ max-width: 1500px; }}
            h1 {{ font-size: 6rem; }}
            .card-title {{ font-size: 1.7rem; }}
            .card-date {{ font-size: 1.2rem; }}
            #search-input {{ font-size: 1.7rem; }}
        }}

        /* Tall mobile screens (20:9 like modern phones) */
        @media screen and (max-width: 480px) and (min-aspect-ratio: 9/19) {{
            .container {{ margin-top: 3vh; }}
            .results-container {{ max-height: 70vh; }}
        }}

        /* Standard mobile (16:9) */
        @media screen and (max-width: 480px) and (max-aspect-ratio: 9/16) {{
            .results-container {{ max-height: 65vh; }}
        }}

        /* Landscape mobile */
        @media screen and (max-height: 500px) and (orientation: landscape) {{
            .container {{ margin-top: 2vh; }}
            h1 {{ font-size: 2rem; }}
            .results-container {{ max-height: 50vh; }}
            #pdf-frame {{ height: 60%; }}
        }}

        /* Reduced motion preference */
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }}
            #particle-canvas {{ display: none; }}
        }}

        /* High contrast mode */
        @media (prefers-contrast: high) {{
            :root {{
                --text-primary: #ffffff;
                --text-accent: #ffd700;
                --border-color: #666666;
            }}
        }}
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
            <span class="graffiti-tag">live_v2</span>
            <h1>Examination</h1>
            <div class="last-updated">Last Updated: {last_updated}</div>
        </header>

        <div class="search-wrapper">
            <input type="text" id="search-input" placeholder="SEARCH ANNOUNCEMENTS..." autocomplete="off" spellcheck="false">
        </div>

        <div class="stats">
            📢 {len(announcements)} announcements loaded (max {MAX_ANNOUNCEMENTS})
        </div>

        <div class="results-container" id="results-list">
            {cards_html}
        </div>
    </div>

    <script>
        // Store all cards for search
        const allCards = document.querySelectorAll('.exam-card');
        
        // Search functionality
        document.getElementById('search-input').addEventListener('input', function(e) {{
            const query = e.target.value.toLowerCase();
            allCards.forEach(card => {{
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(query) ? 'block' : 'none';
            }});
        }});

        // PDF Viewer - Uses Google Docs Viewer for cross-device compatibility
        function openPdf(url) {{
            const pdfFrame = document.getElementById('pdf-frame');
            const pdfLoading = document.getElementById('pdf-loading');
            
            // Show loading indicator
            pdfLoading.classList.add('active');
            
            // Use Google Docs PDF Viewer for reliable cross-device PDF rendering
            // This works on both mobile and desktop, displaying the PDF content directly
            const googleDocsUrl = 'https://docs.google.com/viewer?url=' + encodeURIComponent(url) + '&embedded=true';
            pdfFrame.src = googleDocsUrl;
            
            // Hide loading when iframe loads
            pdfFrame.onload = function() {{
                pdfLoading.classList.remove('active');
            }};
            
            document.getElementById('pdf-modal').style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }}
        
        function closePdf() {{
            document.getElementById('pdf-modal').style.display = 'none';
            document.getElementById('pdf-frame').src = '';
            document.getElementById('pdf-loading').classList.remove('active');
            document.body.style.overflow = '';
        }}

        // ESC to close
        document.addEventListener('keydown', (e) => {{
            if(e.key === 'Escape') closePdf();
        }});

        // Particles
        const canvas = document.getElementById('particle-canvas');
        const ctx = canvas.getContext('2d');
        let particles = [];
        
        function resizeCanvas() {{
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }}
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);

        class Particle {{
            constructor() {{
                this.x = Math.random() * canvas.width;
                this.y = Math.random() * canvas.height;
                this.size = Math.random() * 2;
                this.speedX = (Math.random() - 0.5) * 0.5;
                this.speedY = (Math.random() - 0.5) * 0.5;
                this.alpha = Math.random() * 0.5;
            }}
            update() {{
                this.x += this.speedX;
                this.y += this.speedY;
                this.alpha -= 0.002;
                if(this.alpha <= 0) this.alpha = 0.5;
                if(this.x > canvas.width) this.x = 0;
                if(this.x < 0) this.x = canvas.width;
                if(this.y > canvas.height) this.y = 0;
                if(this.y < 0) this.y = canvas.height;
            }}
        }}

        const isMobile = window.innerWidth < 768 || ('ontouchstart' in window);
        for(let i = 0; i < (isMobile ? 50 : 100); i++) particles.push(new Particle());

        function animate() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.beginPath();
            particles.forEach(p => {{
                p.update();
                ctx.moveTo(p.x + p.size, p.y);
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            }});
            ctx.fillStyle = 'rgba(197, 179, 88, 0.3)';
            ctx.fill();
            requestAnimationFrame(animate);
        }}
        animate();
    </script>
</body>
</html>'''
    
    return html


def main():
    """Main function to generate static site."""
    print("=" * 50)
    print("3-GAL Static Site Generator")
    print("=" * 50)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Fetch announcements
    announcements = fetch_announcements()
    
    # Generate static HTML
    html_content = generate_static_html(announcements)
    
    # Write to file
    output_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"--- [SUCCESS] Generated {output_path} ---")
    print(f"--- [INFO] Total announcements: {len(announcements)} ---")
    
    # Also save data as JSON for reference
    json_path = os.path.join(OUTPUT_DIR, "data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "count": len(announcements),
            "announcements": announcements
        }, f, indent=2)
    
    print(f"--- [SUCCESS] Generated {json_path} ---")


if __name__ == "__main__":
    main()
