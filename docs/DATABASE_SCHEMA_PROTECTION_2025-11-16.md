# DATABASE SCHEMA PROTECTION ANALYSIS

**Generated:** 2025-11-16
**Purpose:** Ensure no production tables/columns are ever dropped by migrations again

---

## EXECUTIVE SUMMARY

- **Total Production Tables:** 41
- **Total Production Columns:** 404
- **Total Migration Files:** 41
- **Total Drop Commands Found:** 95+ (tables, columns, indexes)

### CRITICAL ACTIONS TAKEN

1. ✅ Commented out 13 dangerous `drop_column` commands in migrations `1923d6037f6e` and `2d04705c7c32`
2. ✅ Created restoration migration `2069b8009924` to recover dropped columns
3. ⚠️ All future migrations **MUST** be reviewed for drop commands before deployment

---

## PRODUCTION SCHEMA SNAPSHOT (Current State)

### Tables in Production (41 total)

1. alembic_version
2. backfill_progress
3. celery_taskmeta
4. celery_tasksetmeta
5. characteristic_impact_baselines
6. epic_allocation_baselines
7. epic_baseline_mappings
8. epic_baselines
9. epic_budgets
10. epic_categories
11. epic_category_mappings
12. epic_forecasts
13. epic_hours
14. escalation_history
15. escalation_preferences
16. feedback_items
17. job_executions
18. learnings
19. meeting_metadata
20. monthly_reconciliation_reports
21. proactive_insights
22. processed_meetings
23. project_characteristics
24. project_digest_cache
25. project_forecasting_config
26. project_keywords
27. project_monthly_forecast
28. project_resource_mappings
29. **projects** (CRITICAL - 16 columns including restored ones)
30. slack_sessions
31. standard_epic_templates
32. system_settings
33. template_epics
34. template_tickets
35. tempo_worklogs
36. temporal_pattern_baselines
37. time_tracking_compliance
38. **todo_items** (CRITICAL - source column restored)
39. user_notification_preferences
40. user_watched_projects
41. users

### CRITICAL COLUMNS THAT WERE DROPPED AND RESTORED

The following columns were **permanently deleted** on 2025-11-16 and restored with default values (actual data **LOST**):

#### projects table (11 columns)
- `project_work_type` → restored with default `'project-based'`
- `total_hours` → restored with default `0`
- `cumulative_hours` → restored with default `0`
- `weekly_meeting_day` → restored as `NULL`
- `retainer_hours` → restored with default `0`
- `send_meeting_emails` → restored with default `false`
- `start_date` → restored as `NULL`
- `launch_date` → restored as `NULL`
- `description` → restored as `NULL`
- `lead` → restored as `NULL`
- `show_budget_tab` → restored with default `true`

#### todo_items table (1 column)
- `source` → restored as `NULL`

**⚠️ NOTE:** Column structures were restored via migration `2069b8009924` but **ALL actual data values were permanently LOST**.

---

## DANGEROUS DROP COMMANDS IN MIGRATIONS (Protected)

### Migration: `1923d6037f6e_add_project_projectcharacteristics_and_.py`

- **Status:** ✅ PROTECTED (drop_column commands commented out)
- **Lines:** 164-184
- **Protected Columns:**
  - `projects.description`
  - `projects.send_meeting_emails`
  - `projects.weekly_meeting_day`
  - `projects.project_work_type`
  - `projects.launch_date`
  - `projects.lead`
  - `projects.show_budget_tab`
  - `projects.total_hours`
  - `projects.cumulative_hours`
  - `projects.retainer_hours`
  - `projects.start_date`
  - `todo_items.source`

### Migration: `2d04705c7c32_add_template_epic_and_ticket_tables_for_.py`

- **Status:** ✅ PROTECTED (drop_column commands commented out)
- **Lines:** 80-91
- **Protected Columns:**
  - `projects.project_work_type`
  - `projects.weekly_meeting_day`
  - `projects.description`
  - `projects.retainer_hours`
  - `projects.launch_date`
  - `projects.total_hours`
  - `projects.start_date`
  - `projects.cumulative_hours`
  - `projects.send_meeting_emails`
  - `todo_items.source`

