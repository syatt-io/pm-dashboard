# Autonomous PM Agent

An intelligent project management system that automatically processes meeting transcripts, generates weekly digests, tracks time, and manages action items across your organization. Built with AI-powered analysis and seamless integrations with Fireflies.ai, Jira, Slack, GitHub, Notion, and Tempo.

## 🚀 Key Features

### Core Capabilities
- **AI Meeting Analysis**: Automatically processes Fireflies.ai transcripts to extract action items, decisions, and blockers
- **Smart Project Linking**: Intelligently associates meetings with relevant projects based on content
- **Weekly Digests**: Generates comprehensive project status reports with insights
- **Time Tracking Integration**: Syncs with Tempo to track project hours and budget
- **Multi-Project Management**: Handles multiple concurrent projects with custom settings
- **User Authentication**: Google SSO and user management with role-based access

### Web Interface
- **Modern React Frontend**: Intuitive dashboard for managing meetings, projects, and action items
- **Real-time Processing**: Live meeting analysis and ticket creation
- **Project Settings**: Configure notification schedules, Slack channels, and team members per project
- **Manual Overrides**: Edit action items before creating Jira tickets

### Automation Features
- **Scheduled Reports**: Weekly project digests sent automatically
- **Smart Notifications**: Alerts for blockers, overdue items, and budget concerns
- **Bulk Ticket Creation**: Create multiple Jira tickets with one click
- **Hours Tracking Reports**: Automated time tracking summaries

## 📋 Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL or SQLite
- API Access:
  - Fireflies.ai API key
  - Jira Cloud instance with API token
  - Tempo API token (for time tracking)
  - OpenAI or Anthropic API key
  - Slack workspace (optional)
  - Google OAuth credentials (for SSO)

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd agent-pm
```

### 2. Backend Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 3. Frontend Setup
```bash
cd frontend
npm install
```

### 4. Configure Environment Variables

Edit `.env` with your credentials:

```bash
# Core Services
FIREFLIES_API_KEY=your_fireflies_key
OPENAI_API_KEY=your_openai_key  # or ANTHROPIC_API_KEY

# Jira Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your_jira_token
JIRA_PROJECT_KEY=YOUR_DEFAULT_PROJECT

# Tempo (Time Tracking)
TEMPO_API_TOKEN=your_tempo_token

# Google OAuth (for SSO)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# Slack (Optional)
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your_secret
SLACK_CHANNEL=#your-default-channel

# Email (Optional - using SendGrid)
SENDGRID_API_KEY=your_sendgrid_key
SENDGRID_FROM_EMAIL=notifications@company.com

# Security
JWT_SECRET_KEY=your-secret-key-here
```

### 5. Initialize Database
```bash
# Run migrations
python migrations/migrate_database.py
python migrations/migrate_add_users.py

# Or start fresh
rm pm_agent.db  # Remove existing database
python main.py  # Auto-creates tables on first run
```

## 🚀 Running the Application

### Development Mode

Start both backend and frontend:

```bash
# Terminal 1: Backend API
source venv/bin/activate
python main.py

# Terminal 2: Frontend React App
cd frontend
PORT=4001 npm start
```

Access the application at:
- Frontend: http://localhost:4001
- Backend API: http://localhost:4000

### Production Mode

```bash
# Backend with production settings
python main.py --mode production

