# Pre-Deployment Validation Guide

## Quick Start: Run Before Every Deploy

```bash
# Simple one-liner to validate everything
./scripts/pre-deploy.sh
```

## What Gets Checked

### 1. **Unit & Integration Tests** ✅
```bash
python -m pytest tests/ -v
```

These tests would have caught the JSON serialization bug:
- `tests/models/test_processed_meeting_json.py` - Database JSON serialization
- `tests/models/test_dtos.py` - DTO conversions
- `tests/routes/` - API endpoint integration tests

### 2. **Frontend Build** 🏗️
```bash
cd frontend && npm run build
```

Catches TypeScript errors like the one we fixed earlier:
- Missing function parameters
- Type mismatches
- Import errors

### 3. **Type Checking** 🔎
```bash
python -m mypy src/ --ignore-missing-imports
```

Catches type-related bugs before they hit production.

### 4. **Linting** 🧹
```bash
python -m flake8 src/
```

Enforces code quality and catches common mistakes.

---

## Testing Strategy: The 3-Tier Approach

### Tier 1: Fast Local Tests (2-3 minutes)
Run before every commit:
```bash
# Quick validation
pytest tests/models/ tests/routes/ -v
npm run build --prefix frontend
```

### Tier 2: Full Test Suite (5-10 minutes)
Run before pushing to main:
```bash
./scripts/pre-deploy.sh
```

### Tier 3: Staging Environment (Manual)
Test on staging before production:
```bash
# Deploy to staging first
git push staging main

# Test critical flows:
# - Meeting analysis
# - Ticket creation
# - User authentication
```

---

## Common Issues and How Tests Catch Them

### ❌ JSON Serialization Bug (We Just Fixed)

**Issue**: Storing Python dict/list directly in PostgreSQL TEXT columns

**How to prevent**:
```python
# Test file: tests/models/test_processed_meeting_json.py
def test_processed_meeting_stores_json_as_strings(db_session):
    """This test would have caught the bug!"""
    meeting = ProcessedMeeting(
        action_items=json.dumps([{'title': 'Action 1'}]),  # Must be JSON string
        key_decisions=json.dumps(['Decision 1']),
        blockers=json.dumps(['Blocker 1'])
    )
    db_session.add(meeting)
    db_session.commit()  # Would fail if not JSON strings
```

**Run this test**:
```bash
pytest tests/models/test_processed_meeting_json.py -v
```

### ❌ TypeScript Type Errors

**Issue**: Missing parameters in function calls

**How to prevent**:
```bash
# Frontend build catches these
cd frontend && npm run build

# Look for errors like:
# TS2554: Expected 1 arguments, but got 0
```

### ❌ Database Schema Mismatches

**Issue**: Code expects columns that don't exist in production

**How to prevent**:
```bash
# 1. Test migrations locally first
alembic upgrade head

# 2. Run integration tests that touch the database
pytest tests/integration/test_production.py -v
```

---

## Setting Up Continuous Integration (Recommended)

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt

    - name: Run tests
      run: |
        pytest tests/ -v

    - name: Build frontend
      run: |
        cd frontend
        npm install
        npm run build

    - name: Type check
      run: |
        mypy src/ --ignore-missing-imports
```

This runs automatically on every push and blocks merges if tests fail.

---

## Manual Testing Checklist

Even with automated tests, manually verify these critical paths before deploying:

### Meeting Analysis Flow
- [ ] Navigate to /analysis page
- [ ] Click "Analyze" on a meeting
- [ ] Verify analysis completes without 500 errors
- [ ] Check that action items, decisions, and blockers display correctly

### Ticket Creation
- [ ] Select action items from analyzed meeting
- [ ] Create Jira tickets
- [ ] Verify tickets appear in Jira

### Database Operations
- [ ] Create a new TODO
- [ ] Update TODO status
- [ ] Delete TODO
- [ ] Verify no database errors in logs

---

## Staging Environment Setup (Recommended)

Create a staging environment that mirrors production:

1. **Duplicate DigitalOcean App**
   ```bash
   # Clone app spec
   doctl apps spec get YOUR_APP_ID > app-staging.yaml

   # Modify name and create staging app
   # Edit app-staging.yaml to change name to "agent-pm-staging"
   doctl apps create --spec app-staging.yaml
   ```

2. **Deploy to Staging First**
   ```bash
   # Push to staging branch
   git push staging main

   # Wait for deployment
   doctl apps list-deployments STAGING_APP_ID
   ```

3. **Smoke Test Staging**
   ```bash
   # Test critical endpoints
   curl https://agent-pm-staging.ondigitalocean.app/api/health

   # Manual testing in browser
   open https://agent-pm-staging.ondigitalocean.app
   ```

4. **Deploy to Production**
   ```bash
   # Only after staging tests pass
   git push origin main
   ```

---

## Time Savings Comparison

| Approach | Time to Find Bug | Time to Fix |
|----------|-----------------|-------------|
| **Find in Production** | Deploy time (5-10 min) + Manual testing + Debugging logs | 30-60 min |
| **Find with Tests** | Test run (2-3 min) | 5-10 min |
| **Find with CI/CD** | Automatic on commit | 5-10 min |

**Result**: Save 20-50 minutes per bug by catching issues early!

---

## Best Practices

1. **Write tests for bug fixes**: Every time you fix a bug, write a test that would have caught it
2. **Run tests before committing**: Make it a habit
3. **Use pre-commit hooks**: Automatically run tests on `git commit`
4. **Monitor test coverage**: Aim for 80%+ coverage on critical paths
5. **Keep tests fast**: Slow tests don't get run

---

## Next Steps

1. ✅ Run `./scripts/pre-deploy.sh` before next deployment
2. ✅ Review new test file: `tests/models/test_processed_meeting_json.py`
3. 🔄 Set up GitHub Actions for CI/CD
4. 🔄 Create staging environment for safer deployments
5. 🔄 Add more integration tests for critical flows

---

## Questions?

- Tests failing locally? Check that all dependencies are installed: `pip install -r requirements.txt`
- Need to skip a test temporarily? Use `@pytest.mark.skip`
- Want to run specific tests? Use `pytest tests/path/to/test.py::test_name -v`
