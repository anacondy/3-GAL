# 3-GAL - Galgotias University Examination Announcements Scraper

A dynamic, real-time web scraper for Galgotias University examination announcements with AI-powered PDF analysis and a supernatural/grunge aesthetic UI.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-2.3+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 🌐 Live Demo

**[View Live Site](https://anacondy.github.io/3-GAL/)** - Automatically updated daily with fresh announcements.

> *[📸 Make sure to upload a new Screenshot/GIF here showing the newly updated UI with Tags and Context Descriptions!]*

## ✨ Features

- **🔄 Real-time Scraping**: Live data synchronization from Galgotias University announcements
- **📄 Smart Context Descriptions**: 1-line PDF summary/preview right on the dashboard
- **🏷️ Category Tagging**: Instant visual tags (e.g. Exam, Fees) appended to cards
- **🤖 AI PDF Analysis**: Intelligent document analysis with automatic categorization
- **🔍 Comprehensive Search**: Full-text search with support for dates, paper codes, and various query patterns
- **🌐 Hindi Translation**: Automatic detection and translation of Hindi PDFs to English
- **📱 Responsive Design**: Optimized for all devices - mobile (16:9, 20:9), tablet, desktop, and ultra-wide screens
- **⚡ 60 FPS Performance**: Smooth particle animations with GPU acceleration
- **🎨 Supernatural/Grunge UI**: Unique dark aesthetic with particle effects
- **🚀 GitHub Pages Deployment**: Automatic daily updates via GitHub Actions

## 📋 Requirements

### System Requirements
- Python 3.8 or higher
- 512 MB RAM minimum (1 GB recommended)
- 100 MB disk space

### Supported Platforms
- **Windows**: Windows 10/11
- **macOS**: macOS 10.15+
- **Linux**: Ubuntu 20.04+, Debian 11+, Fedora 35+

## 🚀 Quick Start

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/anacondy/3-GAL.git
   cd 3-GAL
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open in browser**
   ```
   http://localhost:5007
   ```

## 📖 Usage

### Search Features

The search supports various query patterns:

| Query Type | Example | Description |
|------------|---------|-------------|
| Text search | `examination` | Find announcements containing the word |
| Year filter | `2024` | Find announcements from 2024 |
| Date search | `15-01-2024` | Find announcements with specific date |
| Combined | `exam 2024` | Find exam announcements from 2024 |
| Paper code | `CS101` | Find specific paper codes |

### AI Summary (Intel Button)

Click the **INTEL** button on any announcement card to get:
- Document type/category
- Extracted paper codes
- Important dates and times
- Subject information
- Brief content summary

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + K` or `/` | Focus search |
| `Escape` | Close modal/summary |
| `C + O + 2` (hold 2s) | Show system registry |

### Admin Access

Type `upload` in the search box and enter `Alvido` for admin access.

## 🏗️ Project Structure

```
3-GAL/
├── app.py                 # Main Flask application
├── templates/
│   └── index.html         # Frontend template
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── LICENSE                # MIT License
├── .gitignore             # Git ignore rules
├── docs/                  # Documentation (optional)
│   ├── DEPLOYMENT.md      # Deployment guide
│   ├── API.md             # API reference
│   └── WIKI.md            # Wiki documentation
└── galgotias_cache.db     # SQLite database (auto-generated)
```

## 🔌 API Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page with announcements |
| `/api/sync` | POST | Trigger live data sync |
| `/api/search?q=query` | GET | Search announcements |
| `/api/analyze` | POST | Analyze PDF document |
| `/api/data` | GET | Get all announcements |
| `/api/categories` | GET | Get category list |
| `/health` | GET | Health check |

### API Examples

**Search**
```bash
curl "http://localhost:5007/api/search?q=exam%202024"
```

**Analyze PDF**
```bash
curl -X POST "http://localhost:5007/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/document.pdf"}'
```

**Sync Data**
```bash
curl -X POST "http://localhost:5007/api/sync"
```

## ☁️ Deployment

### Heroku

1. **Create Heroku app**
   ```bash
   heroku create your-app-name
   ```

2. **Create Procfile**
   ```
   web: gunicorn app:app --bind 0.0.0.0:$PORT
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

### PythonAnywhere

1. Create a PythonAnywhere account at https://www.pythonanywhere.com

2. Open a Bash console and clone the repository:
   ```bash
   git clone https://github.com/anacondy/3-GAL.git
   ```

3. Create a virtual environment:
   ```bash
   cd 3-GAL
   mkvirtualenv --python=/usr/bin/python3.10 3gal-env
   pip install -r requirements.txt
   ```

4. In the Web tab:
   - Set Source code: `/home/yourusername/3-GAL`
   - Set Working directory: `/home/yourusername/3-GAL`
   - Set WSGI configuration file to point to your app

5. WSGI file configuration:
   ```python
   import sys
   path = '/home/yourusername/3-GAL'
   if path not in sys.path:
       sys.path.append(path)
   from app import app as application
   ```

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5007
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5007"]
```

Build and run:
```bash
docker build -t 3-gal .
docker run -p 5007:5007 3-gal
```

## 💻 Desktop Application

### Building with Tauri (Recommended)

Tauri creates lightweight, secure desktop apps:

1. **Install prerequisites**
   ```bash
   # Install Rust
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   
   # Install Node.js (for Tauri CLI)
   # Download from https://nodejs.org/
   ```

2. **Initialize Tauri**
   ```bash
   npm init tauri-app
   ```

3. **Configure to wrap Flask app**

4. **Build for platforms**
   ```bash
   npm run tauri build
   ```

### Building with PyInstaller

For a pure Python executable:

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "templates:templates" app.py
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_DEBUG` | `True` | Enable debug mode |
| `PORT` | `5007` | Server port |
| `DB_FILE` | `galgotias_cache.db` | Database file path |

### Database

The application uses SQLite with FTS5 (Full-Text Search) for comprehensive search capabilities. The database is automatically created on first run.

## 🔄 Version Management & Troubleshooting

If experimental features break your site, you can revert back to the last known fully stable version (where short contexts, tags, and PDFs all worked perfectly).

**The Stable Version (Commit: e1df46c)**
- [Direct Link to Source Code for Version e1df46c](https://github.com/anacondy/3-GAL/tree/e1df46c)

### How to manually restore to this stable version:
If you mess up your local files or site structure, run these exact commands in your terminal:
`ash
# 1. Force your local codebase back to the stable commit
git reset --hard e1df46c

# 2. Force push this restored version back to GitHub to fix the live site
git push -f origin main
`

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Galgotias University for the announcement data
- Flask community for the excellent web framework
- pdfplumber for PDF text extraction

## 📞 Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/anacondy/3-GAL/issues) page.

---

**Made with ❤️ for Galgotias University students**
