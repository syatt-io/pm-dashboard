# Local Development Setup

This guide explains how to run the application locally with a PostgreSQL database that mimics the production environment, avoiding SQLite vs PostgreSQL compatibility issues.

## Overview

The local development environment now uses:
- **PostgreSQL 15** (same as production) running in Docker
- **Redis** for Celery task queue
- **Port 5433** for local PostgreSQL (to avoid conflicts with system PostgreSQL on 5432)

## Prerequisites

1. **Docker/Colima**: For running PostgreSQL and Redis containers
   ```bash
   brew install colima
   colima start
   ```

2. **Python dependencies**: Install from requirements.txt
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### 1. Start Docker Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL 15 on port 5433
- Redis on port 6379

### 2. Switch to Local Environment

```bash
./switch-to-local.sh
```

This script:
- Backs up your current .env to .env.prod.backup (if not already backed up)
- Updates DATABASE_URL to point to local PostgreSQL
- Shows next steps

### 3. Run the Application

```bash
# Start Flask backend
python src/web_interface.py

# In another terminal, start React frontend
cd frontend && PORT=4001 npm start
```

The app will be available at:
- Backend: http://localhost:4000
- Frontend: http://localhost:4001

## Environment Switching

### Switch to Local Development
```bash
./switch-to-local.sh
```
- Uses local PostgreSQL (127.0.0.1:5433)
- Safe for testing and development
- All other environment variables remain the same

### Switch to Production Database
```bash
./switch-to-prod.sh
```
- Connects to DigitalOcean PostgreSQL
- **⚠️  WARNING**: This connects to PRODUCTION data!
- Only use when you need to test against real production data
- Creates .env.local.backup before switching

## Database Management

### Check Database Status
```bash
# Check if containers are running
docker-compose ps

# Connect to PostgreSQL
docker exec -it pm-agent-db psql -U pm_agent -d pm_agent

# View tables
docker exec pm-agent-db psql -U pm_agent -d pm_agent -c "\dt"
```

### Run Migrations
```bash
# Check current migration version
alembic current

# Run all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "Description of changes"
```

### Reset Local Database
```bash
# Stop containers
docker-compose down

# Remove data volumes (⚠️  destroys all local data)
docker-compose down -v

# Restart containers
docker-compose up -d

# Recreate database schema
alembic upgrade head
```

## Troubleshooting

### Port 5432 Already in Use
If you have local PostgreSQL running on port 5432, the Docker container is configured to use port 5433 instead. The local DATABASE_URL should be:
```
postgresql://pm_agent:changeme@127.0.0.1:5433/pm_agent
```

### "docker: command not found"
Install Colima as a Docker alternative:
```bash
brew install colima
colima start
```

### Alembic Not Finding .env File
The alembic/env.py file has been updated to load .env automatically. If issues persist:
1. Verify .env exists in project root
2. Check DATABASE_URL is set correctly
3. Try running migrations with explicit DATABASE_URL:
   ```bash
   DATABASE_URL=postgresql://pm_agent:changeme@127.0.0.1:5433/pm_agent alembic upgrade head
   ```

### Flask Still Using SQLite
Check the startup logs for:
```
Database engine initialized for development with connection pooling
```

If you see references to SQLite:
1. Verify .env has correct DATABASE_URL
2. Stop Flask completely (check for background processes)
3. Restart Flask

## Environment File Reference

### Local Development (.env)
```bash
DATABASE_URL=postgresql://pm_agent:changeme@127.0.0.1:5433/pm_agent
REDIS_URL=redis://127.0.0.1:6379/0
```

### Production (.env.prod.backup)
```bash
DATABASE_URL=postgresql://agentpm-db:***@...ondigitalocean.com:25060/agentpm-db?sslmode=require
REDIS_URL=redis://default:***@...upstash.io:6379
```

## Docker Compose Services

### PostgreSQL
- **Image**: postgres:15-alpine
- **Container Name**: pm-agent-db
- **Port**: 5433 (host) → 5432 (container)
- **Credentials**: pm_agent / changeme
- **Database**: pm_agent

### Redis
- **Image**: redis:7-alpine
- **Container Name**: pm-agent-cache
- **Port**: 6379
- **Persistence**: redis_data volume

## Benefits of Local PostgreSQL

1. **Production Parity**: Same database engine as production (PostgreSQL 15)
2. **Fewer Bugs**: No more SQLite vs PostgreSQL compatibility issues
3. **Migration Testing**: Test migrations locally before deploying
4. **Better Performance**: PostgreSQL performance characteristics match production
5. **Type Safety**: Catch type mismatches during development

## Next Steps

After setting up local development:
1. Test your changes locally first
2. Run migrations locally to catch issues
3. Switch to production only when necessary for testing
4. Always verify which environment you're connected to before making changes
