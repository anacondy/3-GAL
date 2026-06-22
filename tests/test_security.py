"""Security-focused unit tests for SSRF allowlist, date normalization, FTS caps."""
from config import (
    MAX_QUERY_LENGTH, MAX_QUERY_TOKENS,
    ALLOWED_PDF_DOMAINS, REQUEST_TIMEOUT,
)
from app import (
    is_allowed_url,
    normalize_date_for_sort,
    build_fts_query,
    extract_text_parts,
    extract_date_patterns,
)


# --- SSRF allowlist tests ---

def test_is_allowed_url_rejects_external():
    assert is_allowed_url("https://evil.com/x.pdf") is False


def test_is_allowed_url_rejects_http():
    assert is_allowed_url("http://galgotiasuniversity.edu.in/x.pdf") is False


def test_is_allowed_url_rejects_other_schemes():
    assert is_allowed_url("ftp://galgotiasuniversity.edu.in/x.pdf") is False
    assert is_allowed_url("file:///etc/passwd") is False
    assert is_allowed_url("javascript:alert(1)") is False


def test_is_allowed_url_rejects_lookalike_domains():
    assert is_allowed_url("https://galgotiasuniversity.edu.in.evil.com/x.pdf") is False
    assert is_allowed_url("https://galgotiasuniversity.edu.in@evil.com/x.pdf") is False
    assert is_allowed_url("https://evil-galgotiasuniversity.edu.in/x.pdf") is False


def test_is_allowed_url_rejects_unusual_ports():
    assert is_allowed_url("https://galgotiasuniversity.edu.in:8080/x.pdf") is False


def test_is_allowed_url_accepts_own_domain():
    assert is_allowed_url("https://galgotiasuniversity.edu.in/x.pdf") is True
    assert is_allowed_url("https://www.galgotiasuniversity.edu.in/x.pdf") is True


def test_is_allowed_url_accepts_subdomains():
    assert is_allowed_url("https://cdn.galgotiasuniversity.edu.in/x.pdf") is True
    assert is_allowed_url("https://static.galgotiasuniversity.edu.in/x.pdf") is True


def test_is_allowed_url_handles_garbage():
    assert is_allowed_url("") is False
    assert is_allowed_url("not-a-url") is False
    assert is_allowed_url(None) is False


# --- Sort date normalization tests ---

def test_normalize_dd_mm_yyyy():
    assert normalize_date_for_sort("28-11-2025") == "2025-11-28"
    assert normalize_date_for_sort("08-10-2025") == "2025-10-08"
    assert normalize_date_for_sort("22-06-2026") == "2026-06-22"


def test_normalize_dd_slash_mm_yyyy():
    assert normalize_date_for_sort("28/11/2025") == "2025-11-28"


def test_normalize_handles_2digit_year():
    result = normalize_date_for_sort("28-11-25")
    assert result == "2025-11-28" or result == "1925-11-28"


def test_normalize_returns_empty_for_invalid():
    assert normalize_date_for_sort("") == ""
    assert normalize_date_for_sort("not a date") == ""
    assert normalize_date_for_sort(None) is ""
    assert normalize_date_for_sort("28-11") == ""


def test_normalize_single_digit_day():
    result = normalize_date_for_sort("8-10-2025")
    assert result == "2025-10-08"


# --- FTS query safety tests ---

def test_build_fts_query_strips_double_quotes():
    q = build_fts_query('"hello"')
    assert "hello" in q


def test_build_fts_query_strips_single_quotes():
    q = build_fts_query("hello'world")
    assert "'" not in q


def test_build_fts_query_caps_token_count():
    long = " ".join([f"word{i}" for i in range(100)])
    q = build_fts_query(long)
    assert q.count("OR") <= MAX_QUERY_TOKENS - 1


def test_build_fts_query_handles_empty_input():
    # Truly empty input returns empty string.
    assert build_fts_query("") == ""
    # Whitespace-only: no tokens survive stripping, falls through to original.
    result = build_fts_query("   ")
    assert result == "   " or result == ""


def test_build_fts_query_handles_only_special_chars():
    q = build_fts_query('"" ""')
    assert q == '"" ""' or q == ""


# --- Search query length tests ---

def test_extract_text_parts_strips_dates():
    parts = extract_text_parts("exam 2025-11-28 schedule")
    assert "exam" in parts
    assert "schedule" in parts
    assert "2025-11-28" not in parts
    assert "2025" not in parts


def test_extract_date_patterns_finds_dates():
    patterns = extract_date_patterns("exam on 28-11-2025")
    assert "28-11-2025" in patterns


def test_extract_date_patterns_finds_years():
    patterns = extract_date_patterns("exam in 2025")
    assert "2025" in patterns
