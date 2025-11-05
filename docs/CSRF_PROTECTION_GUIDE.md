# CSRF Protection Guide

**Last Updated**: November 2024

## Overview

This application uses Flask-WTF's CSRFProtect to defend against Cross-Site Request Forgery attacks. However, our React frontend makes API calls using JWT authentication (not CSRF tokens), so **all API endpoints must be explicitly exempted from CSRF protection**.

## The Problem

Flask-WTF's `CSRFProtect` applies CSRF validation by default to ALL POST/PUT/DELETE requests. When the React frontend makes API calls without CSRF tokens, these requests return **400 Bad Request** errors unless the Blueprint is explicitly exempted.

### Common Symptom
```
Error: 400 Bad Request
PUT https://agent-pm.app/api/user/escalation-preferences 400
```

## The Solution: Blueprint Exemption Pattern

Every new Flask Blueprint with API endpoints MUST follow this 3-step pattern in `src/web_interface.py`:

### Step 1: Import the Blueprint
Around line 100-150:
```python
from src.routes.your_new_feature import your_feature_bp
```

### Step 2: Exempt from CSRF Protection
Around line 280-320, **BEFORE registering** the blueprint:
```python
# ✅ SECURITY: Exempt YourFeature endpoints from CSRF protection
# YourFeature endpoints are called from React frontend with JWT auth
csrf.exempt(your_feature_bp)
logger.info("✅ YourFeature endpoints exempted from CSRF protection")
```

### Step 3: Register the Blueprint
Around line 313-330:
```python
app.register_blueprint(your_feature_bp)
```

## Real Examples from Codebase

### Correct Pattern (src/web_interface.py lines 308-325)
```python
# ✅ SECURITY: Exempt Projects endpoints from CSRF protection
# Projects endpoints are called from React frontend (keywords, resource mappings)
csrf.exempt(projects_bp)
logger.info("✅ Projects endpoints exempted from CSRF protection")

# ✅ SECURITY: Exempt User endpoints from CSRF protection
# User endpoints (notification preferences, escalation preferences) are called from React frontend with JWT auth
csrf.exempt(user_bp)
logger.info("✅ User endpoints exempted from CSRF protection")

# Register blueprints
app.register_blueprint(todos_bp)
app.register_blueprint(meetings_bp)
app.register_blueprint(jira_bp)
app.register_blueprint(learnings_bp)
app.register_blueprint(scheduler_bp)
app.register_blueprint(slack_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(tempo_bp)
app.register_blueprint(user_bp)
```

### Currently Exempted Blueprints
All of these blueprints are properly exempted in `src/web_interface.py`:
- `health_bp` - Health check endpoints
- `scheduler_bp` - Scheduler endpoints (API key auth)
- `slack_bp` - Slack webhook endpoints (request signing)
- `jira_bp` - Jira API endpoints (Bearer token)
- `tempo_bp` - Tempo endpoints (JWT auth)
- `projects_bp` - Project management endpoints (JWT auth)
- `user_bp` - User preference endpoints (JWT auth)

## When to Exempt Blueprints

### Blueprints That NEED Exemption ✅
- All `/api/*` routes called from React frontend
- Routes using JWT/Bearer token authentication (not session-based)
- Routes that handle POST/PUT/DELETE requests from frontend
- Webhook endpoints with custom authentication (Slack, GitHub, etc.)

### Blueprints That DON'T Need Exemption ❌
- Routes that only render HTML templates (GET requests)
- Routes using session-based authentication with HTML forms
- Admin pages with CSRF tokens in forms

## Debugging CSRF Issues

### Quick Diagnostic

**Symptom**: 400 Bad Request on POST/PUT/DELETE from React frontend

**Step 1**: Check if blueprint is exempted
```bash
# Search for your blueprint in web_interface.py
grep "your_feature_bp" src/web_interface.py

# Look for TWO lines:
# 1. csrf.exempt(your_feature_bp)  ← MUST exist
# 2. app.register_blueprint(your_feature_bp)  ← MUST exist
```

**Step 2**: Verify exemption is BEFORE registration
The `csrf.exempt()` call must come **before** `app.register_blueprint()`, otherwise the exemption won't apply.

**Step 3**: Check browser console
```javascript
// In browser DevTools Console, check the failed request
// Look for CSRF-related error messages
```

### If Exemption is Missing

1. Add the exemption following the pattern above
2. Commit the change
3. Deploy to production
4. Verify the fix by testing the endpoint from the frontend

## Historical Issues Log

### Week 2 Auto-Escalation (November 2024)
**Issue**: 400 Bad Request when saving escalation preferences
**Root Cause**: `user_bp` blueprint was not exempted from CSRF protection
**Symptom**: `PUT /api/user/escalation-preferences` returned 400
**Fix**: Added `csrf.exempt(user_bp)` at line 315 (commit 95538ac)
**Files Changed**: `src/web_interface.py`

### Add your issues here as they occur...

## Checklist for New API Features

When adding a new API feature with POST/PUT/DELETE endpoints:

- [ ] Create Blueprint in `src/routes/`
- [ ] Import Blueprint in `src/web_interface.py` (around line 100-150)
- [ ] **Add `csrf.exempt(your_bp)` with descriptive comment** (around line 280-320)
- [ ] Register Blueprint with `app.register_blueprint(your_bp)` (around line 313-330)
- [ ] Test POST/PUT/DELETE endpoints from React frontend
- [ ] Verify no 400 errors in browser Network tab
- [ ] Check that success responses return expected data

## Testing CSRF Protection

### Local Testing
```bash
# Start backend
python src/web_interface.py

# Start frontend
cd frontend && PORT=4001 npm start

# Test API endpoint from frontend
# Open browser DevTools → Network tab
# Perform action that calls POST/PUT/DELETE endpoint
# Verify: Status 200 (not 400)
```

### Production Testing
```bash
# After deployment, test the endpoint
curl -X POST https://agent-pm.app/api/your-endpoint \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Should return 200/201, not 400
```

## Security Considerations

### Why We Use CSRF Protection
CSRF protection prevents malicious websites from making unauthorized requests on behalf of authenticated users. It's a critical security layer for web applications.

### Why API Endpoints Are Exempt
Our API endpoints use JWT authentication, which provides CSRF protection through:
1. **Token-based auth**: JWTs are stored in memory/localStorage, not cookies
2. **Same-Origin Policy**: React app and API are on the same origin
3. **Custom headers**: API requests include Authorization headers that browsers prevent from cross-origin requests

### When NOT to Exempt
Do NOT exempt endpoints that:
- Render HTML forms with session-based authentication
- Use cookies for authentication without custom headers
- Are publicly accessible without authentication

## Additional Resources

- [Flask-WTF CSRF Documentation](https://flask-wtf.readthedocs.io/en/stable/csrf.html)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [JWT vs CSRF](https://stackoverflow.com/questions/21357182/csrf-token-necessary-when-using-stateless-sessionless-authentication)

## Questions?

If you encounter CSRF issues not covered in this guide:
1. Check the Historical Issues Log above
2. Search for similar issues in `git log --grep="CSRF"`
3. Review `src/web_interface.py` for exemption patterns
4. Add your findings to this document for future reference
