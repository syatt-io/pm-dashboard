# Database Migrations Guide - Production Schema Updates

## Problem Statement

**Issue**: DigitalOcean App Platform doesn't automatically run Alembic migrations on deployment.

**Current Behavior**:
- App runs custom SQL files from `/workspace/migrations/` directory during startup
- Alembic migrations in `alembic/versions/` are **NOT** executed automatically
- App has insufficient permissions for some DDL operations (e.g., `ALTER TABLE`, `DROP COLUMN`)

## Recommended Process for Production Schema Changes

### Step 1: Create the Migration Locally

Create an Alembic migration as usual:

```bash
# Generate migration file
alembic revision -m "description_of_change"

# Edit the generated file in alembic/versions/
# Implement upgrade() and downgrade() functions
```

**Example Migration**:
```python
def upgrade() -> None:
    """Add include_context field to project_digest_cache."""
    op.add_column(
        'project_digest_cache',
        sa.Column('include_context', sa.Boolean(), nullable=False, server_default='0')
    )
    op.create_index(
        'idx_digest_cache_composite',
        'project_digest_cache',
        ['project_key', 'days', 'include_context', 'created_at'],
        unique=False
    )

def downgrade() -> None:
    """Remove include_context field."""
    op.drop_index('idx_digest_cache_composite', table_name='project_digest_cache')
    op.drop_column('project_digest_cache', 'include_context')
```

### Step 2: Update the Model

Update the SQLAlchemy model in `src/models/`:

```python
class ProjectDigestCache(Base):
    __tablename__ = 'project_digest_cache'

    id = Column(Integer, primary_key=True)
    project_key = Column(String(50), nullable=False)
    days = Column(Integer, nullable=False)
    include_context = Column(Boolean, nullable=False, default=False)  # New field
    digest_data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

### Step 3: Create SQL Migration File (For Production)

Extract the SQL from your Alembic migration and create a `.sql` file:

```bash
# Create SQL file in migrations directory
touch migrations/add_include_context_column.sql
```

**migrations/add_include_context_column.sql**:
```sql
-- Add include_context column to project_digest_cache table
ALTER TABLE project_digest_cache ADD COLUMN IF NOT EXISTS include_context BOOLEAN NOT NULL DEFAULT FALSE;

-- Create composite index for efficient cache lookups
CREATE INDEX IF NOT EXISTS idx_digest_cache_composite
ON project_digest_cache (project_key, days, include_context, created_at);
```

**Important Notes**:
- Use `IF NOT EXISTS` / `IF EXISTS` to make migrations idempotent
- Use `ADD COLUMN ... DEFAULT` for NOT NULL columns to avoid breaking existing rows
- Test SQL syntax is PostgreSQL-compatible (production uses Postgres 15)

### Step 4: Apply Migration to Production Database

#### Option A: Direct psql Connection (Recommended for Critical Changes)

```bash
# 1. Get database cluster ID
doctl databases list

# Output:
# ID                                      Name
# 8dbad607-69bb-4de4-a098-63b1cf557910    app-3e774e03-7ffb-4138-a401-13c2fd3f09b4

# 2. Get connection details
doctl databases connection 8dbad607-69bb-4de4-a098-63b1cf557910 --format Host,Port,User,Password,Database

# Output:
# Host                                                                                  Port     User       Password                    Database
# app-3e774e03-7ffb-4138-a401-13c2fd3f09b4-do-user-9115787-0.m.db.ondigitalocean.com    25060    doadmin    AVNS_xxx...                defaultdb

# 3. Connect and run migration (using agentpm-db database)
PGPASSWORD='AVNS_xxx...' psql \
  -h app-3e774e03-7ffb-4138-a401-13c2fd3f09b4-do-user-9115787-0.m.db.ondigitalocean.com \
  -p 25060 \
  -U doadmin \
  -d "agentpm-db" \
  < migrations/add_include_context_column.sql

# 4. Verify the changes
PGPASSWORD='AVNS_xxx...' psql \
  -h app-3e774e03-7ffb-4138-a401-13c2fd3f09b4-do-user-9115787-0.m.db.ondigitalocean.com \
  -p 25060 \
  -U doadmin \
  -d "agentpm-db" \
  <<'EOF'
