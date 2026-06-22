"""Smoke tests for the Flask app routes.

Uses Flask's test_client — no network calls, no live scraping.
"""
import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_health_endpoint_returns_healthy(client):
    rv = client.get('/health')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['status'] == 'healthy'
    assert 'pdf_support' in data
    assert 'language_detection' in data


def test_search_endpoint_works_without_auth(client):
    rv = client.get('/api/search?q=')
    assert rv.status_code == 200
    # Returns a list (possibly empty if DB is empty, populated otherwise).
    assert isinstance(rv.get_json(), list)


def test_search_handles_long_query(client):
    long_query = "x" * 10000
    rv = client.get(f'/api/search?q={long_query}')
    assert rv.status_code == 200


def test_sync_requires_xhr_header(client):
    rv = client.post('/api/sync')
    assert rv.status_code == 403
    data = rv.get_json()
    assert 'X-Requested-With' in data['error']


def test_sync_with_xhr_header_passes_guard(client):
    rv = client.post('/api/sync', headers={'X-Requested-With': 'XMLHttpRequest'})
    # 200 or 429 are both OK; what matters is NOT 403
    assert rv.status_code != 403


def test_analyze_requires_xhr_header(client):
    rv = client.post('/api/analyze', json={"url": "https://example.com/x.pdf"})
    assert rv.status_code == 403


def test_analyze_rejects_empty_url(client):
    rv = client.post(
        '/api/analyze',
        json={"url": ""},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert rv.status_code == 400
    assert 'No URL' in rv.get_json()['error']


def test_analyze_rejects_disallowed_url(client):
    rv = client.post(
        '/api/analyze',
        json={"url": "https://evil.com/x.pdf"},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert rv.status_code == 400


def test_categories_endpoint_works(client):
    rv = client.get('/api/categories')
    assert rv.status_code == 200
    assert isinstance(rv.get_json(), list)


def test_data_endpoint_accepts_limit_param(client):
    rv = client.get('/api/data?limit=10')
    assert rv.status_code == 200
    assert isinstance(rv.get_json(), list)


def test_data_endpoint_caps_limit_at_500(client):
    rv = client.get('/api/data?limit=100000')
    assert rv.status_code == 200
    assert len(rv.get_json()) <= 500
