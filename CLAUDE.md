# Autonomous PM Agent - Project Documentation

## Project Overview
This is an Autonomous PM Agent that processes Fireflies.ai meeting transcripts, extracts action items using GPT-4, and creates Jira tickets via Model Context Protocol (MCP). The system provides both automated and interactive modes for ticket creation.

## Architecture

### Core Components
1. **Fireflies Integration** (`src/integrations/fireflies.py`)
   - GraphQL API for fetching meeting transcripts
   - Timestamp handling: Fireflies returns milliseconds, convert with `datetime.fromtimestamp(date_val / 1000)`

2. **Meeting Analyzer** (`src/meeting_analyzer.py`)
   - Uses OpenAI GPT-4 via LangChain
   - Extracts: summary, action items, decisions, risks
   - Returns structured ActionItem objects with title, description, assignee, priority

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
- always make updates only to the react app, the old Flask app is no longer being used
- never use mock data without approval
- IMPORTANT: for getting tracked time in Tempo, use the APIs not the MCP tools. Don't use MCP tools as fallback either, the data will be wrong