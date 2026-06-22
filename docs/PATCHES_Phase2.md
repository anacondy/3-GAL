# Phase 2 — Reliability + Defense-in-Depth

**Scope:** Replace broken dependencies, fix the cleanup bug, harden the public API surface, add security headers, ship a single zip.

| # | Finding | File(s) | What this patch does |
|---|---|---|---|
| 1 | P1-03 | `app.py`, `requirements.txt` | Removes `googletrans==4.0.0-rc1` (broken upstream). Translation feature is gone; Hindi PDFs still get detected. |
| 2 | Cleanup bug | `app.py` | `cleanup_old_announcements()` no longer uses the broken `id < threshold` pattern. New logic: `DELETE WHERE id NOT IN (SELECT id ORDER BY sort_date DESC LIMIT 470)`. |
| 3 | P2-04 | `app.py` | New `open_db()` helper enables SQLite WAL mode + busy_timeout=10. All connection sites use it. |
| 4 | P2-05 | `app.py` | PDF text extraction is capped at 5,000 chars per page and 50,000 chars total (was: unbounded). |
| 5 | P2-06 | `app.py` | Search query capped at 500 chars and 32 tokens (was: unbounded — FTS5 could choke). |
| 6 | P2-07 | `generate_static.py` | `html.escape()` applied to `category` and `desc` (was: raw interpolation — latent XSS on GitHub Pages). |
| 7 | P3-01 | `app.py` | Removed dead imports (`threading`, `tempfile`). |
| 8 | P3-02 | `app.py` | Removed unreachable second `return "Notice"` in `categorize_document()`. |
| 9 | P3-04 | `app.py` | New `@app.after_request` sets `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and a CSP. |
| 10 | P3-05 | `app.py` | New `require_xhr()` helper. POST routes (`/api/sync`, `/api/analyze`) now require `X-Requested-With: XMLHttpRequest` header, which browsers won't send cross-origin without a CORS preflight — effectively a CSRF guard. |
| 11 | P3-08 | `.github/workflows/build-release.yml` | `softprops/action-gh-release` pinned to SHA `dec0d2cbf5e635e9b303d6e9bfe36c1915fd0951` (was: `@v1`). |

---

## How to apply

### Step 1: Backup everything you're about to overwrite

```powershell
$dst = "C:\Users\iassh\3-GAL"
Copy-Item "$dst\app.py"             "$dst\app.py.phase1-final.bak"        -Force
Copy-Item "$dst\requirements.txt"    "$dst\requirements.txt.phase1-final.bak" -Force
Copy-Item "$dst\generate_static.py"  "$dst\generate_static.py.prev.bak"   -Force
if (Test-Path "$dst\.github\workflows\build-release.yml") {
    Copy-Item "$dst\.github\workflows\build-release.yml" "$dst\.github\workflows\build-release.yml.prev.bak" -Force
}
```

### Step 2: Extract the zip into your project root

After downloading `3-GAL_phase2.zip` from the workspace, extract it so the file layout matches:

```
C:\Users\iassh\3-GAL\
├── app.py                                # (overwrites)
├── requirements.txt                      # (overwrites)
├── generate_static.py                    # (overwrites)
├── .github\
│   └── workflows\
│       └── build-release.yml             # (overwrites)
└── INSTALLATION_NOTES.md                 # (new — read-only, you can delete after)
```

Easiest way in PowerShell:

```powershell
# After downloading the zip to Downloads
Expand-Archive -Path "C:\Users\iassh\Downloads\3-GAL_phase2.zip" -DestinationPath "C:\Users\iassh\3-GAL\_phase2_tmp" -Force

# Copy each file into place, overwriting
Copy-Item "C:\Users\iassh\3-GAL\_phase2_tmp\app.py"                              "C:\Users\iassh\3-GAL\app.py" -Force
Copy-Item "C:\Users\iassh\3-GAL\_phase2_tmp\requirements.txt"                    "C:\Users\iassh\3-GAL\requirements.txt" -Force
Copy-Item "C:\Users\iassh\3-GAL\_phase2_tmp\generate_static.py"                  "C:\Users\iassh\3-GAL\generate_static.py" -Force
Copy-Item "C:\Users\iassh\3-GAL\_phase2_tmp\.github\workflows\build-release.yml" "C:\Users\iassh\3-GAL\.github\workflows\build-release.yml" -Force