---

## ALL DROP COMMANDS FOUND IN MIGRATIONS (Requires Review)

The following migrations contain drop commands that need to be reviewed:

### 1. `f8fed84667ca` - processed_meetings columns
- **Lines 45-49:** DROP COLUMN (5 columns)
- **Status:** ⚠️ NEEDS REVIEW

### 2. `d8101d785508` - users notification columns
- **Lines 58-59:** DROP COLUMN (2 columns)
- **Status:** ⚠️ NEEDS REVIEW

### 3. `4246ddc8b889` - projects.slack_channel
- **Line 26:** DROP COLUMN
- **Status:** ⚠️ VERIFY deprecated

### 4. `cbcdb0342f53` - Multiple tables/columns
- **Lines 77-119:** Complex migration with many drops
- **Status:** ⚠️ NEEDS REVIEW

### 5. `2f3e386f9b02` - system_settings
- **Line 42:** DROP TABLE `system_settings`
- **Status:** 🚨 **VERIFY** - `system_settings` **EXISTS** in production!

### 6. `feac5fe7245d` - epic_forecasts
- **Lines 57-58:** DROP TABLE `epic_forecasts`
- **Status:** 🚨 **VERIFY** - `epic_forecasts` **EXISTS** in production!

### 7. `4ea73a1de7f0` - system_settings column
- **Line 39:** DROP COLUMN `epic_auto_update_enabled`
- **Status:** ⚠️ NEEDS REVIEW

### 8. `8e244eaab655` - epic_budgets
- **Lines 99-114:** DROP TABLE and columns
- **Status:** 🚨 **VERIFY** - `epic_budgets` **EXISTS** in production!

### 9. `9391760ed2b5` - project_keywords
- **Lines 44-47:** DROP TABLE `project_keywords`
- **Status:** 🚨 **VERIFY** - `project_keywords` **EXISTS** in production!

### 10. `a8873baa32a5` - projects.send_meeting_emails
- **Line 37:** DROP COLUMN
- **Status:** 🚨 **CONFLICT** - This column was **RESTORED** in migration `2069b8009924`!

And many more... (see full grep output in analysis)

---

## CRITICAL FINDINGS & RECOMMENDATIONS

### 🚨 IMMEDIATE ACTION REQUIRED

#### 1. CONFLICTING MIGRATIONS DETECTED

Multiple migrations have `downgrade()` functions that would DROP tables that currently **EXIST** in production:

- `system_settings`
- `epic_forecasts`
- `epic_budgets`
- `project_keywords`
- `tempo_worklogs`
- `escalation_preferences`
- `escalation_history`
- `meeting_metadata`
- `user_notification_preferences`
- `proactive_insights`
- `epic_categories`

**⚠️ This suggests:** These migrations were applied, then later migrations re-created these tables. The drop commands in `downgrade()` functions are **DANGEROUS** if someone accidentally runs `alembic downgrade`.

#### 2. TABLES WITH DROP COMMANDS BUT EXIST IN PRODUCTION

The following tables have `drop_table` commands in migrations but **EXIST** in current production schema:

| Table | Migration with DROP | Status |
|-------|-------------------|---------|
| system_settings | 2f3e386f9b02 | ✅ EXISTS in prod |
| epic_forecasts | feac5fe7245d | ✅ EXISTS in prod |
| epic_budgets | 8e244eaab655 | ✅ EXISTS in prod |
| project_keywords | 9391760ed2b5 | ✅ EXISTS in prod |
| tempo_worklogs | 128f39fae2ea | ✅ EXISTS in prod |
| escalation_preferences | 3b36763ff547 | ✅ EXISTS in prod |
| escalation_history | 3b36763ff547 | ✅ EXISTS in prod |
| meeting_metadata | 80cb362b10db | ✅ EXISTS in prod |
| user_notification_preferences | 80cb362b10db | ✅ EXISTS in prod |
| proactive_insights | 80cb362b10db | ✅ EXISTS in prod |
| epic_categories | b74d972657e5 | ✅ EXISTS in prod |

### 3. RECOMMENDED SAFEGUARDS

