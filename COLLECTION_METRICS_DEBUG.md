# Collection Metrics Not Reflecting Data - Debug Guide

## Possible Reasons

Based on the code analysis, here are the most likely reasons why Collection Metrics is showing ₹0:

### 1. **API Authentication Failure** (Most Likely)
- The API might be returning `{"message": "not authorised"}` or `{"error": "unauthorized"}`
- **Check**: Look for `[Collection Metrics] ✗✗✗ AUTHENTICATION FAILED!` in server console
- **Solution**: Ensure the `blinkr_token` from login is being passed correctly

### 2. **API Returning Empty Data**
- The API might return `{}` (empty dict) if there's no data for the selected date range
- **Check**: Look for `[Collection Metrics] collection_metrics is EMPTY DICT!` in server console
- **Solution**: Try a different date range or check if the API has data for today's date

### 3. **API Response Structure Mismatch**
- The API might return data in a structure we're not expecting
- **Check**: Look for `[Collection Metrics] Response Text` in server console to see the actual structure
- **Solution**: Update the parsing logic to match the actual API response structure

### 4. **API Error Status Code**
- The API might return a non-200 status code (401, 403, 500, etc.)
- **Check**: Look for `[Collection Metrics] ✗✗✗ API Error Status:` in server console
- **Solution**: Check the error message and fix the issue

## How to Debug

### Step 1: Check Server Console Logs

When you load the disbursal summary page, look for these log messages in your Django server console:

```
[Collection Metrics] ✓ Using blinkr_token from session (SAME AS LOGIN)
[Collection Metrics] Response Status: 200
[Collection Metrics] Response Text: {...}
[Collection Metrics] ===== FINAL RESULT =====
```

**What to look for:**
- ✅ If you see `✓ Using blinkr_token` → Token is being passed
- ❌ If you see `✗ ERROR: No blinkr_token` → Token is missing
- ❌ If you see `✗✗✗ AUTHENTICATION FAILED` → Token is invalid/expired
- ❌ If you see `✗✗✗ API Error Status: 401/403` → Authentication issue
- ❌ If you see `collection_metrics is EMPTY DICT!` → API returned empty data

### Step 2: Test API Directly

Run the test script to see what the API actually returns:

```bash
python3 test_collection_metrics.py
```

You'll need to provide your `blinkr_token` (get it from browser localStorage or Django session).

### Step 3: Check Browser Console

Open browser DevTools (F12) → Console tab and look for:

```
=== COLLECTION METRICS UPDATE ===
Collection Metrics Object: {...}
```

This shows what data the frontend received from the AJAX call.

## Common Issues & Solutions

### Issue 1: "not authorised" Error
**Symptom**: Server console shows `AUTHENTICATION FAILED`

**Solution**:
1. Logout and login again to get a fresh token
2. Check if token is stored in session: `request.session.get('blinkr_token')`
3. Verify token format: Should be `Bearer {token}` in Authorization header

### Issue 2: Empty Response `{}`
**Symptom**: Server console shows `collection_metrics is EMPTY DICT!`

**Possible Causes**:
- No data for the selected date range
- API endpoint might be wrong
- API might require different parameters

**Solution**:
1. Try a different date range (e.g., last week)
2. Verify API endpoint: `https://backend.blinkrloan.com/insights/v2/collection_metrics`
3. Check if API requires additional parameters

### Issue 3: Response Structure Mismatch
**Symptom**: API returns data but it's not being parsed correctly

**Solution**:
1. Check the actual API response structure in server console
2. Update the parsing logic in `views.py` to match the actual structure
3. The code currently checks for: `data`, `result`, `metrics` keys, or uses full response

## Code Flow

1. **Page Load** (`disbursal_summary` view):
   - Gets `blinkr_token` from `request.session`
   - Calls `https://backend.blinkrloan.com/insights/v2/collection_metrics`
   - Parses response and extracts metrics
   - Sends to template as `collection_metrics`

2. **Auto-Refresh** (`disbursal_data_api` endpoint):
   - Same process as above
   - Returns JSON with `collection_metrics` key
   - JavaScript updates the KPI cards

3. **Template Display** (`_kpi_cards.html`):
   - Shows `collection_metrics.total_collection_amount` (or variations)
   - Falls back to `₹0` if empty

## Next Steps

1. **Check your server console** when loading the page
2. **Share the console output** (especially `[Collection Metrics]` lines)
3. **Run the test script** to see the actual API response
4. **Check browser console** for frontend errors

Once we see the actual API response, we can fix the parsing logic accordingly.

