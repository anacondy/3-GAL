# STATUS (2026-06-23): Every finding in this audit has been remediated in the current main branch. See docs/FINAL_REPORT.md for the per-commit fix map.

# 3-GAL â€” Security & Robustness Audit Report

**Target:** `3-GAL` â€” Real-time Galgotias University Examination Announcements scraper (Flask + static-site generator)
**Repo files reviewed:** `app.py`, `generate_static.py`, `cinema-scanner-/src/App.jsx`, `templates/index.html`, `static_site/index.html`, `.github/workflows/*.yml`, `requirements.txt`, `README.md`, `docs/API.md`, `docs/WIKI.md`
**Audit type:** Black-box style senior code review â€” vulnerabilities, error handling, hardening gaps, attack-surface enumeration
**Auditor mindset:** "What would a bored teenager with `curl` and 2 hours do to this app?"

---

## 1. Executive Summary

The project is a **read-only public-information aggregator** of public PDF announcements. There is no multi-tenant data, no PII, no payment flow, and no auth in production. Most of the realistic risk is therefore:

1. **Abuse of the public, unauthenticated HTTP surface** (DoS, scraping amplification against the upstream university site, SSRF via the `/api/analyze` endpoint).
2. **Reliability/availability** bugs that will manifest in production under load.
3. **Insecure-by-default dependencies** (`googletrans==4.0.0-rc1`, hard-pinned, known-broken).
4. **A "secret" that isn't a secret** (`Alvido` written in plaintext in `README.md`) â€” security theater, not a vulnerability.

No SQL injection, no XSS, and the SSRF allowlist for the analyzer endpoint is correctly implemented. Those are the wins.

**Headline numbers:**

| Severity | Count |
|----------|-------|
| ðŸ”´ P0 â€” Critical / RCE-class | 0 |
| ðŸŸ  P1 â€” High | 3 |
| ðŸŸ¡ P2 â€” Medium | 7 |
| ðŸŸ¢ P3 â€” Low | 8 |
| âšª P4 â€” Informational / Hygiene | 6 |

> **Overall posture:** Safe for personal/demo use. **Not safe to expose to the public internet** without rate-limiting, an actual reverse proxy with WAF, and removing the `FLASK_DEBUG` environment knob.

---

## 2. Threat Model

| Asset | Threat | Realistic? |
|---|---|---|
| Upstream Galgotias site | DoS via scraping amplification from `/api/sync` | High â€” endpoint is unauthenticated |
| Server CPU/RAM | DoS via repeated `/api/analyze` calls downloading arbitrary PDFs | High |
| Server disk | DB bloat via `/api/sync` spam | Low â€” bounded by `MAX_ANNOUNCEMENTS=470` |
| Internal services | SSRF via `/api/analyze` | Low â€” allowlist is correct |
| Users visiting the site | XSS via reflected titles | Very Low â€” Jinja2 auto-escapes; static-site escaping is partial |
| Admin panel | Bypass via leaked `Alvido` password | None â€” no admin panel actually exists |
| Browser users of `cinema-scanner-` | Gemini API key theft via DevTools / referer | High â€” key is shipped in the JS bundle |

---

## 3. Findings (ranked)

### ðŸ”´ P0 â€” Critical

*None found.* The codebase does not contain a classic RCE, SQLi, or pre-auth data-exposure chain.

---

### ðŸŸ  P1 â€” High

#### P1-01 â€” Public, unauthenticated `/api/analyze` accepts arbitrary attacker-controlled URLs â†’ SSRF amplification & outbound DoS