# Clean up the staging folder
Remove-Item -Recurse -Force "C:\Users\iassh\3-GAL\_phase2_tmp"
```

### Step 3: Install new dep / remove old one

```powershell
cd C:\Users\iassh\3-GAL
.\.venv\Scripts\Activate.ps1
pip uninstall -y googletrans
pip install -U -r requirements.txt
```

### Step 4: Restart Flask

```powershell
# Ctrl+C the running app first
python app.py
```

### Step 5: Verify

| Check | Expected |
|---|---|
| First boot | Should NOT print `--- [MIGRATE] Backfilled sort_date ... ---` (already done in hotfix). |
| First sync | `--- [CLEANUP] Deleted 30 old announcements (kept latest 470) ---` (this was the bug — it now correctly reports the actual number deleted). |
| Final count | `TOTAL ANNOUNCEMENTS IN DB: 470 (max: 470)` — **exactly 470**, not 500. ✅ (cleanup bug fixed) |
| Browser DevTools → Network → `/` response headers | New headers present: `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, `Permissions-Policy`. |
| Click INTEL button | Either works (AI summary shown) OR shows inline message "PDF has no extractable text (it may be a scanned image)..." in the loading area (no more blocking `alert()`). |
| POST `/api/sync` without `X-Requested-With` header | Returns `403` with `{"error": "X-Requested-With header required"}`. |
| POST `/api/sync` with `X-Requested-With: XMLHttpRequest` | Returns `200`. |
| Test from PowerShell: `Invoke-WebRequest -Method POST http://localhost:5007/api/sync -UseBasicParsing -Headers @{"X-Requested-With"="XMLHttpRequest"}` | Should return `200`. |

### Step 6 (rollback if anything goes wrong)

```powershell
$dst = "C:\Users\iassh\3-GAL"
Copy-Item "$dst\app.py.phase1-final.bak"                     "$dst\app.py" -Force
Copy-Item "$dst\requirements.txt.phase1-final.bak"          "$dst\requirements.txt" -Force
Copy-Item "$dst\generate_static.py.prev.bak"                "$dst\generate_static.py" -Force
Copy-Item "$dst\.github\workflows\build-release.yml.prev.bak" "$dst\.github\workflows\build-release.yml" -Force
```

---

## ⚠️ Important: about the CSRF guard

The `X-Requested-With` requirement means **the frontend's existing `fetch()` calls need to add this header**. The current `templates/index.html` uses bare `fetch('/api/sync', {method: 'POST'})` and `fetch('/api/analyze', {method: 'POST'})`. After this patch, those calls will return 403.

**You will need to update `templates/index.html`** to add the header. This will be Phase 3 (the next batch). For now, your app will start but **POST buttons (Sync, INTEL analyze) will stop working** until you apply the frontend update.

To make Phase 2 work end-to-end right now, run a one-line PowerShell replace on `templates/index.html`:

```powershell
$path = "C:\Users\iassh\3-GAL\templates\index.html"
Copy-Item $path "$path.phase2-bak" -Force
(Get-Content -Raw $path) `
    -replace "fetch\('/api/sync', \{\s*method: 'POST'\s*\}\)",
              "fetch('/api/sync', { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' } })" `
    | Set-Content $path -NoNewline
(Get-Content -Raw $path) `
    -replace "fetch\('/api/analyze', \{\s*method: 'POST',\s*headers: \{ 'Content-Type': 'application/json' \},\s*body: JSON\.stringify\(\{ url \}\)\s*\}\)",
              "fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, body: JSON.stringify({ url }) })" `
    | Set-Content $path -NoNewline

Select-String -Path $path -Pattern "X-Requested-With"
```

Expected: two lines, one for each fetch call.

---

## What this does NOT do (still queued for Phase 3+)

- Pin GitHub Actions `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, etc. (only `softprops` was pinned for now to keep this patch small)
- Move to gunicorn + reverse proxy in production (vs. `flask run` for dev)
- OCR fallback for image-only PDFs (would add `tesseract` / `pytesseract`)
- A real admin panel (if/when one is built)

Say **"phase 3"** when ready.
