# Autonomous PM Agent - Project Documentation

## ⚠️ CRITICAL PRODUCTION WARNING ⚠️

**NEVER override production environment variables with placeholder values (YOUR_API_KEY, etc.) without explicit permission!**

When working with `.do/app.yaml` or any production configuration files:
- NEVER change actual API tokens/secrets to placeholders
- NEVER commit changes that replace real values with "YOUR_*" placeholders
- If you need to reference environment variables in documentation, use the local `.env.example` file
- Production secrets should only be updated via DigitalOcean App Platform console or `doctl` CLI
- Always verify environment variable changes won't break production deployments

**This is critical**: Replacing production secrets with placeholders can cause complete service outages and require emergency secret rotation across all services (Slack, Jira, Google OAuth, etc.), wasting significant time and potentially exposing the application to security risks.

---

## 🔧 Deployment Troubleshooting

If you encounter deployment failures or environment variable issues, see **[docs/DEPLOYMENT_TROUBLESHOOTING_2025-10-31.md](docs/DEPLOYMENT_TROUBLESHOOTING_2025-10-31.md)** for:
- Complete troubleshooting guide for DigitalOcean deployments
- Environment variable loading issues and fixes
- Known issues and workarounds
- Commands reference

**Quick Fix for Missing Environment Variables:**
```bash
# Update app spec with secrets from .env
doctl apps spec get a2255a3b-23cc-4fd0-baa8-91d622bb912a --format json > app-spec.json
# Edit app-spec.json to replace EV[1:...] values with actual secrets
doctl apps update a2255a3b-23cc-4fd0-baa8-91d622bb912a --spec app-spec.json
doctl apps create-deployment a2255a3b-23cc-4fd0-baa8-91d622bb912a
```

---

## 🗄️ Production Database Connection

**IMPORTANT**: The production database has TWO databases on the same cluster - make sure you use the correct one!