- **Location:** `app.py` â€” `@app.route('/api/analyze', methods=['POST'])`
- **What it does:** Any internet user can POST `{"url": "https://anything/"}` and the server will fetch it.
- **What stops it being a classic SSRF:** `download_pdf()` calls `is_allowed_url()`, which correctly checks `parsed.scheme in ('http','https')` AND that `host` is in `ALLOWED_PDF_DOMAINS` (`galgotiasuniversity.edu.in` / `www.galgotiasuniversity.edu.in`) with `endswith('.galgotiasuniversity.edu.in')` defense â€” I tested the obvious bypass shapes (`https://x@evil/`, `https://galgotiasuniversity.edu.in.evil/`, ports, punycode variants) and they all correctly fail.
- **The real problem:** This endpoint is still a **paid egress / abuse primitive**. An attacker can:
  1. Trigger `response.content` to be loaded fully into memory (`io.BytesIO(content)` in `download_pdf`). There's **no `Content-Length` cap and no streaming limit**. A single 500 MB response will OOM the worker.
  2. Trigger many concurrent requests â†’ the 4-worker `ThreadPoolExecutor` queues them, request handler threads pile up.
  3. If the upstream Galgotias site ever hosts attacker-controllable content (e.g., user-uploaded PDFs), this becomes a server-side request **abuse chain**, not just SSRF.
- **Impact:** Outbound bandwidth burn, memory exhaustion, possible IP reputation damage if abused from a shared host.
- **Severity justification:** Pre-auth, no rate limit, no size cap. High.

**Fix sketch:**
```python
# 1. Cap download size (hard requirement)
MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB
response = requests.get(url, headers=HEADERS, timeout=PDF_DOWNLOAD_TIMEOUT, stream=True)
response.raise_for_status()
cl = response.headers.get("Content-Length")
if cl and int(cl) > MAX_PDF_BYTES:
    return None
buf = io.BytesIO()
for chunk in response.iter_content(chunk_size=64 * 1024):
    if buf.tell() + len(chunk) > MAX_PDF_BYTES:
        return None
    buf.write(chunk)

# 2. Rate-limit the route
from flask_limiter import Limiter
limiter = Limiter(get_remote_address, app=app, default_limits=["60/minute"])

@app.route('/api/analyze', methods=['POST'])
@limiter.limit("10 per minute")
def analyze_pdf(): ...
```

---

#### P1-02 â€” `/api/sync` is an unauthenticated, public "make a request to galgotiasuniversity.edu.in" button

- **Location:** `app.py` â€” `@app.route('/api/sync', methods=['POST'])`
- **What it does:** Anyone, anywhere, can POST and the server will issue a live `requests.get(EXAM_URL, ...)` against the university website. No auth, no rate limit, no CSRF protection.
- **Impact:**
  - **Scraping amplification / DDoS-as-a-service** against a third-party university site from your infrastructure. This is the kind of thing that gets a project taken offline by abuse complaints.
  - Combined with `analyze_pdf_async`, each sync also queues up to **20 background PDF downloads** (4 workers), consuming outbound bandwidth and CPU.
- **Severity justification:** Pre-auth abuse vector with real third-party collateral damage.

**Fix sketch:**
- Require a shared secret (`X-Sync-Token` header) read from env for the sync endpoint, OR restrict it to admin-only via basic auth.
- Add `@limiter.limit("1 per 5 minutes")` (you only sync every few minutes anyway in production).
- Switch to `request.is_json` only, no GET.

---

#### P1-03 â€” `googletrans==4.0.0-rc1` is pinned to a 4-year-old pre-release that no longer works

- **Location:** `requirements.txt` line: `googletrans==4.0.0-rc1`
- **Why this is in P1 and not P4:** This is not "merely outdated." The `4.0.0-rc1` line uses an **undocumented Google Translate web endpoint** that Google has been throttling/banning. In practice, this library:
  - Throws `AttributeError: 'NoneType' object has no attribute 'group'` against any non-trivial Hindi text.
  - Frequently returns 429s or empty strings from `translator.translate()`.
  - Has had **multiple supply-chain incidents** (typosquatted forks, malware-laced clones on PyPI masquerading as `googletrans`).
  - May also be flagging your IP for abuse if it leaks a Google internal header.
- The `Translator()` is also instantiated **at module import time** (`translator = Translator()` in `app.py`), so an ImportError or upstream outage will break the entire Flask app boot.
- **Severity justification:** Reliability 0, plus latent supply-chain exposure. Fix the pin to a real, supported package or remove the feature.

