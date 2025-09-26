# Autonomous PM Agent

An AI-powered project management assistant that automatically processes meeting transcripts from Fireflies.ai and creates/manages Jira tickets through the Model Context Protocol (MCP).

## Features

- **Automated Meeting Processing**: Retrieves transcripts from Fireflies.ai and extracts action items
- **Smart Ticket Creation**: Automatically creates Jira tickets from identified action items
- **Daily Notifications**: Sends digest emails and Slack notifications for outstanding TODOs
- **MCP Integration**: Uses standardized protocol for tool connections
- **Multi-channel Alerts**: Supports Slack, Email, and Microsoft Teams notifications

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Docker Desktop
- Access to:
  - Fireflies.ai API
  - Jira Cloud instance
  - Slack workspace (optional)
  - Email SMTP server (optional)

### 2. Environment Setup

```bash
# Clone and setup
git clone <repository-url>
cd agent-pm

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 3. Configure Environment Variables

Edit `.env` with your credentials:

```bash
# Fireflies
FIREFLIES_API_KEY=your_api_key_here

# Jira
JIRA_URL=https://company.atlassian.net
JIRA_USERNAME=email@company.com
JIRA_API_TOKEN=your_token_here

# AI Model (choose one)
OPENAI_API_KEY=your_openai_key
# OR
ANTHROPIC_API_KEY=your_claude_key

# Notifications (optional)
SLACK_BOT_TOKEN=xoxb-your-token
SMTP_HOST=smtp.gmail.com
SMTP_USER=notifications@company.com
SMTP_PASS=your_password
```

### 4. Start MCP Services

```bash
# Start Jira MCP server and other services
docker-compose up -d

# Check services are running
docker-compose ps
```

### 5. Test the Agent

```bash
# Test all connections
python main.py --test

# Run once (development mode)
python main.py --once

# Run on schedule (production)
python main.py --mode production
```

## Development Commands

### Running the Agent

```bash
# Development mode (run once)
python main.py --mode development --once

# Test connections
python main.py --test

# Production mode (scheduled)
python main.py --mode production
```

### Working with MCP Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs jira-mcp
docker-compose logs fireflies-mcp

# Restart specific service
docker-compose restart jira-mcp

# Stop all services
docker-compose down
```

### Database Management

```bash
# Initialize database (SQLite by default)
python -c "from main import PMAgent; PMAgent()"

# For PostgreSQL (production)
export DATABASE_URL="postgresql://user:pass@localhost/pm_agent"
```

## Project Structure

```
agent-pm/
├── main.py                 # Main agent orchestrator
├── config/
│   └── settings.py        # Configuration management
├── src/
│   ├── integrations/
│   │   ├── fireflies.py   # Fireflies.ai API client
│   │   └── jira_mcp.py    # Jira MCP client
│   ├── processors/
│   │   └── transcript_analyzer.py  # AI transcript analysis
│   ├── managers/
│   │   └── notifications.py        # Multi-channel notifications
│   └── mcp/
│       ├── fireflies_mcp_server.py # Fireflies MCP wrapper
│       └── Dockerfile.fireflies    # MCP container config
├── docker-compose.yml     # MCP services orchestration
└── requirements.txt       # Python dependencies
```

## How It Works

1. **Meeting Collection**: Agent polls Fireflies.ai for new meeting transcripts
2. **AI Analysis**: Uses LLM to extract action items, decisions, and blockers
3. **Ticket Creation**: Creates structured Jira tickets via MCP protocol
4. **Notification System**: Sends daily digests and urgent alerts
5. **Progress Tracking**: Monitors TODO completion and deadlines

## Configuration Options

### Notification Scheduling

```bash
# Set custom digest times
MORNING_DIGEST_TIME=08:00
EVENING_DIGEST_TIME=17:00

# Cron schedule for agent runs
AGENT_RUN_SCHEDULE="0 8,17 * * *"  # 8 AM and 5 PM daily
```

### AI Model Selection

```bash
# OpenAI (default)
AI_PROVIDER=openai
OPENAI_MODEL=gpt-4

# Anthropic Claude
AI_PROVIDER=anthropic
ANTHROPIC_MODEL=claude-3-opus-20240229
```

### Jira Integration

```bash
# Default project for tickets
JIRA_DEFAULT_PROJECT=PM

# Atlassian MCP server configuration is handled via Docker
```

## Production Deployment

### Option 1: VM with systemd

```bash
# Create systemd service
sudo cp scripts/pm-agent.service /etc/systemd/system/
sudo systemctl enable pm-agent
sudo systemctl start pm-agent
```

### Option 2: Cloud Functions

Deploy `main.py` as a scheduled cloud function (AWS Lambda, Google Cloud Functions).

### Option 3: Kubernetes

Use the provided Kubernetes manifests in `deploy/k8s/`.

## Troubleshooting

### Common Issues

1. **MCP Connection Failed**
   ```bash
   # Check if Docker services are running
   docker-compose ps

   # Check MCP server logs
   docker-compose logs jira-mcp
   ```

2. **Fireflies API Errors**
   ```bash
   # Test API key
   python -c "from src.integrations.fireflies import FirefliesClient; print(FirefliesClient('your_key').get_recent_meetings(1))"
   ```

3. **Notification Failures**
   ```bash
   # Test notification channels
   python main.py --test
   ```

### Logs and Monitoring

```bash
# View agent logs
tail -f pm_agent.log

# Database queries
sqlite3 pm_agent.db ".tables"
sqlite3 pm_agent.db "SELECT * FROM processed_meetings LIMIT 5;"
```

## API Reference

### Fireflies MCP Endpoints

- `POST /mcp` with method `fireflies/getRecentMeetings`
- `POST /mcp` with method `fireflies/getTranscript`
- `POST /mcp` with method `fireflies/searchMeetings`

### Jira MCP Endpoints

- Uses standard Atlassian MCP server endpoints
- Supports ticket creation, updates, and queries

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Create Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in this repository
- Check the troubleshooting section above
- Review MCP documentation: https://modelcontextprotocol.io/