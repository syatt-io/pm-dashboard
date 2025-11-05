# Troubleshooting Guide

Common issues and their solutions for the Agent PM application.

## Table of Contents
- [Fireflies Integration](#fireflies-integration)
- [Jira Integration](#jira-integration)
- [Flask/Template Issues](#flasktemplate-issues)
- [Docker Issues](#docker-issues)
- [Database Issues](#database-issues)
- [CSRF Protection](#csrf-protection)

---

## Fireflies Integration

### Issue: API Returns 400 Error with ISO Timestamp
**Symptom**: Fireflies API rejects date queries with ISO 8601 formatted timestamps

**Root Cause**: Fireflies API expects timestamps in milliseconds, not ISO format

**Solution**: Convert datetime to milliseconds since epoch
```python
# ❌ Wrong - ISO format
start_date = datetime.now().isoformat()

# ✅ Correct - Milliseconds
start_date = int(datetime.now().timestamp() * 1000)

# When receiving timestamps from Fireflies
meeting_date = datetime.fromtimestamp(date_val / 1000)
```

**Files Affected**: `src/integrations/fireflies.py`

---

## Jira Integration

### Issue: User API Endpoint Returns 404
**Symptom**: `/rest/api/3/user/assignable/search` returns 404 Not Found

**Root Cause**: Endpoint deprecated or not available in your Jira instance

**Solution**: Use alternative endpoints
```python
# ❌ May not work
/rest/api/3/user/assignable/search

# ✅ Try these instead
/rest/api/3/user/search
/rest/api/3/user/assignable/multiProjectSearch
```

**Files Affected**: `src/integrations/jira_mcp.py`

### Issue: Missing Tempo Hours Compared to UI
**Symptom**: Hours tracked in Tempo don't match when summed via API

**Root Cause**: Complex data structure and filtering issues

**Solution**: See detailed guide at:
```
/Users/msamimi/syatt/projects/dev-learnings/Jira-integrations/TEMPO_API_INTEGRATION_GUIDE.md
```

**Important Notes**:
- Use Tempo REST APIs directly, not MCP tools
- Don't use MCP tools as fallback (data will be wrong)
- Refer to external guide for complete solution

---

## Flask/Template Issues

### Issue: Template Not Found Error
**Symptom**:
```
jinja2.exceptions.TemplateNotFound: dashboard.html
```

**Root Cause**: Flask looking in wrong directory for templates

**Solution**: Set template_dir to parent directory
```python
# In web_interface.py
template_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'templates'
)
app = Flask(__name__, template_folder=template_dir)
```

**Files Affected**: `src/web_interface.py`

**Directory Structure**:
```
agent-pm/
├── src/
│   └── web_interface.py  ← Flask app here
└── templates/            ← Templates here (one level up)
    ├── base.html
    ├── dashboard.html
    └── ...
```

---

## Docker Issues

### Issue: Can't Install Docker with Homebrew
**Symptom**: Docker Desktop installation fails or permission issues on macOS

**Root Cause**: Docker Desktop requires specific permissions and setup on macOS

**Solution**: Use Colima as Docker alternative
```bash
# Install Colima
brew install colima

# Start Colima
colima start

# Run services
docker-compose up -d

# Stop Colima when done
colima stop
```

**Why Colima?**
- Lightweight alternative to Docker Desktop
- Works seamlessly with docker-compose
- Better resource management on macOS
- No licensing issues

---

## Database Issues

### Issue: Missing Columns After Updates
**Symptom**:
```
sqlalchemy.exc.OperationalError: no such column: users.enable_auto_escalation
```

**Root Cause**: Database schema out of sync with SQLAlchemy models

**Solution Option 1: Run Migration** (Production)
```bash
# Check current migration status
alembic current

# Run pending migrations
alembic upgrade head
```

**Solution Option 2: Reset Database** (Development only)
```bash
# ⚠️ WARNING: This deletes all data!
rm pm_agent.db

# Restart application to recreate tables
python src/web_interface.py
```

**Files Affected**: `src/models.py`, `alembic/versions/*.py`

**When to Use Each Option**:
- **Migration**: Production, preserves data
- **Reset**: Local development, fresh start

### Issue: Database Locked Error
**Symptom**:
```
sqlite3.OperationalError: database is locked
```

**Root Cause**: Multiple processes accessing SQLite simultaneously

**Solution**:
```bash
# Check for processes using the database
lsof pm_agent.db

# Kill processes if necessary
kill <PID>

# Or restart the application
```

**Long-term Solution**: Consider PostgreSQL for production (already configured in DigitalOcean)

---

## CSRF Protection

### Issue: 400 Bad Request on API Calls
**Symptom**: POST/PUT/DELETE requests from React frontend return 400

**Quick Fix**: Check if blueprint is exempted
```bash
grep "your_feature_bp" src/web_interface.py
# Look for: csrf.exempt(your_feature_bp)
```

**Detailed Guide**: See [CSRF Protection Guide](CSRF_PROTECTION_GUIDE.md) for complete troubleshooting steps.

---

## General Debugging Tips

### Enable Debug Logging
```python
# In web_interface.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Environment Variables
```bash
# Verify all required vars are set
env | grep -E "FIREFLIES|JIRA|SLACK|OPENAI"

# Check specific variable
echo $FIREFLIES_API_KEY
```

### Test API Endpoints
```bash
# Test backend endpoint
curl -X GET http://localhost:4000/api/jira/projects \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test with verbose output
curl -v -X POST http://localhost:4000/api/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "Test TODO"}'
```

### Check Logs
```bash
# Local development
tail -f logs/app.log

# Production (DigitalOcean)
doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a --type=run --follow
```

---

## Need More Help?

1. Check [CLAUDE.md](../CLAUDE.md) for project overview
2. See [DEPLOYMENT_TROUBLESHOOTING_2025-10-31.md](DEPLOYMENT_TROUBLESHOOTING_2025-10-31.md) for deployment issues
3. Review [CSRF_PROTECTION_GUIDE.md](CSRF_PROTECTION_GUIDE.md) for CSRF issues
4. Search git history: `git log --grep="your issue"`
5. Check GitHub issues: Look for similar problems in the repository