# Frontend build
cd frontend
npm run build
# Serve the build folder with your web server
```

## 📁 Project Structure

```
agent-pm/
├── main.py                         # Main application entry point
├── config/
│   ├── settings.py                # Configuration management
│   └── ai_prompts.yaml            # Customizable AI prompts
├── src/
│   ├── web_interface.py           # Flask API server
│   ├── models/                    # Database models
│   │   ├── base.py
│   │   ├── project.py
│   │   └── user.py
│   ├── routes/                    # API endpoints
│   │   ├── auth.py               # Authentication routes
│   │   ├── meetings.py           # Meeting management
│   │   └── projects.py          # Project management
│   ├── services/                  # Business logic
│   │   ├── project_activity_aggregator.py  # Digest generation
│   │   ├── hours_report_agent.py          # Time tracking
│   │   ├── meeting_project_linker.py      # Smart project linking
│   │   └── scheduler.py                   # Automated tasks
│   ├── integrations/              # External service clients
│   │   ├── fireflies.py          # Fireflies.ai API
│   │   ├── jira_mcp.py          # Jira integration
│   │   └── tempo.py             # Tempo time tracking
│   ├── processors/                # Data processing
│   │   └── transcript_analyzer.py # AI meeting analysis
│   ├── managers/                  # Service managers
│   │   ├── notifications.py      # Multi-channel alerts
│   │   ├── slack_bot.py         # Slack integration
│   │   └── todo_manager.py      # Task management
│   └── utils/                     # Utilities
│       ├── prompt_manager.py    # AI prompt configuration
│       └── project_matcher.py   # Project association logic
├── frontend/                      # React application
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── services/           # API services
│   │   └── App.js
│   └── package.json
├── migrations/                    # Database migrations
├── templates/                     # Legacy HTML templates
└── static/                       # Legacy static assets
```

## 💡 Key Workflows

### 1. Meeting Processing Flow
```
Fireflies Meeting → AI Analysis → Action Items → Review Interface → Jira Tickets
```

### 2. Weekly Digest Generation
```
Collect Meetings → Aggregate Jira Activity → Fetch Slack Discussions →
Track Time Entries → Generate AI Insights → Send Digest
```

### 3. Project Management
```
Create Project → Configure Settings → Link Meetings →
Generate Reports → Track Progress
```

## 🔧 Configuration

### AI Prompt Customization

Edit `config/ai_prompts.yaml` to customize:
- Meeting analysis prompts
- Digest generation templates
- Slack discussion analysis
- Action item extraction logic

### Project-Specific Settings

Each project can have:
- Custom Slack channel
- Specific team members
- Notification schedules
- Budget thresholds
- Priority rules

## 📊 API Endpoints

### Authentication
- `POST /api/auth/google` - Google SSO login
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Current user info

### Projects
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create new project
- `PUT /api/projects/{id}` - Update project
- `GET /api/projects/{id}/digest` - Generate project digest
- `GET /api/projects/{id}/hours` - Get time tracking data

### Meetings
- `GET /api/meetings` - List recent meetings
- `GET /api/meetings/{id}/analyze` - Analyze specific meeting
- `POST /api/meetings/{id}/link` - Link meeting to project
- `POST /api/meetings/analyze-batch` - Bulk analysis

### Action Items
- `GET /api/action-items` - List action items
- `POST /api/action-items/create-tickets` - Create Jira tickets
- `PUT /api/action-items/{id}` - Update action item
- `DELETE /api/action-items/{id}` - Delete action item

## 🚨 Monitoring & Debugging

### Check Logs
```bash
# Application logs
tail -f logs/app.log

# View database
sqlite3 pm_agent.db ".tables"
sqlite3 pm_agent.db "SELECT * FROM meetings ORDER BY date DESC LIMIT 5;"
```

### Test Integrations
```bash
# Test Fireflies connection
python -c "from src.integrations.fireflies import FirefliesClient; client = FirefliesClient(); print(client.get_recent_meetings(1))"

# Test Jira connection
python -c "from src.integrations.jira_mcp import JiraMCPClient; client = JiraMCPClient(); print(client.get_projects())"
```

## 🔐 Security Features

- JWT-based authentication
- Google SSO integration
- User role management
- API key encryption
- Secure session handling
- CORS protection

## 🚀 Deployment

### Docker Deployment
```bash
docker build -t pm-agent .
docker run -p 4000:4000 -p 4001:4001 --env-file .env pm-agent
```

### Cloud Deployment (Heroku/Railway/Render)
1. Set environment variables in cloud platform
2. Configure database URL
3. Deploy with Git push
4. Set up scheduled jobs for automation

### Production Checklist
- [ ] Configure production database (PostgreSQL recommended)
- [ ] Set strong JWT secret key
- [ ] Configure SSL certificates
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Configure backup strategy
- [ ] Set rate limiting
- [ ] Configure CDN for frontend

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 🎯 Roadmap

- [ ] AI-powered project predictions
- [ ] Integration with more tools
- [ ] Custom workflow automation
- [ ] Real-time collaboration features

---
Built with ❤️ by the Syatt team