**Fix sketch:**
```python
# Option A: drop the dependency and use the official Google Cloud Translate API
# Option B: drop it entirely and ship a "Hindi detected â€” no translation available" notice
# Option C: pin to deep-translator (actively maintained) instead
# requirements.txt:
deep-translator>=1.11.4   # instead of googletrans==4.0.0-rc1
```

---

### ðŸŸ¡ P2 â€” Medium

#### P2-01 â€” `Alvido` "admin password" is in plaintext in the README â€” security theater

- **Locations:**
  - `README.md` (public, in the repo): *"Type `upload` in the search box and enter `Alvido` for admin access."*
  - `app.py` `/api/search`: prints `"[AUTH] Admin upload requested. Waiting for 'Alvido' credential."` when `q == "upload"`.
  - `docs/API.md`: *"Admin functions use client-side credential check."*
- **The problem:**
  - There is **no upload endpoint** anywhere in the codebase. The README and the API doc describe a feature that **does not exist**.
  - There is **no client-side check** either â€” searching the entire bundle for "Alvido" returns matches only in the README and the `print()` statement. No JS prompt, no modal, no submit handler.
  - Anyone reading the repo knows the password â€” but there is nothing for the password to gate.
- **Impact:** None today (no protected asset). **High future risk:** when someone finally wires up `/api/upload`, they'll think "the README says Alvido, that's secure, ship it" â€” and it'll be a real RCE pivot.
- **Severity justification:** Not exploitable *now*, but the pattern is a foot-gun. Remove it.

**Fix sketch:**
- Delete the `if q.lower() == "upload"` block in `/api/search`.
- Delete the "Admin Access" section in `README.md`.
- If/when an admin panel is added, require a real per-user auth (e.g., HTTP Basic with a bcrypt-hashed password from env, or signed session cookies). Never ship a "secret" in source control.

---

#### P2-02 â€” `FLASK_DEBUG` toggle exposes Werkzeug interactive debugger if misconfigured

- **Location:** `app.py` last block:
  ```python
  debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
  app.run(debug=debug_mode, port=port, threaded=True)
  ```
- **Why this matters:** If anyone ever sets `FLASK_DEBUG=true` (a `.env` file, a Docker misconfig, a PaaS UI toggle, a "let me debug this in prod" moment), `app.run(debug=True)` enables the Werkzeug debugger, which provides an **arbitrary-Python-execution console** to anyone who can reach the server. This is a textbook critical-RCE primitive.
- **The default is safe** (`'false'`). But **the variable exists**, which is the issue. Don't even give yourself the option.
- **Severity justification:** Conditional RCE if misconfigured. Common PaaS footgun.

**Fix sketch:**
```python
# Hard-disable the debugger. Period.
app.run(debug=False, host='127.0.0.1', port=port, threaded=True)
# If you need a public-facing deploy, put gunicorn + nginx in front (your README already shows this).
```

Also remove the `FLASK_DEBUG` env-var plumbing entirely.

---

#### P2-03 â€” `executor.submit(...)` returns unawaited `Future`s; thread-pool queue has no upper bound

- **Location:** `app.py`:
  ```python
  executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
  ...
  def analyze_pdf_async(url):
      def task(): ...
      executor.submit(task)
  ```
- **What this means:** Every call to `/api/analyze` or every `/api/sync` that finds new URLs fires a `submit()` whose `Future` is **discarded**. No error propagation, no backpressure, no shutdown handling beyond `executor.shutdown(wait=False)` at exit.
- **Impact:**
  - If 1000 syncs are triggered in 10 seconds, you have ~5000 PDF-parse tasks queued in a 4-worker pool. Memory grows until OOM.
  - Errors inside `task()` are swallowed by the bare `except Exception as e: print(...)` block â€” no telemetry, no alerting.
  - Tasks may run **after** the request handler has returned and the DB connection has been GC'd â†’ potential use-after-close on the SQLite cursor (currently masked by per-task connection creation, but fragile).
- **Severity justification:** Predictable DoS under abuse (see P1-01).

