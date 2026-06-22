# Phase 1 Patches — "Stop the Bleeding"

**Scope:** The 4 highest-impact fixes that take ~1 hour and prevent immediate abuse / data loss.

| # | Finding | File(s) | What this patch does |
|---|---|---|---|
| 1 | P1-01 | `app.py` | Adds 25 MB hard cap + streaming download in `download_pdf()` so a single huge response can't OOM the worker. |
| 2 | P1-01 / P1-02 | `app.py`, `requirements.txt` | Adds `flask-limiter` and rate-limits `/api/sync` (1 / 5 min) and `/api/analyze` (10 / min). |
| 3 | P2-01 | `app.py`, `README.md` | Deletes the dead "Alvido" admin-upload branch in `/api/search` and removes the matching "Admin Access" section from `README.md`. |
| 4 | P2-02 | `app.py` | Removes the `FLASK_DEBUG` env-var knob; debug is hard-pinned to `False`. |

---

## How to apply

1. **Back up your current project** (just in case):
   ```powershell
   Copy-Item -Recurse C:\Users\iassh\3-GAL C:\Users\iassh\3-GAL.backup-phase1
   ```

2. **Drop the three files into `C:\Users\iassh\3-GAL\`, overwriting the originals:**
   - `app.py` → replaces `C:\Users\iassh\3-GAL\app.py`
   - `requirements.txt` → replaces `C:\Users\iassh\3-GAL\requirements.txt`
   - `README.md` → replaces `C:\Users\iassh\3-GAL\README.md`

3. **Activate your venv and install the new dependency:**
   ```powershell
   cd C:\Users\iassh\3-GAL
   .\.venv\Scripts\Activate.ps1
   pip install -U flask-limiter>=3.5.0
   ```

4. **Smoke test:**
   ```powershell
   python app.py
   ```
   Open `http://localhost:5007/` — should render normally.
   Hit `POST /api/sync` repeatedly in a loop; you should see HTTP 429 after the first one within 5 minutes:
   ```powershell
   1..10 | ForEach-Object { Invoke-WebRequest -Method POST http://localhost:5007/api/sync -UseBasicParsing | Select-Object -ExpandProperty StatusCode }
   ```

5. **If something is wrong**, restore from backup:
   ```powershell
   Remove-Item -Recurse C:\Users\iassh\3-GAL
   Rename-Item C:\Users\iassh\3-GAL.backup-phase1 C:\Users\iassh\3-GAL
   ```

---

## What changed (line-by-line, for your review)

### `app.py`

| Region | Before | After |
|---|---|---|
| Imports | (unchanged) | + `from flask_limiter import Limiter` |
| Constants | (unchanged) | + `MAX_PDF_BYTES = 25 * 1024 * 1024` |
| App setup | `app = Flask(__name__)` | + `limiter = Limiter(get_remote_address, app=app, default_limits=["120 per minute"])` |
| `download_pdf()` | `requests.get(...stream=True)` then `response.content` | streams in 64 KB chunks, bails at `MAX_PDF_BYTES` |
| `/api/sync` route | `@app.route(...)` | `@app.route(...)` + `@limiter.limit("1 per 5 minutes")` |
| `/api/analyze` route | `@app.route(...)` | `@app.route(...)` + `@limiter.limit("10 per minute")` |
| `/api/search` route | had the `Alvido` `print()` block | block removed entirely |
| `__main__` block | `debug_mode = os.environ.get(...)` | hard-pinned `debug=False` |

### `requirements.txt`

| Before | After |
|---|---|
| (no rate limiter) | + `flask-limiter>=3.5.0` |

### `README.md`

| Before | After |
|---|---|
| "### Admin Access" section with `Alvido` | Section removed entirely |

---

## What this does NOT do (Phase 2+ territory)

These are intentionally **out of scope** for Phase 1 — we'll do them in the next batches:

- Replacing `googletrans==4.0.0-rc1` (P1-03) — Phase 2
- SQLite WAL mode + query length caps (P2-04, P2-06) — Phase 2
- `html.escape()` in `generate_static.py` (P2-07) — Phase 2
- Security headers, CSRF trick, GH-Actions SHA pinning — Phase 3
- Dead imports / unreachable code removal — Phase 4

Say **"phase 2"** when ready and I'll generate that batch.
