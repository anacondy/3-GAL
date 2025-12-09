# Announcement Counter Fix Documentation

## Problem Statement

The announcement counter was showing a fixed value (470) and not updating when new announcements were added. This was causing confusion about whether:
1. The counter was not updating in real-time
2. There was a hard limit capping at 470
3. Old announcements were not being deleted when new ones arrived

## Root Cause Analysis

After analyzing the codebase, we identified the following issues:

1. **No Cleanup Mechanism**: The `save_announcement()` function only inserted new records or updated existing ones, but never deleted old ones. This meant the database could grow indefinitely.

2. **No Max Limit Enforcement**: There was no maximum limit configured, so the database could contain any number of announcements.

3. **Static Counter Display**: The counter on the static GitHub Pages site showed the count at generation time, which could become stale if announcements weren't being fetched properly.

## Solution Implementation

### 1. Maximum Announcements Limit

Added a configurable `MAX_ANNOUNCEMENTS` constant set to 470:

```python
# Maximum number of announcements to keep in database
# When this limit is reached, oldest announcements will be automatically deleted
MAX_ANNOUNCEMENTS = 470
```

This constant is used in both:
- `app.py` (Flask application)
- `generate_static.py` (Static site generator)

### 2. Automatic Cleanup Function

Created `cleanup_old_announcements()` function in `app.py`:

```python
def cleanup_old_announcements():
    """Remove oldest announcements if count exceeds MAX_ANNOUNCEMENTS."""
    # Gets current count
    # If count > MAX_ANNOUNCEMENTS:
    #   - Calculates how many to delete
    #   - Deletes oldest announcements (by id)
    #   - Logs the operation
    # Returns number of deleted records
```

**Key Features:**
- Only deletes when count exceeds `MAX_ANNOUNCEMENTS`
- Deletes oldest announcements first (by ID, which is auto-incremented)
- Logs cleanup operations for debugging
- Returns count of deleted records

### 3. Integration with Sync Process

Updated `scrape_and_sync()` function to:
1. Fetch and save new announcements
2. Run cleanup to enforce the limit
3. Return accurate count after cleanup

```python
# After saving all announcements
deleted = cleanup_old_announcements()

# Get final count after cleanup
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM announcements")
total_count = c.fetchone()[0]
conn.close()
```

### 4. Enhanced API Response

Updated `/api/sync` endpoint to return:
- `count`: Number of items processed in this sync
- `total`: Total announcements in database after cleanup
- `max_limit`: The maximum allowed announcements (470)
- `message`: Detailed status message

Example response:
```json
{
    "status": "success",
    "count": 15,
    "total": 470,
    "max_limit": 470,
    "message": "Synchronized 15 announcements (Total: 470/470)"
}
```

### 5. Real-Time Counter Display

**Flask App (`templates/index.html`):**
- Added stats display showing current count and max limit
- Updates automatically after sync operations
- JavaScript updates the counter in real-time

```html
<div class="stats" id="stats-display">
    📢 <span class="count" id="total-count">{{ total_count }}</span> 
    announcements in database (max <span class="count">{{ max_limit }}</span>)
</div>
```

**Static Site (`generate_static.py`):**
- Shows announcement count with max limit
- Applied same limit when generating static pages

```html
<div class="stats">
    📢 {len(announcements)} announcements loaded (max {MAX_ANNOUNCEMENTS})
</div>
```

### 6. Index Route Enhancement

Updated the `/` route to:
1. Get total count from database
2. Pass it to template along with max limit
3. Ensure accurate display on page load

## Testing

Created comprehensive test suite (`test_cleanup.py`) that verifies:

1. ✅ Adding announcements beyond the limit
2. ✅ Cleanup deletes correct number of old records
3. ✅ Final count stays within limit (≤ 470)
4. ✅ No deletions when count is under limit
5. ✅ Database integrity is maintained

**Test Results:**
```
✅ PASS: Count is within limit (470 <= 470)
✅ PASS: Correct number deleted (50 == 50)
✅ PASS: No deletions when under limit
```

## How It Works Now

### Normal Operation Flow

1. **University adds new announcement** on their website
2. **GitHub Actions runs daily** at 6 AM UTC (or on push to main)
3. **Static generator fetches** announcements from university website
4. **Cleanup is applied** if count > 470, keeping most recent ones
5. **Static site is generated** with accurate counter
6. **Deployed to GitHub Pages** with updated count

### Flask App Flow

1. **User visits the site** or clicks "SYNC SERVER"
2. **App fetches** latest announcements
3. **Saves** new/updated announcements to database
4. **Cleanup runs** automatically after sync
5. **Counter updates** in real-time showing new total
6. **User sees accurate count** (e.g., "470/470")

## Benefits

1. ✅ **Accurate Counter**: Always shows the real count from database
2. ✅ **Automatic Cleanup**: Old announcements are deleted automatically
3. ✅ **No Manual Intervention**: Maintains itself within the 470 limit
4. ✅ **Real-Time Updates**: Counter updates after each sync
5. ✅ **Configurable**: `MAX_ANNOUNCEMENTS` can be easily changed
6. ✅ **Logged Operations**: Cleanup operations are logged for debugging
7. ✅ **Tested**: Comprehensive test suite ensures reliability

## Configuration

To change the maximum number of announcements:

1. Edit `app.py` and update `MAX_ANNOUNCEMENTS`
2. Edit `generate_static.py` and update `MAX_ANNOUNCEMENTS`
3. Both should have the same value

## Monitoring

Check logs for cleanup operations:
```
--- [CLEANUP] Deleted 50 old announcements (kept latest 470) ---
--- [SYSTEM] TOTAL ANNOUNCEMENTS IN DB: 470 (max: 470) ---
```

## Future Enhancements

Possible improvements:
1. Add admin panel to configure `MAX_ANNOUNCEMENTS` dynamically
2. Add date-based cleanup (e.g., delete announcements older than 1 year)
3. Add archive feature to preserve old announcements
4. Add analytics to track announcement trends over time