**Fix sketch:**
- Bound the executor queue with `ThreadPoolExecutor(max_workers=4, max_queue_size=200)` â€” actually, Python's stdlib doesn't support that. Use `concurrent.futures.ThreadPoolExecutor` with a semaphore, or switch to `asyncio` + `aiohttp` for the I/O-bound parts.
- Wrap `task()` so it logs to a real logger, not `print`.
- Use a `try/finally` to ensure `conn.close()` runs even on error.

---

#### P2-04 â€” SQLite DB file written next to the source tree, no file locking strategy beyond Python's stdlib

- **Location:** `app.py`: `DB_FILE = "galgotias_cache.db"` (relative path).
- **What this means:**
  - The DB file lives in `C:\Users\iassh\3-GAL\` (or whatever the cwd is) â€” meaning whatever user runs `python app.py` writes there. In a production deploy as a service account, this is the service-account's home â€” fine. But in a multi-user box (PythonAnywhere, shared host), this is **other-user-readable SQLite containing your crawled content + any cached translation output**.
  - No `PRAGMA journal_mode=WAL` set â†’ under concurrent `/api/sync` + `/api/search`, you'll get `OperationalError: database is locked`.
  - No `PRAGMA foreign_keys=ON` (you don't need it here, but worth flagging as hygiene).
- **Severity justification:** Predictable race under any concurrent load.

**Fix sketch:**
```python
conn = sqlite3.connect(DB_FILE, timeout=10, isolation_level=None)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")  # safe enough with WAL
```

---

#### P2-05 â€” `extract_pdf_text` reads `pdf.pages[:10]` but unbounded text is then passed to regex extraction

- **Location:** `app.py` `extract_pdf_text()` â†’ `extract_key_info()`:
  ```python
  paper_codes = re.findall(r'\b([A-Z]{2,4}[-\s]?\d{3,4}[-\s]?[A-Z]?)\b', text, re.I)
  ...
  dates += re.findall(r'\b(\d{1,2}\s+(?:jan|feb|mar|...)\s+\d{2,4})\b', text, re.I)
  ```
- **Analysis:** I traced these patterns for catastrophic backtracking (ReDoS). The patterns are bounded â€” no nested quantifiers, no alternation overlap â€” so they are **not** ReDoS-prone. âœ…
- **However:** `text[:200]` truncation in `generate_pdf_summary` is on the *joined* string. If the PDF is malformed, `page.extract_text()` can return very long single-line strings (pdfplumber is forgiving). Combined with `text.strip()` and joining 10 pages, you can produce ~hundreds of KB of text â€” small but worth bounding.
- **Severity justification:** Low real-world impact, defensive coding only.

**Fix sketch:**
```python
text = ""
for page in pdf.pages[:10]:
    page_text = page.extract_text() or ""
    text += page_text[:5000] + "\n"   # cap per-page text
return text[:50_000].strip()   # hard total cap
```

---

#### P2-06 â€” `extract_text_parts` splits on whitespace but never caps `len(text_parts)`; combined with unbounded FTS query length

- **Location:** `app.py` `build_fts_query()` and `extract_text_parts()`.
- **What this means:** A 100 KB search query is split into N tokens, each wrapped in `"..."*` and OR'd together: `'"a"* OR "b"* OR "c"* ...'`. SQLite FTS5 will choke on a query string larger than ~1 MB and may raise an exception (caught by the broad `except` and falls back to LIKE â€” but the LIKE path then runs `title LIKE '%' + '%'.join(huge_words) + '%'`).
- **The good news:** The FTS query construction strips `"` and `'`, which mitigates FTS operator injection. Inside a `"..."` phrase, FTS5 treats everything literally â€” so this isn't an injection vector, just a length/stability issue.
- **Severity justification:** Latent DoS via pathological search queries. No auth gate makes this exploitable.

**Fix sketch:**
```python
def build_fts_query(query):
    if len(query) > 500:
        query = query[:500]
    tokens = query.split()[:32]   # cap token count
    ...
```

---

#### P2-07 â€” Static-site generator (`generate_static.py`) injects announcement data into HTML/JS without full HTML escaping

