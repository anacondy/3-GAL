# API Reference

Complete API documentation for 3-GAL.

## Base URL

```
http://localhost:5007
```

## Authentication

Currently, no authentication is required for API endpoints. Admin functions use client-side credential check.

---

## Endpoints

### GET /

**Description**: Main application page with announcement list.

**Response**: HTML page with rendered announcements.

---

### POST /api/sync

**Description**: Trigger synchronization with the university website to fetch new announcements.

**Request Body**: None

**Response**:

```json
{
    "status": "success",
    "count": 25,
    "message": "Synchronized 25 announcements"
}
```

**Error Response**:

```json
{
    "status": "error",
    "count": 0,
    "message": "Sync failed"
}
```

**Example**:

```bash
curl -X POST http://localhost:5007/api/sync
```

---

### GET /api/search

**Description**: Search announcements with comprehensive query support.

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query |

**Query Examples**:

| Query | Description |
|-------|-------------|
| `exam` | Find all exam-related announcements |
| `2024` | Find announcements from 2024 |
| `15-01-2024` | Find announcements with specific date |
| `CS101` | Find announcements with paper code |
| `exam December` | Combined text search |

**Response**:

```json
[
    {
        "id": 1,
        "date_text": "15-01-2024",
        "title": "End Term Examination Schedule",
        "url": "https://example.com/announcement.pdf",
        "crawled_at": "2024-01-15 10:30:00",
        "pdf_summary": "Type: Examination | Dates: 20-01-2024, 25-01-2024",
        "category": "Examination",
        "translated_title": null
    }
]
```

**Example**:

```bash
curl "http://localhost:5007/api/search?q=exam%202024"
```

---

### POST /api/analyze

**Description**: Analyze a PDF document and extract key information.

**Request Body**:

```json
{
    "url": "https://example.com/document.pdf"
}
```

**Response (Success)**:

```json
{
    "summary": "Type: Examination | Paper Codes: CS101, CS102 | Dates: 15-01-2024",
    "category": "Examination",
    "key_info": {
        "paper_codes": ["CS101", "CS102"],
        "dates": ["15-01-2024", "20-01-2024"],
        "times": ["10:00 AM", "2:00 PM"],
        "subjects": ["computer", "programming"]
    },
    "language_detected": "en",
    "translated": false,
    "cached": false
}
```

**Response (Cached)**:

```json
{
    "summary": "Type: Examination | Paper Codes: CS101",
    "category": "Examination",
    "cached": true
}
```

**Error Response**:

```json
{
    "error": "Could not download PDF"
}
```

**Example**:

```bash
curl -X POST http://localhost:5007/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/exam.pdf"}'
```

---

### GET /api/data

**Description**: Retrieve all announcements with optional filtering.

**Query Parameters**:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `category` | string | No | - | Filter by category |
| `limit` | integer | No | 100 | Maximum results (max 500) |

**Response**:

```json
[
    {
        "id": 1,
        "date_text": "15-01-2024",
        "title": "Examination Notice",
        "url": "https://example.com/notice.pdf",
        "crawled_at": "2024-01-15 10:30:00",
        "pdf_summary": "Type: Examination",
        "category": "Examination",
        "translated_title": null
    }
]
```

**Examples**:

```bash
# Get all announcements
curl "http://localhost:5007/api/data"

# Get examination announcements only
curl "http://localhost:5007/api/data?category=Examination"

# Get latest 20 announcements
curl "http://localhost:5007/api/data?limit=20"
```

---

### GET /api/categories

**Description**: Get list of all unique categories.

**Response**:

```json
[
    "Examination",
    "Result",
    "Academic Calendar",
    "Fee Notice",
    "General Notice"
]
```

**Example**:

```bash
curl http://localhost:5007/api/categories
```

---

### GET /health

**Description**: Health check endpoint for monitoring.

**Response**:

```json
{
    "status": "healthy",
    "pdf_support": true,
    "translation_support": true,
    "language_detection": true
}
```

**Example**:

```bash
curl http://localhost:5007/health
```

---

## Data Models

### Announcement

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique identifier |
| `date_text` | string | Announcement date (DD-MM-YYYY) |
| `title` | string | Announcement title |
| `url` | string | URL to PDF or detail page |
| `crawled_at` | datetime | When the announcement was scraped |
| `pdf_summary` | string | AI-generated summary |
| `category` | string | Document category |
| `translated_title` | string | English translation (if Hindi) |

### Category Values

- `Examination`
- `Academic Calendar`
- `Result`
- `Fee Notice`
- `Admission`
- `Uniform/Dress Code`
- `Event`
- `Assignment/Project`
- `Internship/Placement`
- `Important Dates`
- `General Notice`

---

## Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (missing parameters) |
| 500 | Server Error |

### Error Response Format

```json
{
    "error": "Error message description"
}
```

---

## Rate Limiting

Currently, there is no rate limiting implemented. For production deployment, consider adding:

- Request rate limiting per IP
- PDF analysis queue limits
- Search query caching

---

## Examples

### JavaScript/Fetch

```javascript
// Search
async function search(query) {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    return await response.json();
}

// Analyze PDF
async function analyzePdf(url) {
    const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    });
    return await response.json();
}

// Sync data
async function syncData() {
    const response = await fetch('/api/sync', { method: 'POST' });
    return await response.json();
}
```

### Python/Requests

```python
import requests

BASE_URL = "http://localhost:5007"

# Search
def search(query):
    response = requests.get(f"{BASE_URL}/api/search", params={"q": query})
    return response.json()

# Analyze PDF
def analyze_pdf(url):
    response = requests.post(
        f"{BASE_URL}/api/analyze",
        json={"url": url}
    )
    return response.json()

# Sync
def sync():
    response = requests.post(f"{BASE_URL}/api/sync")
    return response.json()
```

### cURL

```bash
# Search for examination announcements
curl "http://localhost:5007/api/search?q=examination"

# Analyze a PDF
curl -X POST http://localhost:5007/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/exam.pdf"}'

# Trigger sync
curl -X POST http://localhost:5007/api/sync

# Get categories
curl http://localhost:5007/api/categories

# Health check
curl http://localhost:5007/health
```
