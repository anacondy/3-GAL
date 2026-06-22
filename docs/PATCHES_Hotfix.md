# Hotfix Patch — Sort + PDF Viewer

**Scope:** Two non-security bugs you reported:

| # | Bug | Fix |
|---|---|---|
| H-1 | Announcements sorted by *insert order*, not by *announcement date* | Add a `sort_date` column (YYYY-MM-DD, lexicographically sortable), populate at INSERT, migrate existing rows on startup, and change every `ORDER BY id DESC` to `ORDER BY sort_date DESC, id DESC`. |
| H-2 | PDF iframe triggers "Save As" dialog instead of rendering inline | `templates/index.html` `openPdf()` always uses Google Docs Viewer (was: only on mobile). |

These are quality-of-life fixes, not security — they're filed separately from the Phase 1 security patch so they're easy to roll back if needed.

---

## What to download

| File | Replace this |
|---|---|
| `patches/hotfix/app.py` | `C:\Users\iassh\3-GAL\app.py` (overwrites the Phase 1 version) |

For the PDF viewer fix, you do **not** need to download a new `templates/index.html`. Instead, run a one-line PowerShell `-replace` against the existing file (full instructions below). This avoids shipping a 4,700-line HTML file just to change one line.

---

## How to apply

### Step 1: Backup + drop the new `app.py`

```powershell
Copy-Item C:\Users\iassh\3-GAL\app.py C:\Users\iassh\3-GAL\app.py.backup-hotfix
Copy-Item -Path "C:\Users\iassh\Downloads\app (2).py" -Destination "C:\Users\iassh\3-GAL\app.py" -Force
```

> The new file may download as `app (2).py` (or similar) due to name collisions. Adjust the path above if yours has a different number.

### Step 2: Apply the one-line PDF viewer fix to `templates/index.html`

```powershell
$path = "C:\Users\iassh\3-GAL\templates\index.html"
Copy-Item $path "$path.backup-hotfix" -Force
(Get-Content -Raw $path) `
    -replace "const finalUrl = isMobile \? 'https://docs\.google\.com/viewer\?url=' \+ encodeURIComponent\(url\) \+ '&embedded=true' : url;",
              "const finalUrl = 'https://docs.google.com/viewer?url=' + encodeURIComponent(url) + '&embedded=true';" `
    | Set-Content $path -NoNewline

# Sanity check: confirm the change actually took effect
Select-String -Path $path -Pattern "const finalUrl ="
```

Expected output: one line containing `const finalUrl = 'https://docs.google.com/viewer?url='`.

### Step 3: Restart Flask

In your existing `python app.py` terminal, hit `Ctrl+C` and re-run:

```powershell
cd C:\Users\iassh\3-GAL
.\.venv\Scripts\Activate.ps1
python app.py
```

Watch for `--- [SYSTEM] SYNC COMPLETE. ---` and then check the DB migration logged in your terminal — the first run will quietly backfill `sort_date` for existing rows.

### Step 4: Verify

| Check | How |
|---|---|
| **Sort is now by date** | Open `http://localhost:5007/`. The first card should be a **22-06-2026** entry (Anti Ragging Squad / Committee / Vision 2050), NOT a Nov-2025 one. |
| **Sort is also applied in search** | Type `exam` in the search box. Results should be ordered by date desc, not by id desc. |
| **PDF viewer always uses Google Docs** | Click any card. The modal should render the PDF inline via `docs.google.com/viewer` — no "Save As" dialog. |
| **No regressions** | INTEL button still works. Try clicking it on a card; pdfplumber will analyze the PDF and show the summary panel. |

### Step 5 (if anything goes wrong): restore from backups

```powershell
Copy-Item C:\Users\iassh\3-GAL\app.py.backup-hotfix C:\Users\iassh\3-GAL\app.py -Force
Copy-Item "C:\Users\iassh\3-GAL\templates\index.html.backup-hotfix" "C:\Users\iassh\3-GAL\templates\index.html" -Force
```

---

## What changed in `app.py` (line-by-line)

| Region | Before (Phase 1) | After (Hotfix) |
|---|---|---|
| `init_db()` | Schema had 7 columns | Adds `sort_date TEXT` column; ALTER TABLE for existing DBs; one-time UPDATE backfill for existing rows |
| New helper | (none) | `normalize_date_for_sort()` — converts DD-MM-YYYY → YYYY-MM-DD |
| `save_announcement()` | INSERT with 6 placeholders | Now also computes & writes `sort_date` |
| `/` route | `ORDER BY id DESC LIMIT 100` | `ORDER BY sort_date DESC, id DESC LIMIT 100` |
| `/api/search` LIKE fallback | `ORDER BY id DESC LIMIT 100` (3 places) | `ORDER BY sort_date DESC, id DESC LIMIT 100` (3 places) |
| `/api/data` | `ORDER BY id DESC LIMIT ?` (2 places) | `ORDER BY sort_date DESC, id DESC LIMIT ?` (2 places) |

The `comprehensive_search()` results already come back in whatever order the underlying queries used, so the same fix at the SQL level propagates everywhere.

---

## Why this is safe

- The new `sort_date` column is purely additive. No existing rows are deleted or modified — only the new column is populated.
- If `normalize_date_for_sort()` fails (e.g., a row has an unexpected date format), it returns `""` and that row sorts to the end. No crashes.
- The DB migration runs on every startup but the UPDATE only affects rows with `sort_date IS NULL` — it's idempotent and fast.
- Rate limits, the 25 MB cap, and the `Alvido` removal from Phase 1 are all preserved unchanged.

---

## What this does NOT do (still queued for Phase 2+)

- Replace `googletrans==4.0.0-rc1` (P1-03)
- SQLite WAL mode (P2-04)
- Query length caps (P2-06)
- `html.escape()` in `generate_static.py` (P2-07)
- Security headers, CSRF trick, GH-Actions SHA pinning (Phase 3)
- Dead-code cleanup (Phase 4)

Say **"phase 2"** when ready and I'll generate that batch.
