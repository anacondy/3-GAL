"""Tests for config.py — ensures constants are sensible."""
from config import (
    MAX_ANNOUNCEMENTS,
    MAX_PDF_BYTES,
    MAX_TEXT_PER_PAGE,
    MAX_TEXT_TOTAL,
    MAX_QUERY_LENGTH,
    MAX_QUERY_TOKENS,
    ALLOWED_PDF_DOMAINS,
    HEADERS,
)


def test_max_announcements_is_positive_int():
    assert isinstance(MAX_ANNOUNCEMENTS, int)
    assert MAX_ANNOUNCEMENTS > 0


def test_max_pdf_bytes_is_25mb():
    """Phase 1 P1-01: cap is 25 MB = 26,214,400 bytes."""
    assert MAX_PDF_BYTES == 25 * 1024 * 1024


def test_text_caps_are_positive():
    assert MAX_TEXT_PER_PAGE > 0
    assert MAX_TEXT_TOTAL > MAX_TEXT_PER_PAGE  # total > per-page


def test_query_caps_are_reasonable():
    assert MAX_QUERY_LENGTH >= 100
    assert MAX_QUERY_LENGTH <= 10_000
    assert MAX_QUERY_TOKENS >= 8
    assert MAX_QUERY_TOKENS <= 100


def test_allowed_domains_are_https_only():
    """Phase 1 P3-03: only the official Galgotias domains."""
    assert "galgotiasuniversity.edu.in" in ALLOWED_PDF_DOMAINS
    assert "www.galgotiasuniversity.edu.in" in ALLOWED_PDF_DOMAINS
    # Should not include anything sketchy
    assert all("galgotiasuniversity.edu.in" in d for d in ALLOWED_PDF_DOMAINS)


def test_user_agent_looks_like_a_real_browser():
    ua = HEADERS.get("User-Agent", "")
    assert "Mozilla" in ua or "Chrome" in ua or "Safari" in ua
