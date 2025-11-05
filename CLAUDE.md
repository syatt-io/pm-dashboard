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

## 🛡️ CSRF Protection Requirements

**CRITICAL**: Every new Flask Blueprint with API endpoints MUST be explicitly exempted from CSRF protection!

### The Problem
This application uses Flask-WTF's CSRFProtect, which by default applies CSRF validation to ALL POST/PUT/DELETE requests. Our React frontend makes API calls without CSRF tokens (using JWT authentication instead), so API endpoints will return **400 Bad Request** errors unless explicitly exempted.

### The Solution Pattern (src/web_interface.py)

When creating a new Blueprint with API endpoints:

1. **Import the blueprint** (around line 100-150):
```python
from src.routes.your_new_feature import your_feature_bp
```

2. **Exempt it from CSRF protection** (around line 280-320, BEFORE registering):
```python
# ✅ SECURITY: Exempt YourFeature endpoints from CSRF protection
# YourFeature endpoints are called from React frontend with JWT auth
csrf.exempt(your_feature_bp)
logger.info("✅ YourFeature endpoints exempted from CSRF protection")
```

3. **Register the blueprint** (around line 313-330):
```python
app.register_blueprint(your_feature_bp)
```

### Real Examples from Codebase

**Correct Pattern** (lines 308-316):
```python
# ✅ SECURITY: Exempt Projects endpoints from CSRF protection
csrf.exempt(projects_bp)
logger.info("✅ Projects endpoints exempted from CSRF protection")

# ✅ SECURITY: Exempt User endpoints from CSRF protection
csrf.exempt(user_bp)
logger.info("✅ User endpoints exempted from CSRF protection")

app.register_blueprint(todos_bp)
app.register_blueprint(meetings_bp)
app.register_blueprint(user_bp)
```

### Blueprints That Need Exemption
- All `/api/*` routes called from React frontend
- Routes using JWT authentication (not session-based auth)
- Routes that handle POST/PUT/DELETE requests

### Blueprints That Don't Need Exemption
- Routes rendering HTML templates (GET only)
- Routes using session-based authentication with forms
- Webhook endpoints (like `/slack/` - already exempted)

### How to Debug CSRF Issues

**Symptom**: 400 Bad Request on POST/PUT/DELETE from frontend

**Quick Check**:
```bash
# Search for your blueprint in web_interface.py
grep "your_feature_bp" src/web_interface.py

# Look for these two lines:
# 1. csrf.exempt(your_feature_bp)  ← Should exist
# 2. app.register_blueprint(your_feature_bp)  ← Should exist
```

**If exemption is missing**: Add it following the pattern above, commit, and deploy.

### Historical Issues
- **Week 2 Auto-Escalation (Nov 2024)**: user_bp not exempted → 400 errors on `/api/user/escalation-preferences`
- **Fix**: Added `csrf.exempt(user_bp)` at line 315 (commit 95538ac)

### Checklist for New API Features
- [ ] Create Blueprint in `src/routes/`
- [ ] Import Blueprint in `src/web_interface.py`
- [ ] **Add `csrf.exempt(your_bp)` BEFORE registering**
- [ ] Register Blueprint with `app.register_blueprint(your_bp)`
- [ ] Test POST/PUT/DELETE endpoints from frontend
- [ ] Verify no 400 errors in browser console

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

4. **Web Interface** (`src/web_interface.py`)
   - Flask application with SQLAlchemy ORM
   - Analysis caching to avoid redundant API calls
   - TODO list management with CRUD operations

5. **Database** (`src/models.py`)
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

### 1. Fireflies Timestamp Issue
**Problem**: API returns 400 error with ISO timestamp
**Fix**: Use milliseconds - `datetime.fromtimestamp(date_val / 1000)`

### 2. Jira User API 404
**Problem**: `/rest/api/3/user/assignable/search` returns 404
**Fix**: Use `/rest/api/3/user/search` or `/rest/api/3/user/assignable/multiProjectSearch`

### 3. Template Not Found
**Problem**: Flask can't find templates
**Fix**: Set template_dir to parent directory:
```python
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
```

### 4. Docker Permission Issues
**Problem**: Can't install Docker with Homebrew
**Solution**: Use Colima as alternative:
```bash
brew install colima
colima start
```

### 5. Database Schema Mismatch
**Problem**: Missing columns after updates
**Fix**: Run migration script or delete `pm_agent.db` and restart

### 6. Jira Tempo Hours Missing
**Problem**: Missing hours when summed, compared to Tempo UI
**Fix**: Refer to /Users/msamimi/syatt/projects/dev-learnings/Jira-integrations/TEMPO_API_INTEGRATION_GUIDE.md for how this was solved

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