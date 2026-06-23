"""
patch_mobile_ux_v2.py — Phase 5 mobile UX improvements.

Simpler, more robust version. Uses single-line matching + targeted inserts
instead of multi-line regex.

Run once from project root:
    python patch_mobile_ux_v2.py

Modifies templates/index.html to:
1. Fix body touch-action: pan-x pan-y -> manipulation
2. Add auto-fallback in openPdf() (open PDF in new tab if Google viewer fails)
"""
import sys
from pathlib import Path
import shutil

HTML = Path("templates/index.html")

if not HTML.exists():
    print(f"ERROR: {HTML} not found. Run from project root.", file=sys.stderr)
    sys.exit(1)

# Backup
backup = HTML.with_suffix(".html.pre-phase5.bak")
if not backup.exists():
    shutil.copy(HTML, backup)
    print(f"Backed up to {backup}")

content = HTML.read_text(encoding="utf-8")
original_content = content

# --- Patch 1: fix touch-action on body ---
# Just find the line and replace it. Single-line matching is more robust.
old_touch = "    touch-action: pan-x pan-y;"
new_touch = "    touch-action: manipulation;  /* Phase 5: was 'pan-x pan-y' which blocked vertical scroll */"

if "touch-action: manipulation;" in content:
    print("[skip] body touch-action already updated")
elif old_touch in content:
    content = content.replace(old_touch, new_touch)
    print("[OK] Fixed body touch-action: pan-x pan-y -> manipulation")
else:
    print("WARN: Couldn't find 'touch-action: pan-x pan-y;' line.")
    print("      Searching for any 'touch-action:' line...")
    import re
    matches = re.findall(r"touch-action:\s*[^;]+;", content)
    print(f"      Found these instead: {matches}")
    print("      The body CSS may have a different format than expected.")

# --- Patch 2: add auto-fallback timer in openPdf() ---
# Find the line that sets pdfFrame.src and inject a setTimeout right after pdfFrame.onload block.
# We use a marker that should appear in any reasonable version of the function.

# Find the line that sets pdfFrame.src = googleDocsUrl;
src_line = "            pdfFrame.src = googleDocsUrl;"
if "Phase 5: auto-fallback if Google viewer fails" in content:
    print("[skip] auto-fallback already present")
elif src_line in content:
    # Insert the fallback setTimeout right BEFORE document.getElementById('pdf-modal').style.display
    auto_fallback_js = """            // Phase 5: if Google Docs viewer fails (returns a download instead of HTML preview),
            // auto-open the PDF in a new tab after 6s. The [OPEN ORIGINAL] button still works as the manual option.
            setTimeout(function() {
                try {
                    var iframeDoc = pdfFrame.contentDocument || (pdfFrame.contentWindow && pdfFrame.contentWindow.document);
                    var bodyText = (iframeDoc && iframeDoc.body) ? (iframeDoc.body.innerText || iframeDoc.body.textContent || '') : '';
                    if (!bodyText || bodyText.length < 30) {
                        window.open(url, '_blank');
                    }
                } catch (e) {
                    // Cross-origin or other error -> just open directly.
                    window.open(url, '_blank');
                }
            }, 6000);

"""
    # Find the line "document.getElementById('pdf-modal').style.display = 'flex';"
    # and inject the setTimeout before it.
    modal_line = "            document.getElementById('pdf-modal').style.display = 'flex';"
    if modal_line in content:
        content = content.replace(modal_line, auto_fallback_js + modal_line)
        print("[OK] Added auto-fallback in openPdf()")
    else:
        # Fallback: insert right after pdfFrame.src line
        content = content.replace(src_line, src_line + "\n" + auto_fallback_js)
        print("[OK] Added auto-fallback (fallback position)")
else:
    print("WARN: Couldn't find 'pdfFrame.src = googleDocsUrl;' line in openPdf().")
    print("      Manual fix: paste the setTimeout snippet from INSTALLATION_NOTES.md.")

# Save
HTML.write_text(content, encoding="utf-8")

if content != original_content:
    print(f"\nDone. {HTML} patched.")
else:
    print(f"\nNo changes were applied to {HTML}. Manual edit may be needed.")

print("Idempotent — running again is a no-op.")
