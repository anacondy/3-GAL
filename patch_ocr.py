"""
patch_ocr.py — One-shot patcher to add OCR fallback support to app.py.

Run this once after applying the rest of Phase 4:
    python patch_ocr.py

It modifies app.py in-place to:
1. Import OCR_ENABLED from config
2. Add a `_try_ocr_page()` helper function
3. Update `extract_pdf_text()` to fall back to OCR when no text layer is found

The patch is idempotent — if you run it twice, the second run is a no-op.
"""
import sys
from pathlib import Path

APP_PY = Path("app.py")

if not APP_PY.exists():
    print(f"ERROR: {APP_PY} not found. Run this from your project root.", file=sys.stderr)
    sys.exit(1)

# Back up first
backup = APP_PY.with_suffix(".py.pre-ocr.bak")
if not backup.exists():
    import shutil
    shutil.copy(APP_PY, backup)
    print(f"Backed up to {backup}")

content = APP_PY.read_text(encoding="utf-8")

# --- Patch 1: add OCR_ENABLED to the config import ---
old_import = """from config import (
    DB_FILE, MAX_ANNOUNCEMENTS,
    BASE_URL, EXAM_URL, HEADERS,
    REQUEST_TIMEOUT, PDF_DOWNLOAD_TIMEOUT,
    MAX_PDF_BYTES, MAX_TEXT_PER_PAGE, MAX_TEXT_TOTAL,
    MAX_QUERY_LENGTH, MAX_QUERY_TOKENS,
    ALLOWED_PDF_DOMAINS,
    DEFAULT_PORT,
)"""

new_import = """from config import (
    DB_FILE, MAX_ANNOUNCEMENTS,
    BASE_URL, EXAM_URL, HEADERS,
    REQUEST_TIMEOUT, PDF_DOWNLOAD_TIMEOUT,
    MAX_PDF_BYTES, MAX_TEXT_PER_PAGE, MAX_TEXT_TOTAL,
    MAX_QUERY_LENGTH, MAX_QUERY_TOKENS,
    ALLOWED_PDF_DOMAINS,
    DEFAULT_PORT,
    OCR_ENABLED,  # Phase 4
)"""

if "OCR_ENABLED," not in content:
    if old_import in content:
        content = content.replace(old_import, new_import)
        print("[OK] Added OCR_ENABLED to config import")
    else:
        print("WARN: Couldn't find config import block; OCR_ENABLED won't be imported automatically.")
        print("      Add it manually if needed.")
else:
    print("[skip] OCR_ENABLED already imported")

# --- Patch 2: replace extract_pdf_text() with OCR-aware version ---
old_extract = """def extract_pdf_text(pdf_bytes):
    \"\"\"Extract text from PDF bytes with length caps (P2-05).\"\"\"
    if not PDF_AVAILABLE or pdf_bytes is None:
        return None

    try:
        with pdfplumber.open(pdf_bytes) as pdf:
            text = \"\"
            for page in pdf.pages[:10]:  # Limit to first 10 pages for performance
                page_text = page.extract_text()
                if page_text:
                    text += page_text + \"\\n\"
            return text.strip()
    except Exception as e:
        print(f\"PDF extraction error: {e}\")
        return None"""

new_extract = """def _try_ocr_page(page):
    \"\"\"Phase 4: OCR a single pdfplumber page using pytesseract + pdf2image.

    Returns the OCR'd text, or None if OCR is unavailable or fails.
    Only called when OCR_ENABLED is True AND no text layer was found.
    \"\"\"
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None
    try:
        # pdfplumber's to_image() returns a PIL Image
        pil_img = page.to_image(resolution=200).original
        return pytesseract.image_to_string(pil_img)
    except Exception as e:
        print(f\"OCR page error: {e}\")
        return None


def extract_pdf_text(pdf_bytes):
    \"\"\"Extract text from PDF bytes with length caps (P2-05) + optional OCR fallback (Phase 4).\"\"\"
    if not PDF_AVAILABLE or pdf_bytes is None:
        return None

    try:
        with pdfplumber.open(pdf_bytes) as pdf:
            text = \"\"
            for page in pdf.pages[:10]:
                page_text = page.extract_text() or \"\"
                text += page_text[:MAX_TEXT_PER_PAGE] + \"\\n\"
                if len(text) >= MAX_TEXT_TOTAL:
                    break

            # Phase 4: OCR fallback for image-only PDFs.
            # Only kicks in if (a) OCR_ENABLED env var is set AND (b) pytesseract + Tesseract binary are installed
            # AND (c) pdfplumber found no text layer at all.
            if not text.strip() and OCR_ENABLED:
                print(\"--- [OCR] No text layer found; attempting OCR fallback ---\")
                ocr_pages_done = 0
                for page in pdf.pages[:3]:  # cap OCR to 3 pages for latency
                    ocr_text = _try_ocr_page(page)
                    if ocr_text:
                        text += ocr_text[:MAX_TEXT_PER_PAGE] + \"\\n\"
                        ocr_pages_done += 1
                        if len(text) >= MAX_TEXT_TOTAL:
                            break
                if ocr_pages_done:
                    print(f\"--- [OCR] Recovered text from {ocr_pages_done} page(s) ---\")
                else:
                    print(\"--- [OCR] No text recovered (tesseract/pytesseract may not be installed) ---\")

            return text[:MAX_TEXT_TOTAL].strip()
    except Exception as e:
        print(f\"PDF extraction error: {e}\")
        return None"""

if "_try_ocr_page" not in content:
    if old_extract in content:
        content = content.replace(old_extract, new_extract)
        print("[OK] Replaced extract_pdf_text with OCR-aware version")
    else:
        print("WARN: Couldn't find the original extract_pdf_text function.")
        print("      Your app.py may have been modified; the OCR patch may not apply cleanly.")
        print("      You can paste the new extract_pdf_text manually from INSTALLATION_NOTES.md.")
else:
    print("[skip] _try_ocr_page already present")

APP_PY.write_text(content, encoding="utf-8")
print(f"\nDone. {APP_PY} patched.")
print("Idempotent — running this script again is a no-op.")
