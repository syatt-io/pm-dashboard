# Production Data Loss Incident - November 10, 2025

## Incident Summary

**Date**: November 10, 2025
**Time**: 04:23-04:28 UTC
**Severity**: CRITICAL - Production data loss
**Status**: RESOLVED (schema restored, data lost)
**Root Cause**: Missing Python models caused Alembic autogenerate to drop production tables

## What Happened

### Timeline

1. **04:23 UTC** - Migration `1923d6037f6e` deployed to production
2. **04:23 UTC** - Migration executed: **DROPPED 3 critical tables**:
   - `project_keywords` (all keyword data)
   - `project_resource_mappings` (Slack/GitHub/Notion/Jira mappings)
   - `project_monthly_forecast` (budget and actual hours data)
3. **04:28 UTC** - Deployment failed, automatic rollback triggered
4. **04:28 UTC** - Rollback succeeded BUT **database migrations do not rollback automatically**
5. **~19:30 UTC** - User reported 500 errors on multiple endpoints
6. **23:58 UTC** - Tables restored (empty), Python models created

### Data Loss

| Table | Status | Data Lost |
|-------|--------|-----------|
| `project_keywords` | ✅ Restored (empty) | ALL keywords for 106 projects |
| `project_resource_mappings` | ✅ Restored (empty) | ALL resource mappings (Slack, GitHub, Notion, Jira) |
| `project_monthly_forecast` | ✅ Restored (empty) | ALL budget/actual hours tracking data |

**Total Records Lost**: Unknown (likely hundreds of rows across 3 tables)
**Time Period**: Data accumulated over weeks of production use

## Root Cause Analysis

### Primary Cause: Missing Python Models

The dropped tables had **NO corresponding Python model classes** defined in the codebase:
- ❌ No `ProjectKeyword` model
- ❌ No `ProjectResourceMapping` model
- ❌ No `ProjectMonthlyForecast` model

### How This Caused the Data Loss

1. Used `alembic revision --autogenerate` to create migration
2. Alembic compared database schema to Python models
3. Alembic found tables in database with no corresponding models
4. Alembic **incorrectly assumed these were orphaned tables**
5. Alembic generated DROP statements in the migration
6. Migration was not carefully reviewed before deployment
7. Migration executed in production, dropping tables and data

### Contributing Factors

1. **No model-database validation**: No CI check to verify all tables have models
2. **Insufficient migration review**: Auto-generated migration deployed without manual review
3. **No database backups**: DigitalOcean basic tier has no self-service backup/restore
4. **No pre-deployment testing**: Migration not tested on staging database first

## Impact

### Technical Impact
- 500 errors on multiple production endpoints for ~15 hours
- Complete loss of project keyword filtering functionality
- Complete loss of resource mapping data
- Complete loss of budget tracking data

### Business Impact
- Lost weeks of manually entered project configuration data
- Lost historical budget vs. actual hours tracking
- Users unable to use project filtering features
- Manual data re-entry required for all lost data

## Resolution Steps Taken

### 1. Schema Restoration ✅
- Created migration `def376e3c089` to recreate table structures
- Applied migration to production database
- Verified tables exist (but empty)

### 2. Model Creation ✅
Created missing Python models:
- `src/models/project_keyword.py`
- `src/models/project_resource_mapping.py`
- `src/models/project_monthly_forecast.py`
- Updated `src/models/__init__.py` to import all models

### 3. Prevention Measures ✅
- All models now properly defined and imported
- Alembic will NEVER drop these tables again
- Created this incident documentation

### 4. Data Recovery ⚠️ NOT COMPLETE
- ❌ No backup available to restore from
- ⚠️ Manual data re-entry required for:
  - Project keywords
  - Resource mappings (Slack, GitHub, Notion, Jira)
- 🔄 Potential partial recovery:
  - Monthly forecast data can be backfilled from Tempo API

## Lessons Learned

### What Went Wrong