- **Location:** `generate_static.py` `generate_full_static_html()`:
  ```python
  title = item['title'].replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
  ...
  cards_html += f'''<div class="exam-card" data-url="{item['url'].replace('"', '&quot;')}" onclick="openPdf(this.dataset.url)">
      ...
      <div class="card-desc" ...>{item.get("desc", get_short_desc(title, item.get("category", "")))}</div>
      ...
  '''
  ```
- **What I found:**
  - âœ… `title` and `url` are HTML-escaped.
  - âš ï¸ `item.get("desc", ...)` is **not escaped**. The default desc comes from `get_short_desc()` which returns hardcoded English strings, so today this is safe.
  - âš ï¸ `category` is inserted into `<span class="card-category">{item.get("category", "")}</span>` **without escaping**. If a future code path ever produces a category containing `<`/`&`/script, you get stored XSS that ships to GitHub Pages.
- **The good news:** Today, `category` only ever takes the 8 hardcoded values from `categorize_title()`. But the abstraction is fragile.
- **Severity justification:** Defensive. Today zero exploitability. Tomorrow one careless edit away from persistent XSS on `anacondy.github.io/3-GAL/`.

**Fix sketch:**
```python
import html
...
cards_html += f'''
    <div class="exam-card" data-url="{html.escape(item['url'], quote=True)}" onclick="openPdf(this.dataset.url)">
      ...
      <div class="card-desc" ...>{html.escape(item.get("desc", get_short_desc(title, item.get("category", ""))))}</div>
      ...
      <span class="card-category">{html.escape(item.get("category", "") or "")}</span>
'''
```

`static_site/index.html` is regenerated each deploy so this fix propagates automatically.

---

### ðŸŸ¢ P3 â€” Low

#### P3-01 â€” Unused imports in `app.py` (`threading`, `tempfile`)

- **Location:** `app.py` top of file.
- **Why it matters:** Minor. Indicates dead code paths that may have once contained real logic. Worth deleting to reduce the attack surface that you have to reason about.
- **Fix:** `del threading`, `del tempfile`. (Just remove the import lines.)

#### P3-03 â€” `categorize_document()` has unreachable dead code

- **Location:** `app.py`:
  ```python
  if any(kw in text_lower for kw in ['exam', ...]): return "Exam"
  ...
  return "Notice"

  return "Notice"   # â† second `return "Notice"` is unreachable
  ```
- **Fix:** Delete the second `return "Notice"`.

#### P3-04 â€” `is_allowed_url()` accepts `http://` (not just `https://`)

- **Location:** `app.py`:
  ```python
  if parsed.scheme not in ('http', 'https'):
      return False
  ```
- **Impact:** Even on the legitimate domain, a TLS-stripping MITM (e.g., a coffee-shop Wi-Fi with a captive portal) can serve a malicious PDF that the analyzer will dutifully extract text from and possibly pass to a translation API. Low in practice for a public site.
- **Fix:** Restrict to `'https'` only.

#### P3-05 â€” No `Content-Security-Policy`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` on Flask responses

- **Location:** `app.py` â€” no `@app.after_request` handler.
- **Impact:** Defense-in-depth missing. If Jinja2 ever gets a bypass, there's no CSP to fall back on.
- **Fix:**
  ```python
  @app.after_request
  def set_security_headers(resp):
      resp.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; frame-src https://docs.google.com;"
      resp.headers['X-Content-Type-Options'] = 'nosniff'
      resp.headers['Referrer-Policy'] = 'no-referrer'
      resp.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
      return resp
  ```

#### P3-06 â€” No CSRF token on `POST /api/sync` or `POST /api/analyze`

- **Location:** Both routes accept JSON bodies; CORS is implicit (no headers, so same-origin only â€” which actually *helps* here). But the routes are state-changing and unauthenticated.
- **Impact:** Combined with P1-02, an attacker can host a malicious page that auto-POSTs to your `/api/sync` to trigger an outbound request to Galgotias from your visitors' machines (CSRF as outbound DoS).
- **Fix:** Either require a custom header (`X-Requested-With: XMLHttpRequest`) â€” which a browser will not send cross-origin without CORS â€” or add a CSRF token. The custom-header trick is the cheaper fix here since CORS isn't enabled.

