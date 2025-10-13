# Production Deployment Checklist

## ✅ Completed Fixes (Ready to Deploy)

### Critical Issues Fixed

1. **✅ Database Backups Enabled**
   - Changed `.do/app.yaml` → `production: true`
   - Automated daily backups now active
   - **Action Required**: Verify backups after deployment

2. **✅ Celery Result Expiration**
   - Added `result_expires=3600` to prevent database bloat
   - Results auto-cleaned after 1 hour
   - Added `result_backend_max_connections=10`

3. **✅ CORS Configuration Hardened**
   - Production: Single domain only (`WEB_BASE_URL`)
   - Development: Multiple localhost ports for testing
   - Proper environment-based configuration

4. **✅ Removed Dev Secret Fallback**
   - JWT_SECRET_KEY now always required (fail-fast)
   - No insecure fallbacks
   - **Action Required**: Ensure JWT_SECRET_KEY is set in production

5. **✅ Rate Limiting Implemented**
   - Flask-Limiter added to `requirements.txt`
   - Global limits: 1000/day, 200/hour
   - Auth endpoints: 10 login attempts/minute
   - Backfill endpoints:
     - Jira/Notion: 3/hour
     - Tempo/Fireflies: 5/hour
   - Uses Redis in production, memory in development

6. **✅ Input Validation with Pydantic**
   - All backfill endpoints validated
   - Date format validation (YYYY-MM-DD)
   - Range validation (1-3650 days)
   - Proper error responses with validation details

---

## 🔄 Deploy These Changes

### Step 1: Install New Dependencies
```bash
# On your development machine
pip install flask-limiter>=3.5.0

# Verify it works locally
pytest tests/ -v
```

### Step 2: Test Locally
```bash
# Set required environment variables
export JWT_SECRET_KEY="your-32-char-secret-here"

# Run the app
python src/web_interface.py

# Test rate limiting
curl -X POST http://localhost:4000/api/backfill/jira?days=365 \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

### Step 3: Deploy to DigitalOcean
```bash
# Commit changes
git add .
git commit -m "Production hardening: backups, rate limiting, input validation"

# Push to trigger auto-deployment
git push origin main

# Monitor deployment
doctl apps list
doctl apps logs <app-id> --follow
```

### Step 4: Verify After Deployment

#### Database Backups
```bash
# Check database is in production mode
doctl databases list

# Verify backup schedule
doctl databases backups list <database-id>
```

#### Rate Limiting
```bash
# Test rate limiting works
for i in {1..15}; do
  curl -X POST https://your-app.com/api/auth/google \
    -H "Content-Type: application/json" \
    -d '{"credential":"test"}'
done
# Should see 429 (Too Many Requests) after 10 attempts
```

#### Input Validation
```bash
# Test invalid input is rejected
curl -X POST "https://your-app.com/api/backfill/jira?days=9999" \
  -H "X-Admin-Key: $ADMIN_API_KEY"
# Should return 400 with validation error

# Test valid input works
curl -X POST "https://your-app.com/api/backfill/jira?days=365" \
  -H "X-Admin-Key: $ADMIN_API_KEY"
# Should return 202 Accepted
```

---

## ⚠️ Remaining Tasks (High Priority)

### 1. Fix SQL String Formatting in Migrations
**Risk**: Potential SQL injection pattern (currently safe, but dangerous practice)

**Location**: `src/web_interface.py:302`
```python
# BAD (current):
conn.execute(text(f"ALTER TABLE processed_meetings ADD COLUMN {column_name} {column_type}"))

# GOOD (use Alembic migrations instead):
# See alembic/versions/*.py for examples
```

**Action Required**:
- Move all schema changes to Alembic migrations
- Never use f-strings with SQL
- Run migrations in CI/CD before app deployment

### 2. Document Alembic Migration Strategy
**File**: Create `docs/MIGRATIONS.md`

**Content**:
```markdown
# Database Migrations Strategy

## Creating Migrations
```bash
# Auto-generate migration
alembic revision --autogenerate -m "Add new column"

# Edit migration file in alembic/versions/
# Review SQL statements carefully
```

## Running Migrations
```bash
# In CI/CD (before app deployment)
alembic upgrade head

# Check current version
alembic current

# Rollback if needed
alembic downgrade -1
```

## Migration Best Practices
1. Always review auto-generated migrations
2. Test rollback before deploying
3. Keep schema backward compatible for 1 release
4. Never run migrations in worker processes
```

---

## 📋 Next Steps (Medium Priority)

### 3. Improve Error Handling
- Don't expose stack traces in production
- Use structured logging with request IDs
- Implement proper error monitoring (Sentry/Datadog)

### 4. Deep Health Checks
- Add PostgreSQL connection check
- Add Redis connection check
- Add Celery worker health check
- Add Pinecone connectivity check

### 5. Increase Test Coverage
- Current: ~14% file coverage (18 tests / 125 files)
- Target: 70%+ with integration tests
- Add auth flow tests, API endpoint tests, Celery task tests

---

## 🔒 Security Recommendations

### Short-term
1. **Rotate Admin API Key** - Current key is in `.do/app.yaml`
2. **Use Service Account for Jira** - Not personal email
3. **Enable 2FA on DigitalOcean** - Protect infrastructure access

### Long-term
1. **Secret Management** - Migrate to AWS Secrets Manager or Vault
2. **Security Audit** - Third-party penetration testing
3. **Dependency Scanning** - Add Dependabot or Snyk to CI/CD

---

## 📊 Monitoring Checklist

After deployment, monitor:
- [ ] Application logs for errors
- [ ] Database connection pool usage
- [ ] Redis rate limiter storage
- [ ] Celery task queue length
- [ ] API response times
- [ ] Rate limit hits (429 responses)

---

## 🆘 Rollback Plan

If deployment fails:
```bash
# 1. Revert database to production: false (if backups cause issues)
git revert <commit-sha>
git push

# 2. Check for breaking changes
doctl apps logs <app-id> --type=run --tail=500

# 3. Restore database from backup if needed
doctl databases backups list <database-id>
doctl databases backups restore <database-id> <backup-id>
```

---

## ✅ Definition of Done

This deployment is considered successful when:
- [ ] Application starts without errors
- [ ] All health checks pass
- [ ] Rate limiting blocks excessive requests
- [ ] Input validation rejects invalid parameters
- [ ] Database backups are being created
- [ ] No increase in error rate
- [ ] Response times remain acceptable