\d project_digest_cache
EOF
```

**Verification Output**:
```
                                           Table "public.project_digest_cache"
     Column      |            Type             | Collation | Nullable |                     Default
-----------------+-----------------------------+-----------+----------+--------------------------------------------------
 id              | integer                     |           | not null | nextval('project_digest_cache_id_seq'::regclass)
 project_key     | character varying(50)       |           | not null |
 days            | integer                     |           | not null |
 digest_data     | text                        |           | not null |
 created_at      | timestamp without time zone |           | not null |
 include_context | boolean                     |           | not null | false
Indexes:
    "project_digest_cache_pkey" PRIMARY KEY, btree (id)
    "idx_digest_cache_composite" btree (project_key, days, include_context, created_at)
```

#### Option B: Deploy via Custom SQL Files (For Non-Critical Changes)

1. **Add SQL file to `migrations/` directory**
2. **Commit and push changes**
3. **App will attempt to run SQL on next deployment**

**Limitations**:
- May fail due to insufficient permissions
- Runs during app startup (not ideal for long-running migrations)
- No rollback mechanism

### Step 5: Commit All Changes

```bash
# Commit migration, model changes, and SQL file
git add alembic/versions/*.py
git add src/models/__init__.py
git add migrations/add_include_context_column.sql

git commit -m "Add include_context field to project_digest_cache

- Created Alembic migration: 39ec1875570b
- Updated ProjectDigestCache model
- Added SQL migration for production deployment
- Created composite index for cache isolation

🤖 Generated with Claude Code"

git push
```

## Troubleshooting Common Issues

### Issue 1: Permission Denied Errors

**Error**:
```
psycopg2.errors.InsufficientPrivilege: must be owner of table projects
```

**Solution**: Use direct psql connection (Option A above). The app user has limited permissions.

### Issue 2: Column Already Exists

**Error**:
```
psycopg2.errors.DuplicateColumn: column "include_context" already exists
```

**Solution**: Always use `IF NOT EXISTS` / `IF EXISTS` in SQL:
```sql
ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name TYPE;
DROP INDEX IF EXISTS index_name;
CREATE INDEX IF NOT EXISTS index_name ON table_name (columns);
```

### Issue 3: Migration Not Running on Deployment

**Problem**: Alembic migrations in `alembic/versions/` don't run automatically.

**Solution**:
- Use direct psql connection for immediate changes
- OR add SQL file to `migrations/` directory and redeploy

### Issue 4: How to Check Current Database Schema

```bash
# List all tables
PGPASSWORD='xxx' psql -h ... -p 25060 -U doadmin -d "agentpm-db" -c "\dt"

# Describe specific table
PGPASSWORD='xxx' psql -h ... -p 25060 -U doadmin -d "agentpm-db" -c "\d table_name"

# Check indexes
PGPASSWORD='xxx' psql -h ... -p 25060 -U doadmin -d "agentpm-db" -c "\di"
```

## Best Practices

### 1. Always Create Both Alembic and SQL Migrations
- **Alembic**: For local development and version control
- **SQL File**: For production deployment (backup method)

### 2. Make Migrations Idempotent
```sql
-- Good
ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name TYPE;

-- Bad (fails on second run)
ALTER TABLE table_name ADD COLUMN column_name TYPE;
```

### 3. Test Migrations Locally First
```bash
# Test with local PostgreSQL
alembic upgrade head
alembic downgrade -1  # Test rollback
alembic upgrade head
```

### 4. Use Server Defaults for NOT NULL Columns
```sql
-- Good: Won't break existing rows
ALTER TABLE table_name ADD COLUMN new_col BOOLEAN NOT NULL DEFAULT FALSE;

-- Bad: Fails if table has existing rows
ALTER TABLE table_name ADD COLUMN new_col BOOLEAN NOT NULL;
```

### 5. Add Indexes Concurrently for Large Tables
```sql
-- For large tables in production
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table_name (column);
```

## Quick Reference

### Get Production Database Access

```bash
# 1. List databases
doctl databases list

# 2. Get connection info
doctl databases connection <db-id> --format Host,Port,User,Password,Database

# 3. Connect to agentpm-db
PGPASSWORD='<password>' psql -h <host> -p <port> -U doadmin -d "agentpm-db"
```

### Common SQL Commands

```sql
-- List tables
\dt

-- Describe table
\d table_name

-- List indexes
\di

-- Show table constraints
\d+ table_name

-- Quit psql
\q
```

## Example: Complete Migration Workflow

**Scenario**: Add `send_meeting_emails` column to `users` table

```bash
# 1. Create Alembic migration
alembic revision -m "add_send_meeting_emails_to_users"

# 2. Edit alembic/versions/xxx_add_send_meeting_emails_to_users.py
def upgrade() -> None:
    op.add_column('users', sa.Column('send_meeting_emails', sa.Boolean(), nullable=False, server_default='1'))

def downgrade() -> None:
    op.drop_column('users', 'send_meeting_emails')

# 3. Update model in src/models/user.py
class User(Base):
    send_meeting_emails = Column(Boolean, nullable=False, default=True)

# 4. Create SQL file migrations/add_send_meeting_emails_column.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS send_meeting_emails BOOLEAN NOT NULL DEFAULT TRUE;

# 5. Test locally
alembic upgrade head

# 6. Commit changes
git add -A
git commit -m "Add send_meeting_emails preference to users table"
git push

# 7. Apply to production immediately (don't wait for deployment)
doctl databases list
doctl databases connection <db-id> --format Host,Port,User,Password,Database
PGPASSWORD='xxx' psql -h ... -p 25060 -U doadmin -d "agentpm-db" < migrations/add_send_meeting_emails_column.sql

# 8. Verify
PGPASSWORD='xxx' psql -h ... -p 25060 -U doadmin -d "agentpm-db" -c "\d users"
```

## Automated Alembic Migrations (Recommended Solution)

### Why Migrations Were Disabled

Previously, `run_database_migrations()` was called on app startup but was **disabled** due to:

```python
# src/web_interface.py line 382-384
# TEMPORARILY DISABLED: Causing health check failures due to blocking each gunicorn worker
# TODO: Move migrations to a separate pre-deployment step or run only in master process
# run_database_migrations()
```

**The Problem**:
- With 4 gunicorn workers, each worker ran migrations on startup
- 4 parallel migration attempts = race conditions + slow startup (30-60+ seconds)
- DigitalOcean health checks timeout after ~30 seconds
- Result: **Failed health checks = failed deployments**

### The Solution: PRE_DEPLOY Job

DigitalOcean App Platform supports **PRE_DEPLOY jobs** that run once before the app starts:

```yaml
# .do/app.yaml
jobs:
- name: migrations
  kind: PRE_DEPLOY
  instance_count: 1
  instance_size_slug: basic-xxs
  run_command: alembic upgrade head
  source_dir: /
  envs:
  - key: DATABASE_URL
    scope: RUN_AND_BUILD_TIME
    value: ${agentpm-db.DATABASE_URL}
  - key: REDIS_URL
    scope: RUN_AND_BUILD_TIME
    value: ${redis.REDIS_URL}
  # Add other environment variables needed for migrations
```

**Benefits**:
- ✅ Runs **once** per deployment (not per worker)
- ✅ Runs **before** app starts (no health check failures)
- ✅ **Automatic rollback** if migration fails
- ✅ Proper deployment pipeline
- ✅ No race conditions
- ✅ Fast app startup

**Implementation Status**: ⚠️ A `db-migrations` PRE_DEPLOY job already exists in production with run command:
```bash
alembic upgrade head && python3 scripts/ensure_watched_projects_table.py
```

**Current Issue**: The `ensure_watched_projects_table.py` script sometimes fails due to permission errors or missing table dependencies, causing deployments to fail.

**Recommended Fix**: Modify the PRE_DEPLOY job to only run Alembic migrations:
```yaml
run_command: alembic upgrade head
```

The watched_projects table creation should be handled by an Alembic migration instead of a separate script.

## Related Files

- Alembic migrations: `alembic/versions/`
- SQLAlchemy models: `src/models/`
- Production SQL migrations: `migrations/`
- Alembic config: `alembic.ini`, `alembic/env.py`