#### a) Immediate Actions
- [ ] Comment out ALL `drop_table` and `drop_column` commands in `downgrade()` functions for tables/columns that exist in production
- [ ] Add warning comments to all drop commands explaining the risk
- [ ] Create migration review checklist

#### b) Process Improvements
- [ ] Implement pre-deployment migration review checklist
- [ ] **NEVER** run `alembic downgrade` in production
- [ ] Add database backup verification before any migration
- [ ] Require explicit approval for any drop commands

#### c) Technical Safeguards
- [ ] Consider creating a pre-commit hook that flags drop commands
- [ ] Add migration testing against production schema snapshot
- [ ] Implement schema version comparison before deployment
- [ ] Add CI/CD check that compares migration changes against production schema

---

## MIGRATION BEST PRACTICES (Going Forward)

1. ❌ **NEVER** use `alembic revision --autogenerate` without thorough review
2. ❌ **NEVER** include `drop_column` or `drop_table` in `upgrade()` without explicit approval
3. ✅ **ALWAYS** verify production schema before applying migrations
4. ✅ **ALWAYS** backup database before migrations
5. ❌ **NEVER** run `downgrade()` in production
6. ✅ **ALWAYS** comment dangerous commands instead of deleting migration files
7. ✅ **ALWAYS** use migration review checklist before merging

---

## INCIDENT POSTMORTEM

### Date
2025-11-16

### Incident
Production data loss due to migration dropping 12 critical columns

### Root Cause
- Migration `1923d6037f6e` contained `drop_column` commands in `upgrade()` function
- Migration was autogenerated and not properly reviewed
- Drop commands executed in production, permanently deleting column data
- This is the **SECOND** time this has happened

### Impact
- 11 project table columns dropped (`project_work_type`, `total_hours`, etc.)
- 1 `todo_items` column dropped (`source`)
- **ALL** data in these columns **permanently lost**
- Column structures restored via migration `2069b8009924` but data gone
- Required manual work to identify and restore affected columns
- User extremely frustrated: *"this is fucking crazy, same thing happened last week"*

### Timeline
1. Migration `1923d6037f6e` deployed to production
2. Drop commands executed, deleting 12 columns
3. User discovered projects not showing in UI
4. Investigation revealed missing `project_work_type` column
5. Further analysis revealed 11 more missing columns
6. Created emergency restoration migration `2069b8009924`
7. Commented out all dangerous drop commands
8. Conducted comprehensive schema analysis

### Prevention Measures Implemented
1. ✅ Commented out all dangerous drop commands in affected migrations
2. ✅ Created this comprehensive schema protection document
3. ✅ Updated `CLAUDE.md` with explicit instructions about NEVER dropping data
4. ⚠️ Need to implement automated safeguards (pre-commit hooks, CI/CD checks)

### User Directive
> "do a very, very thorough analysis of the current production DB and make sure all migrations scripts have ALL our current DB tables and columns so we never lose another Table or Column ever ever again, this is seriously important as its happened twice now"

### Lessons Learned
1. Autogenerated migrations **MUST** be manually reviewed before deployment
2. Drop commands should **NEVER** be in `upgrade()` functions for production data
3. Need automated checks to prevent this in the future
4. Database backups are critical but don't prevent lost work hours
5. User instructions in `CLAUDE.md` were ignored - need technical enforcement

---

## MIGRATION REVIEW CHECKLIST

Use this checklist **BEFORE** deploying any migration:

- [ ] Migration file manually reviewed (not blindly accepted from autogenerate)
- [ ] No `drop_table` commands in `upgrade()` for existing production tables
- [ ] No `drop_column` commands in `upgrade()` for existing production columns
- [ ] All `drop_*` commands in `downgrade()` commented out with warnings
- [ ] Migration tested against production schema snapshot
- [ ] Database backup verified before deployment
- [ ] Rollback plan documented
- [ ] User approval obtained for any schema changes affecting data

---

## APPENDIX: Full Production Schema

See `/tmp/full_db_schema.txt` for complete list of all 404 columns across 41 tables.

---

**Document Owner:** AI/DevOps Team
**Last Updated:** 2025-11-16
**Next Review:** Before every migration deployment
