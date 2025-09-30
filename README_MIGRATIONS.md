# Database Migrations Guide

This project uses Alembic for database schema migrations.

## Setup

Alembic is already configured and ready to use. The migration system tracks all changes to database schemas.

## Creating a New Migration

After making changes to models in `src/models/`:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of your changes"

# Example
alembic revision --autogenerate -m "Add email_verified column to users"
```

## Applying Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply specific migration
alembic upgrade +1         # Apply one migration
alembic upgrade <revision>  # Apply to specific revision
```

## Rolling Back

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision>

# Rollback all migrations
alembic downgrade base
```

## Viewing Migration History

```bash
# Show current revision
alembic current

# Show migration history
alembic history --verbose

# Show pending migrations
alembic heads
```

## Configuration

- **alembic.ini**: Main configuration file
- **alembic/env.py**: Environment setup (loads models and database URL)
- **alembic/versions/**: Migration files directory

### Database URL

The database URL is automatically loaded from your `.env` file via `config/settings.py`:
- Uses `DATABASE_URL` environment variable
- Falls back to `sqlite:///pm_agent.db` for local development

## Best Practices

1. **Always review auto-generated migrations** before applying them
2. **Test migrations** on a development database first
3. **Never edit applied migrations** - create a new one instead
4. **Include both upgrade() and downgrade()** functions
5. **Use descriptive migration messages**

## Common Issues

### "Target database is not up to date"

```bash
# Check current revision
alembic current

# Stamp database with current head (if database already has schema)
alembic stamp head
```

### Migrations out of sync

```bash
# View history
alembic history

# Stamp to specific revision
alembic stamp <revision>
```

### Need to manually fix migration

1. Create a new migration: `alembic revision -m "Fix previous migration"`
2. Edit the generated file in `alembic/versions/`
3. Apply: `alembic upgrade head`

## Migration in Production

For production deployments, migrations should run automatically:

```bash
# In your deployment script or Dockerfile
alembic upgrade head
```

### DigitalOcean App Platform

Add to `app-spec.yaml` run command:

```yaml
run_command: alembic upgrade head && gunicorn ...
```

## Example Migration Workflow

```bash
# 1. Make changes to models
vim src/models/user.py  # Add new column

# 2. Generate migration
alembic revision --autogenerate -m "Add user preferences"

# 3. Review the generated migration
vim alembic/versions/xxxx_add_user_preferences.py

# 4. Test in development
alembic upgrade head

# 5. Verify schema
alembic current

# 6. If something went wrong, rollback
alembic downgrade -1

# 7. Fix and create new migration
alembic revision --autogenerate -m "Fix user preferences migration"
alembic upgrade head
```

## Initial Migration

The initial migration captures the current state of all models:
- Users table with authentication
- Learnings table for team insights
- TodoItems table for task management
- ProcessedMeetings table for Fireflies integration
- UserWatchedProjects table for project tracking

This migration was generated to establish a baseline for future schema changes.