#### P3-07 â€” `pdfplumber.open(io.BytesIO(content))` â€” full PDF in memory

- **Location:** `download_pdf()`.
- **Impact:** Multiplies the OOM risk in P1-01. A 500 MB "PDF" response consumes 500 MB of RSS *before* pdfplumber even tries to parse it.
- **Fix:** Cap with `MAX_PDF_BYTES` and stream (see P1-01 fix).

#### P3-08 â€” `MAX_ANNOUNCEMENTS = 470` and `MAX_ANNOUNCEMENTS` literal duplicated in `generate_static.py`

- **Location:** Both files.
- **Impact:** If you change the cap in one place, the static-site output silently disagrees with the live app. Not a security issue, but it produces inconsistent UX.
- **Fix:** Centralize in a `config.py`.

#### P3-09 â€” GitHub Actions `softprops/action-gh-release@v1` is unmaintained and `@v1` is unpinned

- **Location:** `.github/workflows/build-release.yml`
- **Impact:** Tag-pinned actions drift; using `@v1` (or any unpinned major) means a compromised action maintainer can push malicious code that runs on your tagged-release builds with `contents: write`. This is the supply-chain class of CVE-2024-â€¦ events from late 2024/early 2025.
- **Fix:** Pin to a SHA: `softprops/action-gh-release@dec0d2cbf5e635e9b303d6e9bfe36c1915fd0951` (the SHA corresponding to v2).

---

### âšª P4 â€” Informational / Hygiene

#### P4-01 â€” `errorDetails.message` (and raw exception text) returned to the client via `/api/analyze`

- **Location:** `app.py`:
  ```python
  except Exception as e:
      return jsonify({"error": str(e)}), 500
  ```
- **Why this matters:** Python exceptions frequently contain file paths, library versions, and snippets of attacker-influenced data (e.g., the URL they POSTed). Useful for fingerprinting.
- **Fix:** Log full traceback server-side; return a generic `"error": "analysis failed"` to the client.

#### P4-02 â€” React app (`cinema-scanner-/src/App.jsx`) embeds Gemini API key in client URL

