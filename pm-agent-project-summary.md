# Autonomous PM Agent Project Summary

## Project Overview
**Goal**: Build an autonomous AI agent that streamlines project management tasks by automatically processing meeting notes and managing project tickets.

## Core Objectives

### Primary Features
1. **Meeting Notes Processing**
   - Automatically retrieve meeting transcripts from Fireflies.ai
   - Extract and summarize key discussion points
   - Identify action items and TODOs from conversations

2. **Jira Integration**
   - Create tickets automatically from identified action items
   - Update existing tickets based on meeting discussions
   - Manage ticket lifecycle (status updates, assignments)

3. **Daily Notification System** *(Added Feature)*
   - Send daily notifications for outstanding TODOs
   - Alert on in-progress items approaching deadlines
   - Flag overdue tickets requiring immediate attention
   - Customizable notification channels (Slack, email, Teams)

## Technical Architecture

### Core Technology Stack
- **Model Context Protocol (MCP)**: Standardized framework for AI-to-tool connections
- **Fireflies.ai API**: Meeting transcription and analysis
- **Jira MCP Server**: Atlassian integration via Docker
- **AI Framework**: LangChain/LangGraph for orchestration
- **Language Model**: OpenAI/Anthropic for natural language processing

### System Components

```
┌─────────────────────────────────────────────────┐
│                 AI PM Agent Core                 │
├─────────────────────────────────────────────────┤
│                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────┐ │
│  │  Meeting     │  │   Ticket     │  │  Daily │ │
│  │  Processor   │  │   Manager    │  │ Monitor│ │
│  └──────────────┘  └──────────────┘  └────────┘ │
│                                                   │
├─────────────────────────────────────────────────┤
│                 MCP Layer                        │
├─────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌────────┐ │
│  │ Fireflies    │  │    Jira      │  │ Slack/ │ │
│  │    API       │  │  MCP Server  │  │  Email │ │
│  └──────────────┘  └──────────────┘  └────────┘ │
└─────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Foundation Setup (Week 1)
- [ ] Environment setup (Docker, Node.js, Python)
- [ ] Obtain API credentials (Fireflies.ai, Jira)
- [ ] Install MCP Atlassian Docker image
- [ ] Configure authentication (OAuth 2.0/API tokens)

### Phase 2: MCP Configuration (Week 2)
- [ ] Set up Jira MCP server with Docker
- [ ] Create Fireflies.ai MCP wrapper
- [ ] Test basic connectivity
- [ ] Implement error handling and logging

### Phase 3: Core Agent Development (Weeks 3-4)
- [ ] Build meeting transcript retrieval system
- [ ] Implement AI-powered action item extraction
- [ ] Create Jira ticket creation pipeline
- [ ] Develop meeting-to-ticket workflow

### Phase 4: Daily Notification System (Week 5)
- [ ] Implement TODO tracking database
- [ ] Build notification scheduler (cron jobs)
- [ ] Create notification templates
- [ ] Set up multiple notification channels
- [ ] Add customizable notification preferences

### Phase 5: Testing & Refinement (Week 6)
- [ ] End-to-end testing with sample data
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Documentation creation

## Daily Notification Feature - Detailed Specifications

### Notification Types
1. **Morning Digest** (8:00 AM)
   - Outstanding TODOs from yesterday's meetings
   - Overdue tickets requiring attention
   - Today's deadline reminders

2. **End-of-Day Summary** (5:00 PM)
   - New action items created today
   - Status of in-progress items
   - Tomorrow's priorities

### Notification Rules
- **Overdue**: Immediate notification + daily reminder
- **Due Today**: Morning notification + 2-hour warning
- **Due This Week**: Include in morning digest
- **In Progress > 3 days**: Flag for review

### Notification Channels
```python
notification_config = {
    'slack': {
        'channel': '#pm-updates',
        'urgent_channel': '#urgent-tasks',
        'personal_dm': True
    },
    'email': {
        'digest_time': '08:00',
        'urgent_immediate': True
    },
    'teams': {
        'enabled': True,
        'webhook_url': 'TEAMS_WEBHOOK_URL'
    }
}
```

## Key Integrations

### Required APIs and Services

| Service | Purpose | Authentication |
|---------|---------|----------------|
| Fireflies.ai | Meeting transcripts | API Key |
| Jira Cloud | Ticket management | OAuth 2.0 / API Token |
| Slack | Notifications | Bot Token |
| Email (SMTP) | Email notifications | SMTP credentials |
| Microsoft Teams | Team notifications | Webhook URL |

### Environment Variables
```bash
# Fireflies Configuration
FIREFLIES_API_KEY=your_fireflies_api_key

