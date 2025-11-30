# 3-GAL Wiki

Welcome to the 3-GAL documentation wiki!

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Features In-Depth](#features-in-depth)
4. [Configuration](#configuration)
5. [Customization](#customization)
6. [Troubleshooting](#troubleshooting)

## Overview

3-GAL (Galgotias Announcements Live) is a web-based scraping application designed to aggregate and display examination announcements from Galgotias University. It features real-time data synchronization, AI-powered PDF analysis, comprehensive search capabilities, and a unique supernatural/grunge aesthetic UI.

### Key Capabilities

- **Web Scraping**: Automatically fetches announcements from the university website
- **PDF Analysis**: Extracts and categorizes information from PDF documents
- **Language Translation**: Detects Hindi content and translates to English
- **Full-Text Search**: Supports complex queries with dates, paper codes, and keywords
- **Responsive Design**: Works on all devices from mobile to ultra-wide monitors

## Architecture

### Technology Stack

```
┌─────────────────────────────────────────────────────┐
│                    Frontend                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │    HTML5    │  │    CSS3     │  │ Vanilla JS  │  │
│  │  (Jinja2)   │  │ (Responsive)│  │ (ES6+)      │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                  Backend (Flask)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   Routes    │  │   Scraper   │  │ PDF Engine  │  │
│  │   (API)     │  │ (BeautifulS)│  │ (pdfplumber)│  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                   │
│  │ Translator  │  │   Search    │                   │
│  │(googletrans)│  │   (FTS5)    │                   │
│  └─────────────┘  └─────────────┘                   │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                   Database                           │
│  ┌─────────────────────────────────────────────────┐│
│  │              SQLite with FTS5                    ││
│  │  - announcements table                           ││
│  │  - announcements_fts (full-text search)          ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

### Data Flow

1. **Scraping**: `scrape_and_sync()` fetches HTML from university website
2. **Parsing**: BeautifulSoup extracts announcement links, dates, and titles
3. **Storage**: Data is saved to SQLite database with unique URL constraint
4. **Analysis**: PDFs are analyzed asynchronously via thread pool
5. **Search**: FTS5 enables fast, comprehensive full-text search
6. **Display**: Jinja2 templates render data with real-time updates

## Features In-Depth

### 1. Web Scraping

The scraper uses multiple strategies to extract announcements:

```python
# Strategy 1: "View Detail" links
links = soup.find_all("a", string=re.compile(r"View Detail", re.I))

# Strategy 2: Direct PDF links
pdf_links = soup.find_all("a", href=re.compile(r"\.pdf", re.I))
```

### 2. AI PDF Analysis

The PDF analysis pipeline:

```
PDF URL → Download → Extract Text → Detect Language
                                          ↓
                              ┌───────────┴───────────┐
                              ▼                       ▼
                         Hindi PDF              English PDF
                              │                       │
                         Translate                    │
                              │                       │
                              └───────────┬───────────┘
                                          ▼
                                    Categorize
                                          ↓
                              ┌───────────┴───────────┐
                              ▼                       ▼
                        Extract Info            Generate Summary
                        - Paper codes           - Type
                        - Dates                 - Key points
                        - Times                 - Brief content
                        - Subjects
```

**Categories detected:**
- Examination
- Academic Calendar
- Result
- Fee Notice
- Admission
- Uniform/Dress Code
- Event
- Assignment/Project
- Internship/Placement
- Important Dates
- General Notice

### 3. Comprehensive Search

Search capabilities:

| Feature | Example | How it works |
|---------|---------|--------------|
| Text | `examination` | LIKE query on title, summary |
| Year | `2024` | Date pattern extraction |
| Full date | `15-01-2024` | Date field search |
| Paper code | `CS101` | Pattern matching in content |
| Combined | `exam december 2024` | Multi-term AND search |

**FTS5 Query Building:**
```python
# User types: "exam 2024"
# Becomes: "exam"* OR "2024"*
```

### 4. Responsive Design

Breakpoints:

| Screen Size | CSS Media Query | Optimizations |
|-------------|-----------------|---------------|
| Mobile | `max-width: 480px` | Smaller fonts, compact cards |
| Tablet | `481px - 768px` | Medium sizing |
| Desktop | `769px - 1199px` | Standard layout |
| Large | `1200px - 1599px` | Wider container |
| Ultra-wide | `1600px+` | Larger fonts, expanded layout |
| Tall mobile | `9/19` aspect | Adjusted height |

### 5. Performance Optimizations

- **GPU Acceleration**: `transform: translateZ(0)` for smooth animations
- **Frame Rate Control**: 60 FPS target with frame limiting
- **Lazy Loading**: PDF iframe loads on demand
- **Debounced Search**: 250ms delay prevents excessive API calls
- **DocumentFragment**: Batch DOM updates for rendering
- **Reduced Particles**: Fewer on mobile devices
- **Visibility API**: Pauses animation when tab is hidden

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_DEBUG` | `True` | Debug mode (disable in production) |
| `PORT` | `5007` | Server port |
| `DB_FILE` | `galgotias_cache.db` | Database path |
| `REQUEST_TIMEOUT` | `15` | Scraping timeout (seconds) |
| `PDF_DOWNLOAD_TIMEOUT` | `30` | PDF download timeout |

### Database Schema

```sql
CREATE TABLE announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_text TEXT,
    title TEXT,
    url TEXT UNIQUE,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pdf_summary TEXT,
    category TEXT,
    translated_title TEXT
);

CREATE VIRTUAL TABLE announcements_fts USING fts5(
    title, date_text, pdf_summary, translated_title, category,
    content='announcements', content_rowid='id'
);
```

## Customization

### Changing the Theme

Edit CSS variables in `templates/index.html`:

```css
:root {
    --bg-color: #0f0f0f;           /* Background */
    --glass-panel: rgba(30, 28, 20, 0.7);  /* Card background */
    --text-primary: #dcdcdc;       /* Main text */
    --text-accent: #c5b358;        /* Accent (gold) */
    --text-graffiti: #8c8c73;      /* Secondary text */
    --border-color: #3e3b32;       /* Borders */
}
```

### Adding New Categories

Edit the `categorize_document()` function in `app.py`:

```python
categories = {
    "Your Category": ['keyword1', 'keyword2', 'keyword3'],
    # ... existing categories
}
```

### Modifying Particle Effects

In the JavaScript section:

```javascript
// Change particle count
const particleCount = isMobile ? 50 : 100;

// Change particle color
ctx.fillStyle = 'rgba(197, 179, 88, 0.3)';  // Gold

// Change particle speed
this.speedX = (Math.random() - 0.5) * 0.5;
this.speedY = (Math.random() - 0.5) * 0.5;
```

## Troubleshooting

### Common Issues

#### 1. Database Locked
**Problem**: "database is locked" error
**Solution**: 
- Restart the application
- Kill any background processes
- Check for concurrent write operations

#### 2. PDF Analysis Fails
**Problem**: "Could not extract text from PDF"
**Solution**:
- Check if PDF is image-based (needs OCR)
- Verify PDF URL is accessible
- Check pdfplumber installation

#### 3. Scraping Fails
**Problem**: "SCRAPE FAILED" in logs
**Solution**:
- Verify internet connection
- Check if university site is up
- Site structure may have changed (update selectors)

#### 4. Slow Performance
**Problem**: UI feels sluggish
**Solution**:
- Reduce particle count
- Check for memory leaks
- Clear browser cache
- Use production mode (debug=False)

#### 5. Translation Errors
**Problem**: Hindi text not translated
**Solution**:
- Google Translate API limits may be hit
- Install googletrans correctly: `pip install googletrans==4.0.0-rc1`
- Check internet connectivity

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Check

Visit `/health` endpoint to verify system status:

```json
{
    "status": "healthy",
    "pdf_support": true,
    "translation_support": true,
    "language_detection": true
}
```
