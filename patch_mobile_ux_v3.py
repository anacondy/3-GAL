"""
patch_mobile_ux_v3.py — Phase 5 mobile + desktop UX improvements.

Adds THREE things to templates/index.html (v3 is idempotent on the first two,
adds the new ones):

1. (v2) body touch-action: pan-x pan-y -> manipulation
2. (v3 NEW) prevent desktop zoom:
   - Ctrl+scroll wheel
   - Ctrl+Plus/Minus/Zero keyboard
   - Cmd+Plus/Minus/Zero on Mac (metaKey)
   Note: this is controversial UX. Some users expect browser zoom. If
   you don't like it, edit this file and remove the addEventListener block.
3. (v3 NEW) click outside the PDF modal to close it.

Run once from project root:
    python patch_mobile_ux_v3.py
"""
import sys
from pathlib import Path
import shutil

HTML = Path("templates/index.html")

if not HTML.exists():
    print(f"ERROR: {HTML} not found. Run from project root.", file=sys.stderr)
    sys.exit(1)

backup = HTML.with_suffix(".html.pre-phase5.bak")
if not backup.exists():
    shutil.copy(HTML, backup)
    print(f"Backed up to {backup}")

content = HTML.read_text(encoding="utf-8")
original = content

# --- Patch 1: touch-action (from v2) ---
old_touch = "    touch-action: pan-x pan-y;"
new_touch = "    touch-action: manipulation;  /* Phase 5: was 'pan-x pan-y' which blocked vertical scroll */"
if "touch-action: manipulation;" in content:
    print("[skip] Patch 1: body touch-action already updated")
elif old_touch in content:
    content = content.replace(old_touch, new_touch)
    print("[OK] Patch 1: Fixed body touch-action")
else:
    print("[skip] Patch 1: could not find old touch-action line (may already be patched)")

# --- Patch 2: prevent desktop zoom (Ctrl+scroll, Ctrl+Plus/Minus/Zero) ---
# Insert a script tag in the head. We'll add it right before </head>.
zoom_block_js = """    <script>
    /* Phase 5: prevent desktop zoom (Ctrl+scroll, Ctrl+Plus/Minus/Zero).
       On mobile the meta viewport 'user-scalable=no' handles this.
       On desktop, browser-native shortcuts need to be captured in JS. */
    (function() {
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && ['+', '-', '0', '='].indexOf(e.key) !== -1) {
                e.preventDefault();
            }
        }, { passive: false });
        document.addEventListener('wheel', function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
            }
        }, { passive: false });
    })();
    </script>
</head>"""

if "Phase 5: prevent desktop zoom" in content:
    print("[skip] Patch 2: desktop zoom prevention already present")
elif "</head>" in content:
    content = content.replace("</head>", zoom_block_js)
    print("[OK] Patch 2: Added desktop zoom prevention")
else:
    print("[skip] Patch 2: could not find </head> tag")

# --- Patch 3: click outside PDF modal to close ---
# Find the <div id="pdf-modal"> and add an onclick handler that closes if clicked directly.
old_modal_open = '<div id="pdf-modal">'
new_modal_open = '<div id="pdf-modal" onclick="if(event.target===this) closePdf()">'

if "if(event.target===this) closePdf()" in content:
    print("[skip] Patch 3: click-outside-to-close already present")
elif old_modal_open in content:
    content = content.replace(old_modal_open, new_modal_open)
    print("[OK] Patch 3: Added click-outside-to-close on PDF modal")
else:
    print("[skip] Patch 3: could not find <div id=\"pdf-modal\"> tag")

# Save
HTML.write_text(content, encoding="utf-8")

if content != original:
    print(f"\nDone. {HTML} patched ({sum(1 for a,b in zip(original,content) if a!=b)} differences).")
else:
    print(f"\nNo changes were applied to {HTML}. Manual edit may be needed.")

print("Idempotent — running again is a no-op.")