**Correct Database for agent-pm:**
- **Host**: `app-3e774e03-7ffb-4138-a401-13c2fd3f09b4-nov-20-backup-1am-do-u.e.db.ondigitalocean.com`
- **Database**: `agentpm-db` ⚠️ NOT `defaultdb` (that's a different app!)
- **Username**: `doadmin` ⚠️ CRITICAL - For restored backups, always use `doadmin` not `agentpm-db`!
- **Port**: 25060
- **Password**: Stored in DigitalOcean App Platform environment variables as `DATABASE_URL`

**Connection String Format:**
```
postgresql://doadmin:PASSWORD@HOST:25060/agentpm-db?sslmode=require
```

**Common Mistakes to Avoid:**
- ❌ Using `defaultdb` - This is a completely different application with tables like `sites`, `accounts`, `performance_metrics`
- ✅ Always use `agentpm-db` database - This has the correct tables: `projects`, `users`, `todo_items`, etc.
- ❌ Using username `agentpm-db` - This user exists but can't authenticate on restored backups
- ✅ Always use username `doadmin` - Only user with accessible password on DigitalOcean managed databases

**Why `doadmin` and not `agentpm-db`?**
DigitalOcean managed databases only expose the `doadmin` user's password. When you restore a backup, the `agentpm-db` user is copied to the new cluster, but you can only authenticate with `doadmin`. The `agentpm-db` database is accessible once connected.

**Verification Command:**
```bash
# Should show projects, users, todo_items, etc.
psql -h <HOST> -U doadmin -d agentpm-db -p 25060 -c "\dt"
```

**Database Ownership After Restore:**
After restoring a backup, ALL database objects (tables, sequences, types) will be owned by `agentpm-db` user. This causes migration failures because `doadmin` (the user the app connects as) can't ALTER enum types that have dependent tables owned by another user.

**Fix ownership issues with:**
```bash
# Transfer all object ownership to doadmin
psql -h <HOST> -U doadmin -d agentpm-db -p 25060 -c 'REASSIGN OWNED BY "agentpm-db" TO doadmin;'

# Verify all tables are owned by doadmin
psql -h <HOST> -U doadmin -d agentpm-db -p 25060 -c "SELECT COUNT(*) as total, COUNT(CASE WHEN tableowner = 'doadmin' THEN 1 END) as doadmin_owned FROM pg_tables WHERE schemaname = 'public';"
```

**When to run this:**
- ✅ Immediately after restoring from backup
- ✅ If migrations fail with "permission denied" or ownership errors
- ✅ Before any deployment that includes Alembic migrations

---

## 🛡️ CSRF Protection

**CRITICAL**: Every new Flask Blueprint with API endpoints MUST be explicitly exempted from CSRF protection or you'll get 400 errors!

See **[docs/CSRF_PROTECTION_GUIDE.md](docs/CSRF_PROTECTION_GUIDE.md)** for:
- Complete explanation of the CSRF problem
- Step-by-step blueprint exemption pattern
- Real examples from codebase
- Debugging checklist for 400 errors
- Historical issues and fixes
- Security considerations

**Quick Reference**:
```python
# In src/web_interface.py (BEFORE registering blueprint):
csrf.exempt(your_feature_bp)
logger.info("✅ YourFeature endpoints exempted from CSRF protection")
app.register_blueprint(your_feature_bp)
```

---

## 🔄 ALEMBIC MIGRATION SAFETY

**CRITICAL**: SQLAlchemy models MUST match database reality to prevent Alembic from hallucinating column drops!

### The Problem (Occurred Nov 16 & Nov 19, 2025)

When running `alembic revision --autogenerate`, Alembic compares:
1. Model definitions in `src/models/` (what SQLAlchemy thinks exists)
2. Database schema (what actually exists)

If columns exist in the database but NOT in the model, Alembic assumes they're "orphaned" and generates `DROP COLUMN` commands!

### What Happened

The `Project` model (`src/models/project.py`) was missing 11 columns that:
- ✅ Existed in production database
- ✅ Were actively used in 10-68 files each
- ✅ Were critical for Tempo sync, forecasting, email notifications, budget tracking

Result: Alembic auto-generated migrations dropped them TWICE (Nov 16, Nov 19), causing:
- Data loss
- Application crashes
- Hours of recovery work

### Prevention Rules

**BEFORE running `alembic revision --autogenerate`:**

1. ✅ **Verify model completeness**: Check that ALL columns in the database table exist in the corresponding SQLAlchemy model
2. ✅ **Run verification test**: After adding columns to model, run autogenerate to verify it produces NO drops
3. ✅ **NEVER blindly trust autogenerate**: ALWAYS review generated migrations before committing
4. ✅ **Look for DROP COLUMN**: If you see ANY `op.drop_column()` commands, investigate WHY before committing

**Red Flags:**
```python
# 🚨 DANGER: Alembic wants to drop columns - investigate before committing!
op.drop_column("projects", "cumulative_hours")
op.drop_column("projects", "total_hours")
```

**Safe Pattern:**
```python
# ✅ GOOD: Model matches database - only adding new columns
op.add_column("projects", sa.Column("new_feature", sa.String(50)))
```

### Fixed Migration Pattern

See `alembic/versions/7a2ca1bc7707_add_slack_installations_table_for_oauth_.py` for example of commenting out hallucinated drops with clear warning.

### Model Maintenance Checklist

When modifying the `Project` model:
- [ ] Does model have ALL columns that exist in production database?
- [ ] Run `alembic revision --autogenerate -m "verify"` to test
- [ ] Review generated migration - should be EMPTY or only ADD columns
- [ ] Delete verification migration if clean
- [ ] Document WHY each column exists (usage count, purpose)

**Related Files:**
- `src/models/project.py` - Contains model with ALL required columns and usage docs
- `alembic/versions/7a2ca1bc7707_*.py` - Example of fixed migration with drops commented out
- `alembic/versions/2069b8009924_*.py` - Previous restore migration (Nov 16, 2025)

---

## Project Overview
This is an Autonomous PM Agent that processes Fireflies.ai meeting transcripts, extracts action items using AI, and creates Jira tickets via Model Context Protocol (MCP). The system provides both automated and interactive modes for ticket creation.

## Architecture

### Core Components
1. **Fireflies Integration** (`src/integrations/fireflies.py`)
   - GraphQL API for fetching meeting transcripts
   - Timestamp handling: Fireflies returns milliseconds, convert with `datetime.fromtimestamp(date_val / 1000)`

2. **Meeting Analyzer** (`src/processors/transcript_analyzer.py`)
   - Multi-provider AI support: OpenAI, Anthropic (Claude), Google (Gemini)
   - Dynamic configuration: updates take effect immediately without restart
   - Extracts: summary, action items, decisions, risks
   - Returns structured ActionItem objects with title, description, assignee, priority
   - **See**: [AI Configuration Guide](docs/AI_CONFIGURATION.md)

3. **Jira Integration** (`src/integrations/jira_mcp.py`)
   - Direct REST API v3 calls with Basic Auth
   - MCP server fallback for ticket creation
   - User endpoint: `/rest/api/3/user/search` or `/rest/api/3/user/assignable/multiProjectSearch`

4. **Tempo Integration** (`src/integrations/tempo.py`)
   - Tempo Cloud API v4 for time tracking data
   - Server-side project filtering using numeric project IDs
   - Epic hours aggregation with Jira epic lookup
   - Caching mechanisms for project IDs and epic keys
   - **CRITICAL**: See [Tempo API v4 Project Filtering Guide](docs/TEMPO_API_V4_PROJECT_FILTERING.md)
   - **Key Discovery**: Must use `projectId` parameter with numeric ID, NOT `projectKey` with string key

5. **Web Interface** (`src/web_interface.py`)
   - Flask application with SQLAlchemy ORM
   - Analysis caching to avoid redundant API calls
   - TODO list management with CRUD operations

6. **Database** (`src/models.py`)
   - SQLite with SQLAlchemy
   - Tables: meetings, action_items, todo_items
   - Caching layer for meeting analysis results

## Design System
Implements Syatt Design System:
- **Primary Colors**: Royal Purple (#554DFF), Neon Mint (#00FFCE)
- **Font**: Poppins (weights: 400, 500, 600, 700)
- **Components**: Buttons, cards, forms with consistent styling
- **Gradients**: Purple gradient (136deg, #554DFF to #7D00FF)

## Environment Setup

### Required Environment Variables (.env)
```bash
# Fireflies API
FIREFLIES_API_KEY=your_api_key
# System-level API key for nightly meeting analysis job
FIREFLIES_SYSTEM_API_KEY=your_system_api_key

# OpenAI
OPENAI_API_KEY=your_api_key

# Jira
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your_email@example.com
JIRA_API_TOKEN=your_api_token
JIRA_PROJECT_KEY=YOUR_PROJECT

# Slack
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your_secret
SLACK_CHANNEL=#your-channel

# Email (SendGrid)
SENDGRID_API_KEY=your_api_key
SENDGRID_FROM_EMAIL=from@example.com
SENDGRID_TO_EMAIL=to@example.com
```

### Docker Setup (Using Colima)
```bash
# Install Colima (Docker alternative for Mac)
brew install colima
colima start

# Run services
docker-compose up -d
```

## Port Configuration

The application uses the following ports:
- **Backend (Flask)**: Port 4000 - `http://localhost:4000`
- **Frontend (React)**: Port 4001 - `http://localhost:4001`

These ports are configured to avoid conflicts with other applications that commonly use ports 3000/3001/5001.

## Running the Application

### Web Interface
```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask app (backend)
python src/web_interface.py
# Backend accessible at http://localhost:4000

# Run React app (frontend)
cd frontend && PORT=4001 npm start
# Frontend accessible at http://localhost:4001
```

### Interactive CLI Mode
```bash
python src/main.py --interactive
```

### Automated Mode
```bash
python src/main.py
```

## API Endpoints

### Jira Metadata APIs
- `GET /api/jira/projects` - Get all projects (sorted alphabetically)
- `GET /api/jira/users` - Get all assignable users
- `GET /api/jira/users?project=KEY` - Get project-specific users
- `GET /api/jira/priorities` - Get priority levels
- `GET /api/jira/issue-types?project=KEY` - Get issue types for project

### Meeting APIs
- `GET /` - Dashboard with recent meetings
- `GET /analyze/<meeting_id>` - Analyze specific meeting
- `POST /analyze/<meeting_id>` - Force re-analysis
- `GET /review` - Review action items interface
- `POST /create_tickets` - Bulk create Jira tickets

### TODO APIs
- `GET /todos` - TODO dashboard
- `POST /api/todos` - Create TODO
- `PUT /api/todos/<id>` - Update TODO
- `DELETE /api/todos/<id>` - Delete TODO

## Common Issues & Fixes

See **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** for comprehensive troubleshooting guide including:
- Fireflies integration issues
- Jira API problems
- Flask/template errors
- Docker setup issues
- Database schema mismatches
- General debugging tips

**Quick Reference**:
- CSRF 400 errors → [CSRF Protection Guide](docs/CSRF_PROTECTION_GUIDE.md)
- Deployment issues → [Deployment Troubleshooting](docs/DEPLOYMENT_TROUBLESHOOTING_2025-10-31.md)
- Tempo API v4 project filtering → [Tempo API v4 Project Filtering Guide](docs/TEMPO_API_V4_PROJECT_FILTERING.md)
- Missing Tempo hours → Use Tempo/Jira APIs (NOT MCP tools - data will be wrong)

## Project Structure
```
agent-pm/
├── src/
│   ├── main.py                 # Entry point
│   ├── web_interface.py        # Flask application
│   ├── meeting_analyzer.py     # GPT-4 analysis
│   ├── models.py               # SQLAlchemy models
│   ├── todo_manager.py         # TODO CRUD operations
│   ├── integrations/
│   │   ├── fireflies.py        # Fireflies API client
│   │   ├── jira_mcp.py        # Jira MCP/API client
│   │   ├── slack.py           # Slack bot
│   │   └── email.py           # SendGrid integration
│   └── utils/
│       └── config.py           # Settings management
├── templates/                   # Jinja2 templates
│   ├── base.html               # Master template with Syatt design
│   ├── dashboard.html          # Meeting list
│   ├── analysis.html           # Analysis results
│   ├── review.html             # Action item review
│   └── todos.html              # TODO management
├── static/                      # CSS/JS assets
├── docker-compose.yml          # Container orchestration
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables
```

## Form Implementation Notes

### Review Form (`templates/review.html`)
- **Single Assignee Dropdown**: Populated with all Jira users via `loadAllUsers()`
- **Dynamic Issue Types**: Loaded based on selected project
- **Priority Dropdown**: Single dropdown with Jira priorities
- **Project Sorting**: Alphabetical by project key
- **No Due Date**: Removed per requirements

### JavaScript Functions
```javascript
// Load all users for assignee dropdown
function loadAllUsers() {
    fetch('/api/jira/users')
        .then(response => response.json())
        .then(data => {
            jiraData.users = data.users || [];
            populateAssigneeDropdowns();
        });
}

// Sort projects alphabetically
function populateProjectDropdowns() {
    const sortedProjects = [...jiraData.projects].sort((a, b) =>
        a.key.localeCompare(b.key)
    );
}
```

## Recent Fixes (Latest)

1. **Removed Duplicate Assignee Field**: Consolidated to single "Assignee" dropdown
2. **Fixed Unpopulated Assignee Dropdown**: Added `loadAllUsers()` function to fetch all users
3. **Removed Due Date Field**: Eliminated from form per requirements
4. **Consolidated Priority Dropdowns**: Single priority dropdown with Jira values
5. **Fixed Project Sorting**: Alphabetical sort by project key (e.g., SATG before SUBS)

## Key Features

### 1. Meeting Processing
- Fetches transcripts from Fireflies.ai
- AI-powered analysis with GPT-4
- Caches analysis results in database
- Supports re-analysis on demand

### 2. Action Item Management
- Interactive review interface (`/review`)
- Bulk creation of Jira tickets
- Dynamic form population with Jira metadata
- Single assignee dropdown with all users
- Project-based filtering for issue types

### 3. TODO List System
- Full CRUD operations via web UI
- Status tracking (pending, in-progress, done)
- Integration with action items
- Dashboard view at `/todos`

### 4. Notification System
- Slack bot with slash commands
- Email via SendGrid
- Real-time updates on ticket creation

### 5. Scheduled Jobs
#### Nightly Meeting Analysis (`src/jobs/meeting_analysis_sync.py`)
- **Schedule**: Runs daily at 7 AM UTC (3 AM EST)
- **Purpose**: Automatically analyzes meetings from active projects
- **Process**:
  1. Fetches active projects and their keywords from database
  2. Retrieves meetings from last 3 days via Fireflies API
  3. Filters meetings by project keywords (title matching)
  4. Checks for unanalyzed meetings (not in processed_meetings table)
  5. Runs AI analysis for each matched meeting
  6. Stores results in processed_meetings table
  7. Sends Slack notification with stats
- **Authentication**: Uses `FIREFLIES_SYSTEM_API_KEY` (org-wide access required)
- **Manual Testing**: `python src/jobs/meeting_analysis_sync.py`
- **API Trigger**: `POST /api/scheduler/meeting-analysis-sync` (requires X-Admin-Key header)
- **GitHub Actions**: `.github/workflows/nightly-meeting-analysis.yml`

**Key Features**:
- 3-day lookback window (catches meetings if job fails one night)
- Rate limiting: 2-second delay between analyses
- Slack notifications with success/error stats
- Duplicate prevention via processed_meetings check
- Project-based filtering via keywords

**Requirements**:
- FIREFLIES_SYSTEM_API_KEY must have org-wide access to all meetings
- Active projects must have keywords defined in project_keywords table
- SLACK_BOT_TOKEN and SLACK_CHANNEL for notifications

## Testing Checklist

### Meeting Analysis
- [ ] Fetch Fireflies transcript
- [ ] Extract action items with GPT-4
- [ ] Cache analysis in database
- [ ] Display in web UI

### Jira Integration
- [ ] Load projects (alphabetically sorted)
- [ ] Load all users for assignee dropdown
- [ ] Load priorities dynamically
- [ ] Create tickets with correct fields
- [ ] Handle API errors gracefully

### TODO Management
- [ ] Create new TODOs
- [ ] Update status
- [ ] Edit descriptions
- [ ] Delete items
- [ ] Persist in database

### UI/UX
- [ ] Syatt design system applied
- [ ] Navigation with breadcrumbs
- [ ] Responsive forms
- [ ] Loading states
- [ ] Error handling

## Commands to Run/Test

### Lint and Type Check
```bash
# Check for lint command in package.json or setup.cfg
npm run lint           # If Node.js project
python -m flake8       # Python linting
python -m mypy src/    # Type checking
```

### Run Tests
```bash
# Look for test directory or pytest config
python -m pytest tests/    # Run test suite
python -m pytest -v       # Verbose test output
```

### Database Management
```bash
# Database operations
python -c "from src.models import *; Base.metadata.create_all(engine)"  # Create tables
rm pm_agent.db  # Reset database if schema changes
```

## Development Guidelines

When working on this project:
1. Always test Jira API endpoints before form changes
2. Use environment variables for all credentials
3. Follow Syatt design system for UI components
4. Cache API responses to avoid rate limits
5. Run lint/typecheck before committing changes
6. Test form functionality after Jira integration changes
- never use mock data without approval
- IMPORTANT: for getting tracked time in Tempo, use the APIs not the MCP tools. Don't use MCP tools as fallback either, the data will be wrong

## Data Backfill Scripts

### ⚠️ IMPORTANT: Always Use V2 Backfill Scripts

**See the comprehensive guide: [docs/BACKFILL_BEST_PRACTICES.md](docs/BACKFILL_BEST_PRACTICES.md)** for:
- Complete V2 disk-caching pattern
- API-specific gotchas (Jira pagination bug, etc.)
- Verification and validation strategies
- Troubleshooting checklist
- Production-ready example scripts

When creating or running backfill scripts (Jira, Slack, GitHub, Tempo, etc.), **ALWAYS use the disk-caching pattern** from `scripts/backfill_jira_standalone_v2.py`.

**Why V2 is Critical:**
- **Data persistence**: Saves fetched data to disk incrementally (no data loss on crashes)
- **Resume capability**: Can resume from where it left off if interrupted
- **Memory efficiency**: Doesn't hold all data in RAM during fetch phase
- **Debugging**: Can inspect cached data manually
- **Reliability**: Survives crashes, OOM errors, network interruptions

**Key Features of V2 Pattern:**
```python
# Save each project immediately after fetching
CACHE_DIR = Path("/tmp/jira_backfill_cache")
save_project_data(project_key, issues)  # Saves to {PROJECT_KEY}.json

# Resume capability - skip already cached projects
already_fetched = get_already_fetched_projects()
if resume and project_key in already_fetched:
    skip_project()

# Load all cached data before ingestion
all_cached_data = load_cached_projects()
ingest_service.ingest(all_cached_data)
```

**Usage Examples:**
```bash
# Normal run with resume (recommended)
python scripts/backfill_jira_standalone_v2.py --days 730

# Start fresh (clear cache and re-fetch)
python scripts/backfill_jira_standalone_v2.py --days 730 --clear-cache

# Check cache status
ls -lh /tmp/jira_backfill_cache/

# Inspect specific project cache
cat /tmp/jira_backfill_cache/SUBS.json | jq '.issue_count'
```

**DO NOT use V1 scripts** (in-memory only) for production backfills - they risk losing hours of work if the process crashes!

### 🐛 Critical: Jira Cloud API Pagination Bug

**NEVER use pagination with Jira's `/rest/api/3/search/jql` GET endpoint** - it completely ignores the `startAt` parameter and always returns the first page, causing massive duplication!

**Solution:** Fetch all results in ONE call with `maxResults=1000` (Jira's max):
```python
result = await client.search_issues(
    jql=jql,
    max_results=1000,  # Get all in one call
    start_at=0         # Always 0
)
```

See [docs/BACKFILL_BEST_PRACTICES.md](docs/BACKFILL_BEST_PRACTICES.md) section "Jira Cloud API Pagination Bug" for full details and workarounds.

---

- always refer to @docs/README_MIGRATIONS.md when doing DB migrations.
- Locally use the Postgres DB, not SQLlite