"""
config.py — Centralized configuration for 3-GAL.

Both app.py and generate_static.py import from this module so that
constants like MAX_ANNOUNCEMENTS, ALLOWED_PDF_DOMAINS, etc. live in
exactly one place. Previously these were duplicated (Phase 3 P3-07).

Override any value at runtime via environment variable of the same
name (e.g. `MAX_ANNOUNCEMENTS=1000 python app.py`).
"""

import os

# --- Database ---
DB_FILE = os.environ.get("DB_FILE", "galgotias_cache.db")
MAX_ANNOUNCEMENTS = int(os.environ.get("MAX_ANNOUNCEMENTS", "470"))

# --- Network: target site ---
BASE_URL = os.environ.get("BASE_URL", "https://www.galgotiasuniversity.edu.in")
EXAM_URL = os.environ.get(
    "EXAM_URL",
    f"{BASE_URL}/p/announcements/examination-announcement",
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# --- Timeouts (seconds) ---
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "15"))
PDF_DOWNLOAD_TIMEOUT = int(os.environ.get("PDF_DOWNLOAD_TIMEOUT", "30"))

# --- Size limits ---
MAX_PDF_BYTES = int(os.environ.get("MAX_PDF_BYTES", str(25 * 1024 * 1024)))  # 25 MB
MAX_TEXT_PER_PAGE = int(os.environ.get("MAX_TEXT_PER_PAGE", "5000"))
MAX_TEXT_TOTAL = int(os.environ.get("MAX_TEXT_TOTAL", "50000"))

# --- Search ---
MAX_QUERY_LENGTH = int(os.environ.get("MAX_QUERY_LENGTH", "500"))
MAX_QUERY_TOKENS = int(os.environ.get("MAX_QUERY_TOKENS", "32"))

# --- SSRF allowlist (Phase 1 P1-01) ---
ALLOWED_PDF_DOMAINS = [
    "galgotiasuniversity.edu.in",
    "www.galgotiasuniversity.edu.in",
]

# --- Server ---
DEFAULT_PORT = int(os.environ.get("PORT", "5007"))
