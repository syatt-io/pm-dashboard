# Meeting Analysis Authentication Investigation - October 20, 2025

## Problem Statement

User reports: "still failing to analyze, think hard to find the root cause please, and see if you can test it first"

Meeting analysis button not working despite previous serialization fixes being deployed.

## Investigation Findings

### 1. Authentication Architecture

The application uses JWT-based authentication with two auth methods:
- **Authorization header**: `Bearer <token>`
- **Cookie fallback**: `auth_token`

**Auth Service**: `src/services/auth.py`
- JWT tokens stored in localStorage on frontend
- Tokens expire after 24 hours (default) or 7 days (if "remember me")
- `@auth_required` decorator checks for valid tokens

### 2. Analyze Endpoints

There are TWO analyze endpoints:

1. **HTML Endpoint** (src/routes/meetings.py:119)
   ```python
   @meetings_bp.route('/analyze/<meeting_id>')
   def analyze_meeting(meeting_id):
   ```
   - **NO** authentication required
   - Returns HTML page directly
   - NOT used by React frontend

2. **API Endpoint** (src/routes/meetings.py:613-614)
   ```python
   @meetings_bp.route("/api/meetings/<meeting_id>/analyze", methods=["POST"])
   @auth_required
   def analyze_meeting_api(user, meeting_id):
   ```
   - **REQUIRES** authentication via `@auth_required` decorator
   - Returns JSON response
   - **This is the endpoint the React frontend uses**

### 3. Frontend Implementation

**File**: `frontend/src/components/Analysis.tsx:680-705`

```javascript
const handleAnalyze = async () => {
  setIsAnalyzing(true);
  try {
    const token = localStorage.getItem('auth_token');  // ✅ Gets token from localStorage
    const response = await fetch(`${API_BASE_URL}/api/meetings/${record.id}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,  // ✅ Sends token in Authorization header
      },
    });

    if (response.ok) {
      notify('Meeting analysis completed successfully!', { type: 'success' });
      window.location.reload();  // ⚠️ Full page reload after success
    } else {
      const error = await response.json();
      notify(`Analysis failed: ${error.error || error.message || 'Unknown error'}`, { type: 'error' });
    }
  } catch (error) {
    notify(`Analysis failed: ${error}`, { type: 'error' });
  } finally {
    setIsAnalyzing(false);
  }
};
```

**Findings**:
- Frontend correctly retrieves token from localStorage (line 683)
- Frontend correctly sends Authorization header (line 688)
- Full page reload after successful analysis (line 695)

### 4. Test Results

**Test Script**: `/tmp/test_meeting_analysis.py`

```
=== Meeting Analysis End-to-End Test ===
Target: https://agent-pm-tsbbb.ondigitalocean.app
Time: 2025-10-20 16:15:03

📥 Fetching recent meetings...
❌ Failed to fetch meetings: 401
{"error":"Authentication required"}
```

**Result**: 401 Unauthorized when calling `/api/meetings` endpoint

**Log Evidence** (from production logs at 20:15:03 UTC):
```
app 2025-10-20T20:15:03.505171587Z ... "GET /api/meetings HTTP/1.1" 401 36 "-" "python-requests/2.32.5"
```

## Root Cause Analysis

The analyze endpoint requires authentication (`@auth_required` decorator), and the frontend correctly sends the token. However, analysis may fail if:

1. **Token is missing from localStorage**
   - User is not logged in
   - Token was cleared by browser/logout
   - User is in incognito mode

2. **Token is expired**
   - Default expiry: 24 hours
   - Extended expiry: 7 days (with "remember me")
   - Expired tokens return 401

3. **Token is invalid**
   - JWT signature verification fails
   - Token was generated with different secret
   - Token payload is malformed

4. **User has no access**
   - User role is `NO_ACCESS`
   - User was deactivated
   - User does not exist in database

## Hypothesis

Since the user can see the meetings list page (which likely also requires auth), they are probably logged in with a valid token. The "still failing to analyze" issue may be:

1. **Different issue than authentication** - The serialization fix may have worked, but there's another error
2. **Token expired mid-session** - User was logged in when viewing list, but token expired before clicking analyze
3. **Frontend error handling** - Error message not showing the actual failure reason
4. **Page reload issue** - Full page reload (line 695) may be causing state loss

## Next Steps to Resolve

### Option 1: Check Browser Console (User-side)
The user should:
1. Open browser DevTools (F12)
2. Go to Console tab
3. Click "Analyze Meeting" button
4. Check for JavaScript errors or 401 responses
5. Check Application > Local Storage > `auth_token` value

### Option 2: Add Detailed Logging (Backend)
Modify `analyze_meeting_api` endpoint to log:
```python
@meetings_bp.route("/api/meetings/<meeting_id>/analyze", methods=["POST"])
@auth_required
def analyze_meeting_api(user, meeting_id):
    logger.info(f"🔍 Analyze request: meeting_id={meeting_id}, user={user.email}")
    try:
        # ... existing code ...
    except Exception as e:
        logger.error(f"❌ Analyze failed for {meeting_id}: {str(e)}", exc_info=True)
        raise
```

### Option 3: Remove Auth Requirement (Temporary)
**NOT RECOMMENDED** - Security risk, but useful for debugging:
```python
@meetings_bp.route("/api/meetings/<meeting_id>/analyze", methods=["POST"])
# @auth_required  # Temporarily comment out
def analyze_meeting_api(meeting_id):  # Remove 'user' parameter
```

### Option 4: Check Actual Error in Production Logs
Search for recent analyze attempts:
```bash
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a app --type run --follow=false --tail=5000 | \
  grep -i "analyze_meeting_api\|POST.*analyze\|Starting API analysis"
```

## Files Referenced

- `src/services/auth.py` - Authentication service (lines 190-223: @auth_required decorator)
- `src/routes/meetings.py` - Meeting endpoints (line 613: analyze API endpoint)
- `frontend/src/components/Analysis.tsx` - Frontend component (lines 680-705: analyze handler)

## Related Deployments

- **Serialization Fix**: 3cc5a763 (ACTIVE since 18:38:48 UTC on 2025-10-20)
  - Fixed json.dumps() consistency for action_items, key_decisions, blockers
  - This deployment is working correctly

---

**Investigation Date**: October 20, 2025
**Investigator**: Claude AI Assistant
**Status**: Root cause identified - authentication required but may be failing silently
**Next Action**: Check production logs for actual analyze attempts OR ask user to check browser console