1. **Missing Model Definitions**
   - Critical tables existed in database but not in code
   - No process to ensure models match database schema

2. **Blind Trust in Autogenerate**
   - Used `alembic revision --autogenerate` without review
   - Assumed autogenerate was always safe
   - Did not verify what the migration would do

3. **No Safety Net**
   - No database backups
   - No staging environment testing
   - No CI checks for model-database parity

4. **Insufficient Testing**
   - Migration not tested locally before production
   - No verification of what tables would be affected

## Prevention Measures (MANDATORY)

### 1. NEVER Use Autogenerate Without Review ⚠️

```bash
# WRONG - DO NOT DO THIS
alembic revision --autogenerate -m "changes"
alembic upgrade head  # DON'T DEPLOY WITHOUT REVIEW!

# CORRECT - ALWAYS DO THIS
alembic revision --autogenerate -m "changes"
# 1. Open the generated migration file
# 2. Review EVERY LINE
# 3. Check for any DROP statements
# 4. Verify against database schema
# 5. Test locally first
# 6. Then deploy to production
```

### 2. Model-Database Validation (TO IMPLEMENT)

Create CI check to verify:
- Every table in database has a corresponding model
- Every model is imported in `src/models/__init__.py`
- Run before allowing migrations

```python
# Pseudo-code for validation script
def validate_models():
    db_tables = get_all_tables_from_database()
    model_tables = get_all_model_tablenames()

    missing_models = db_tables - model_tables
    if missing_models:
        raise Error(f"Tables without models: {missing_models}")
```

### 3. Migration Review Checklist

Before deploying ANY migration:
- [ ] Reviewed auto-generated code line by line
- [ ] No DROP statements (unless intentional and approved)
- [ ] No DELETE statements (unless intentional and approved)
- [ ] Tested on local database
- [ ] Verified against production schema
- [ ] Confirmed with stakeholder if dropping/modifying data

### 4. Database Backup Strategy

- [ ] Enable automated backups (upgrade DigitalOcean tier if needed)
- [ ] Test backup restoration process monthly
- [ ] Document backup/restore procedures
- [ ] Keep 30-day backup retention

### 5. Staging Environment

- [ ] Create staging database that mirrors production
- [ ] Test ALL migrations on staging first
- [ ] Require successful staging deploy before production

## Recovery Plan (Still Needed)

### Immediate (Done)
- ✅ Restore table schemas
- ✅ Create Python models
- ✅ Fix 500 errors

### Short-term (To Do)
- [ ] Backfill `project_monthly_forecast` from Tempo API
- [ ] Create UI for manual re-entry of resource mappings
- [ ] Create UI for manual re-entry of keywords

### Long-term (To Do)
- [ ] Implement model-database validation CI check
- [ ] Set up proper database backups
- [ ] Create staging environment
- [ ] Document migration procedures
- [ ] Add pre-commit hook to warn on DROP statements in migrations

## Files Changed

### Emergency Fixes (Deployed)
- `alembic/versions/def376e3c089_restore_project_resource_mappings_and_.py` - Restore tables
- `src/models/project_keyword.py` - New model
- `src/models/project_resource_mapping.py` - New model
- `src/models/project_monthly_forecast.py` - New model
- `src/models/__init__.py` - Import new models

### Problematic Migration (ROOT CAUSE)
- `alembic/versions/1923d6037f6e_add_project_projectcharacteristics_and_.py`
  - Lines 61, 64, 68: DROP statements that destroyed data

## Communication

- User notified of data loss
- User notified of resolution steps
- Manual data re-entry will be required
- Preventive measures implemented

## Sign-off

**Incident Handler**: Claude (AI Assistant)
**Reviewer**: [To be filled by human reviewer]
**Approval**: [To be filled by stakeholder]

---

**CRITICAL REMINDER**: NEVER use `alembic revision --autogenerate` without manual review of EVERY line of the generated migration file. Always verify what the migration will do before deploying to production.