# Jira Configuration
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=your.email@company.com
JIRA_API_TOKEN=your_jira_api_token

# Notification Configuration
SLACK_BOT_TOKEN=xoxb-your-slack-token
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=notifications@company.com
SMTP_PASS=your_smtp_password
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...

# Agent Configuration
OPENAI_API_KEY=your_openai_api_key  # or ANTHROPIC_API_KEY
AGENT_RUN_SCHEDULE="0 8,17 * * *"  # 8 AM and 5 PM daily
```

## Success Metrics

### Efficiency Metrics
- ⏱️ Time saved per week on manual task creation
- 📊 Percentage of action items automatically captured
- 🎯 Accuracy of extracted action items
- 📈 Reduction in overdue tickets

### Quality Metrics
- ✅ Completeness of created tickets
- 🎨 Clarity of ticket descriptions
- 🔄 Reduction in ticket rework
- 👥 Team satisfaction scores

## Security Considerations

1. **API Key Management**
   - Store in environment variables
   - Use secrets management service
   - Rotate keys regularly

2. **Data Privacy**
   - Encrypt data in transit and at rest
   - Implement access controls
   - Comply with data retention policies

3. **Authentication**
   - OAuth 2.0 preferred over API tokens
   - Implement rate limiting
   - Monitor for unusual activity

## Deployment Options

### Local Development
```bash
# Docker Compose for local development
docker-compose up -d jira-mcp fireflies-wrapper
python main.py --mode development
```

### Production Deployment
- **Option 1**: Cloud Functions (AWS Lambda, Google Cloud Functions)
- **Option 2**: Kubernetes cluster with scheduled jobs
- **Option 3**: Dedicated VM with systemd services

## Future Enhancements (Post-MVP)

1. **Intelligence Layer**
   - Sprint planning assistance
   - Blocker detection
   - Risk identification

2. **Advanced Analytics**
   - Velocity tracking
   - Burndown predictions
   - Team performance metrics

3. **Extended Integrations**
   - GitHub/GitLab for code tracking
   - Confluence for documentation
   - Calendar for meeting scheduling

## Resources and Documentation

### Essential Documentation
- [Model Context Protocol Docs](https://modelcontextprotocol.io/)
- [Fireflies API Reference](https://fireflies.ai/api)
- [Jira Cloud REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- [MCP Atlassian GitHub](https://github.com/sooperset/mcp-atlassian)

### Support Resources
- Community forums for MCP implementations
- Atlassian developer community
- LangChain documentation for agent development

## Project Timeline

```
Week 1: Foundation & Setup
Week 2: MCP Configuration
Week 3-4: Core Agent Development
Week 5: Daily Notification System
Week 6: Testing & Deployment
Week 7-8: Monitoring & Optimization
```

## Getting Started Checklist

### Immediate Actions (Day 1)
- [ ] Create Fireflies.ai API key
- [ ] Generate Jira API token
- [ ] Install Docker Desktop
- [ ] Set up Python virtual environment

### First Week Goals
- [ ] Successfully retrieve a meeting transcript via API
- [ ] Create a test Jira ticket programmatically
- [ ] Send a test notification to Slack/Email
- [ ] Run MCP Atlassian server locally

### First Month Deliverable
- [ ] Working prototype that processes one meeting and creates tickets
- [ ] Daily notification system for outstanding TODOs
- [ ] Basic error handling and logging
- [ ] Documentation for team deployment

---

*Last Updated: [Current Date]*
*Version: 1.0*
*Status: Planning Phase*