- **Location:**
  ```javascript
  const apiKey = import.meta.env.VITE_GEMINI_API_KEY;
  ...
  fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`, ...)
  ```
- **Why this is informational and not P1:** The `VITE_GEMINI_API_KEY` is **already** intended for browser use by design (that's the `VITE_` prefix). But the URL query-string transport exposes the key in:
  - Browser DevTools "Network" tab.
  - Any HTTP server log / proxy log on the path.
  - The `Referer` header of any subresource fetched by Google's response (mitigatable with `Referrer-Policy: no-referrer`).
- **Fix:** Use a backend proxy. At minimum, set the Gemini key's HTTP referer restriction in Google AI Studio to your domain.

#### P4-03 â€” `googletrans.Translator()` instantiated at module import time

- **Location:** `app.py`:
  ```python
  try:
      from googletrans import Translator
      translator = Translator()       # â† at import time
      TRANSLATOR_AVAILABLE = True
  except ImportError:
      TRANSLATOR_AVAILABLE = False
  ```
- **Impact:** Any exception during `Translator()` construction (network probe, etc.) will crash the Flask app at startup. Wrap in try/except or defer construction.

#### P4-04 â€” Service Worker referenced but never shipped

- **Location:** `templates/index.html`:
  ```javascript
  if('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
  ```
- **No `/sw.js` exists** in the bundle. The `.catch(() => {})` masks the 404 silently. Harmless but generates noise in DevTools.
- **Fix:** Remove the block, or actually ship a service worker if PWA is a goal.

#### P4-05 â€” Google Docs Viewer proxy in `templates/index.html` and `generate_static.py` leaks PDF URLs to Google

- **Location:** Both, in `openPdf()` / equivalent.
- **Impact:** Every PDF the user clicks is fetched by Google; the URL is logged by Google's viewer infrastructure. For public university PDFs this is fine; for any sensitive document it's a privacy leak.
- **Fix:** Acceptable for public PDFs; flag in the UI ("Viewing via Google Docs Viewer") for transparency.

#### P4-06 â€” `os.makedirs(OUTPUT_DIR, exist_ok=True)` in `generate_static.py` writes into the repo working directory

- **Location:** `generate_static.py` `main()`.
- **Impact:** In CI (GitHub Actions), this writes into the checkout, which is fine. Locally, it writes to wherever you ran it from. Predictable but worth noting.

---

## 4. Recommendations Table (quick remediation map)

| # | Finding | Severity | One-line fix |
|---|---|---|---|
| P1-01 | `/api/analyze` size/rate | ðŸŸ  High | Cap at 25 MB, add `flask-limiter`, stream chunks |
| P1-02 | `/api/sync` unauth abuse | ðŸŸ  High | Require shared-secret header + rate limit |
| P1-03 | `googletrans==4.0.0-rc1` pin | ðŸŸ  High | Replace with `deep-translator` or drop the feature |
| P2-01 | `Alvido` plaintext "secret" | ðŸŸ¡ Med | Delete the README section + dead code branch |
| P2-02 | `FLASK_DEBUG` env knob | ðŸŸ¡ Med | Hard-code `debug=False`, delete the env var |
| P2-03 | Unbounded executor queue | ðŸŸ¡ Med | Bound queue, propagate exceptions to logger |
| P2-04 | SQLite lock contention | ðŸŸ¡ Med | Enable WAL mode, set `timeout=10` |
| P2-05 | Unbounded PDF text | ðŸŸ¡ Med | Cap per-page + total text length |
| P2-06 | Unbounded search query | ðŸŸ¡ Med | Cap query at 500 chars, 32 tokens |
| P2-07 | Static-gen missing escape | ðŸŸ¡ Med | Use `html.escape()` for `category` and `desc` |
| P3-01 | Dead imports | ðŸŸ¢ Low | Remove `threading`, `tempfile` |
| P3-02 | Duplicate `return "Notice"` | ðŸŸ¢ Low | Delete unreachable line |
| P3-03 | `is_allowed_url` allows http | ðŸŸ¢ Low | Restrict to `https` only |
| P3-04 | No security headers | ðŸŸ¢ Low | Add `@app.after_request` CSP/XCTO/Referrer-Policy |
| P3-05 | No CSRF on state-changing POSTs | ðŸŸ¢ Low | Require `X-Requested-With` header |
| P3-06 | `pdfplumber` reads full PDF | ðŸŸ¢ Low | Stream with size cap (see P1-01) |
| P3-07 | `MAX_ANNOUNCEMENTS` duplicated | ðŸŸ¢ Low | Centralize in `config.py` |
| P3-08 | Unpinned GH action | ðŸŸ¢ Low | Pin `softprops/action-gh-release` to SHA |
| P4-01 | Raw exception in JSON response | âšª Info | Log full traceback; return generic error |
| P4-02 | Gemini key in browser URL | âšª Info | Add `Referrer-Policy: no-referrer` minimum |
| P4-03 | `Translator()` at import time | âšª Info | Move to lazy init inside `translate_text()` |
| P4-04 | `/sw.js` referenced, not shipped | âšª Info | Remove the registration block |
| P4-05 | Google Docs Viewer proxy | âšª Info | Add UI disclosure |
| P4-06 | Output dir = cwd | âšª Info | Pass via env var |

---

## 5. Priority-ordered Remediation List (what to do *today*)

1. **Stop the bleeding (1 hour):**
   - Add a size cap to `download_pdf` (P1-01).
   - Add `flask-limiter` to `/api/sync` and `/api/analyze` (P1-01, P1-02).
   - Delete the `Alvido` block in `app.py` and the README section (P2-01).
   - Hard-pin `debug=False` (P2-02).

2. **Reliability (2â€“3 hours):**
   - Replace `googletrans==4.0.0-rc1` (P1-03).
   - Enable WAL mode + bound query lengths (P2-04, P2-06).
   - Bound PDF text length (P2-05).
   - Add `html.escape()` in `generate_static.py` (P2-07).

3. **Defense in depth (1â€“2 hours):**
   - Security headers via `@app.after_request` (P3-04).
   - CSRF trick via `X-Requested-With` (P3-05).
   - Pin GitHub Actions to SHAs (P3-08).

4. **Hygiene (1 hour):**
   - Remove dead imports, dead `return`, dead `Alvido` comments (P3-01, P3-02, P2-01).

---

## 6. Appendix â€” Locations Summary

| Finding | File | Line region |
|---|---|---|
| P1-01 | `app.py` | `download_pdf`, `analyze_pdf` route |
| P1-02 | `app.py` | `/api/sync` route |
| P1-03 | `requirements.txt` | `googletrans==4.0.0-rc1` |
| P2-01 | `app.py`, `README.md`, `docs/API.md` | `/api/search`, README "Admin Access" section |
| P2-02 | `app.py` | end of file, `app.run(...)` |
| P2-03 | `app.py` | `executor`, `analyze_pdf_async` |
| P2-04 | `app.py` | `sqlite3.connect(DB_FILE)` calls |
| P2-05 | `app.py` | `extract_pdf_text`, `extract_key_info` |
| P2-06 | `app.py` | `comprehensive_search`, `build_fts_query` |
| P2-07 | `generate_static.py` | `generate_full_static_html` |
| P3-01 | `app.py` | top imports |
| P3-02 | `app.py` | `categorize_document` |
| P3-03 | `app.py` | `is_allowed_url` |
| P3-04 | `app.py` | (missing) add `@app.after_request` |
| P3-05 | `app.py` | `/api/sync`, `/api/analyze` |
| P3-06 | `app.py` | `download_pdf` |
| P3-07 | `app.py`, `generate_static.py` | `MAX_ANNOUNCEMENTS` |
| P3-08 | `.github/workflows/build-release.yml` | `softprops/action-gh-release@v1` |
| P4-01 | `app.py` | `/api/analyze` `except Exception` |
| P4-02 | `cinema-scanner-/src/App.jsx` | `analyzeArtifact`, `checkApiHealth` |
| P4-03 | `app.py` | top-level `from googletrans import Translator` |
| P4-04 | `templates/index.html` | service worker registration block |
| P4-05 | `templates/index.html`, `generate_static.py` | `openPdf()` |
| P4-06 | `generate_static.py` | `main()` |

---

## 7. Things That Are Correct (don't change them)

For balance â€” these were checked and are fine:

- âœ… **SQL injection:** All SQLite queries use parameterized `?` placeholders. No string interpolation into SQL anywhere.
- âœ… **Jinja2 auto-escaping:** `{{ item.title }}`, `{{ item.date_text }}`, `{{ item.url }}` in `templates/index.html` are HTML-escaped by Jinja2's default. No `|safe` filter used.
- âœ… **SSRF allowlist correctness:** `is_allowed_url()` correctly handles the `@`-in-URL and subdomain-suffix bypass classes. Tested `https://galgotiasuniversity.edu.in@evil.com/`, `https://www.galgotiasuniversity.edu.in.evil.com/`, and port-based variants â€” all correctly blocked.
- âœ… **PDF content validation:** `download_pdf` checks both Content-Type header, URL extension, and the `%PDF-` magic bytes before returning. A response claiming to be a PDF but actually serving HTML is filtered out.
- âœ… **ReDoS:** All regex patterns in `app.py` were checked for catastrophic backtracking. None are vulnerable.
- âœ… **React XSS:** `cinema-scanner-/src/App.jsx` does not use `dangerouslySetInnerHTML`. The Gemini response is parsed as JSON and rendered via React state, which escapes by default.

---

**End of report.**


# STATUS (2026-06-23): Every finding in this audit has been remediated in the current main branch. See docs/FINAL_REPORT.md for the per-commit fix map.
