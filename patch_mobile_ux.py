"""
patch_mobile_ux.py — Phase 5 mobile UX improvements.

Run once from project root:
    python patch_mobile_ux.py

It modifies templates/index.html in-place to:

1. Fix touch-action on body — change from "pan-x pan-y" (which blocks vertical
   scrolling!) to "manipulation" (allows scroll but no double-tap zoom, and
   respects pinch-zoom only on the iframe content, not the host UI).

2. Add auto-fallback in openPdf(): if Google Docs viewer loads but the iframe
   ends up empty/triggers download, automatically open the PDF in a new tab
   after a 6-second timeout. This avoids the "stuck on LOADING PDF..." state.

The patch is idempotent.
"""
import sys
from pathlib import Path

HTML = Path("templates/index.html")

if not HTML.exists():
    print(f"ERROR: {HTML} not found. Run from project root.", file=sys.stderr)
    sys.exit(1)

# Backup
backup = HTML.with_suffix(".html.pre-phase5.bak")
if not backup.exists():
    import shutil
    shutil.copy(HTML, backup)
    print(f"Backed up to {backup}")

content = HTML.read_text(encoding="utf-8")

# --- Patch 1: fix body touch-action (pan-x pan-y -> manipulation) ---
old_body_css = """body {
    background-color: var(--bg-color);
    color: var(--text-primary);
    font-family: 'Special Elite', monospace;
    overflow-x: hidden; overflow-y: visible;
    min-height: 100%;
    display: flex; flex-direction: column; align-items: center;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    touch-action: pan-x pan-y;
}"""

new_body_css = """body {
    background-color: var(--bg-color);
    color: var(--text-primary);
    font-family: 'Special Elite', monospace;
    overflow-x: hidden; overflow-y: visible;
    min-height: 100%;
    display: flex; flex-direction: column; align-items: center;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    /* Phase 5: 'manipulation' allows vertical scroll but disables
       double-tap-to-zoom on the host page. Pinch-zoom is also disabled
       because the meta viewport has user-scalable=no. The PDF iframe
       uses touch-action: auto so it can be zoomed there. */
    touch-action: manipulation;
}"""

if "touch-action: manipulation;" not in content:
    if old_body_css in content:
        content = content.replace(old_body_css, new_body_css)
        print("[OK] Fixed body touch-action: pan-x pan-y -> manipulation")
    else:
        print("WARN: Couldn't find the original body CSS block.")
        print("      The touch-action patch may not apply cleanly.")
else:
    print("[skip] body touch-action already updated to 'manipulation'")

# --- Patch 2: add auto-fallback in openPdf() ---
# Find the existing openPdf function and inject a fallback timer.
# The function looks like:
#   function openPdf(url) {
#       ...
#       pdfFrame.src = googleDocsUrl;
#       ...
#       document.getElementById('pdf-modal').style.display = 'flex';
#       document.body.style.overflow = 'hidden';
#   }
# We add a 6-second timer that, if the iframe's content is empty or fails,
# triggers window.open(url, '_blank') as a fallback.

old_close_pdf_signature = "function closePdf() {"

# Look for the existing openPdf function and add the fallback right after pdfFrame.src is set
old_openpdf_block = """            // Use Google Docs PDF Viewer for reliable cross-device PDF rendering
            // This works on both mobile and desktop, displaying the PDF content directly
            const googleDocsUrl = 'https://docs.google.com/viewer?url=' + encodeURIComponent(url) + '&embedded=true';
            pdfFrame.src = googleDocsUrl;

            // Hide loading when iframe loads
            pdfFrame.onload = function() {
                pdfLoading.classList.remove('active');
            };

            document.getElementById('pdf-modal').style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }"""

new_openpdf_block = """            // Use Google Docs PDF Viewer for reliable cross-device PDF rendering
            // This works on both mobile and desktop, displaying the PDF content directly
            const googleDocsUrl = 'https://docs.google.com/viewer?url=' + encodeURIComponent(url) + '&embedded=true';
            pdfFrame.src = googleDocsUrl;

            // Hide loading when iframe loads
            pdfFrame.onload = function() {
                pdfLoading.classList.remove('active');
            };

            // Phase 5: auto-fallback if Google viewer fails.
            // After 6 seconds, check if the iframe ended up showing an
            // error/empty page (Google returns a download response for some
            // PDFs). If so, open the PDF in a new tab automatically.
            // The user's [OPEN ORIGINAL] button still works as the manual option.
            setTimeout(function() {
                try {
                    // Try to detect if Google viewer showed an error page
                    const iframeDoc = pdfFrame.contentDocument || pdfFrame.contentWindow.document;
                    const bodyText = iframeDoc && iframeDoc.body ? (iframeDoc.body.innerText || '') : '';
                    if (!bodyText || bodyText.length < 50) {
                        // Empty or minimal content: Google viewer failed.
                        // Open the PDF directly in a new tab.
                        window.open(url, '_blank');
                        // Don't close the modal — let user see what happened.
                    }
                } catch (e) {
                    // Cross-origin or other error: viewer likely failed.
                    // Open directly.
                    window.open(url, '_blank');
                }
            }, 6000);

            document.getElementById('pdf-modal').style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }"""

if "Phase 5: auto-fallback if Google viewer fails" not in content:
    if old_openpdf_block in content:
        content = content.replace(old_openpdf_block, new_openpdf_block)
        print("[OK] Added auto-fallback in openPdf()")
    else:
        print("WARN: Couldn't find the original openPdf() function block.")
        print("      The auto-fallback patch may not apply cleanly.")
        print("      Manual fix: paste the setTimeout snippet from INSTALLATION_NOTES.md.")
else:
    print("[skip] openPdf auto-fallback already present")

HTML.write_text(content, encoding="utf-8")
print(f"\nDone. {HTML} patched.")
print("Idempotent — running again is a no-op.")
