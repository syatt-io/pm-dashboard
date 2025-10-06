# PM Agent Deployment Guide

## Deployment Options

### 1. **Cloud VM (Recommended for Interactive Use)**

**Best for**: Teams that want both automated and interactive modes

```bash
# AWS EC2, Google Cloud Compute, or DigitalOcean Droplet
# Ubuntu 22.04 LTS with Docker installed

# Setup
git clone <repo>
cd agent-pm
docker-compose up -d
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Automated processing (cron)
crontab -e
0 8,17 * * * cd /path/to/agent-pm && source venv/bin/activate && python main.py --once

# Interactive access via SSH
ssh user@your-server
cd agent-pm && source venv/bin/activate && python main_interactive.py
```

**Pros**: Full control, interactive access, persistent storage
**Cons**: Requires server management

---

### 2. **Serverless Functions (Automated Only)**

#### AWS Lambda
```python
# lambda_handler.py
import json
from main import PMAgent

def lambda_handler(event, context):
    agent = PMAgent()
    asyncio.run(agent.process_meetings())
    return {'statusCode': 200, 'body': 'Processing complete'}

# Deploy with:
# - EventBridge trigger (twice daily)
# - Environment variables for API keys
# - Lambda layers for dependencies
```

#### Google Cloud Functions
```yaml
# cloud-function.yaml
runtime: python311
entry_point: process_meetings
source: .
env_variables:
  FIREFLIES_API_KEY: "..."
  OPENAI_API_KEY: "..."
  SLACK_BOT_TOKEN: "..."
```

**Pros**: Zero maintenance, scales automatically, cost-effective
**Cons**: No interactive mode, cold starts, timeout limits

---

### 3. **Container Platforms**

#### Docker Swarm/Kubernetes
```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pm-agent
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: pm-agent
        image: pm-agent:latest
        env:
        - name: FIREFLIES_API_KEY
          valueFrom:
            secretKeyRef:
              name: pm-secrets
              key: fireflies-key
        - name: MODE
          value: "production"
```

#### Google Cloud Run
```bash
# Build and deploy
docker build -t gcr.io/project/pm-agent .
docker push gcr.io/project/pm-agent
gcloud run deploy pm-agent --image gcr.io/project/pm-agent --platform managed
```

**Pros**: Managed infrastructure, scalable, CI/CD friendly
**Cons**: Complex setup, primarily for automated mode

---

## Interactive Mode in Deployed Environments

### **Option 1: Web Interface** ⭐ **Recommended**

Create a web-based version of the interactive mode:

```python
# web_interface.py
from flask import Flask, render_template, request, jsonify
from src.processors.interactive_processor import InteractiveProcessor

app = Flask(__name__)

@app.route('/')
def dashboard():
    meetings = get_recent_meetings()
    return render_template('dashboard.html', meetings=meetings)

@app.route('/process/<meeting_id>')
def process_meeting(meeting_id):
    analysis = analyze_meeting(meeting_id)
    return render_template('review.html', analysis=analysis)

@app.route('/confirm', methods=['POST'])
def confirm_processing():
    decisions = request.json
    results = execute_decisions(decisions)
    return jsonify(results)
```

**Deploy as**:
- **Heroku**: Simple web app deployment
- **Cloud Run**: Containerized web service
- **EC2 + nginx**: Full control web server

---

### **Option 2: Slack Bot Interface**

Turn interactive mode into Slack commands:

```python
# slack_bot.py
from slack_bolt import App

app = App(token=os.environ["SLACK_BOT_TOKEN"])

@app.command("/pm-review")
def review_meetings(ack, command, client):
    ack()
    meetings = get_recent_meetings()

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Select a meeting to review:"}
        }
    ]

    for meeting in meetings:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{meeting['title']}*\n{meeting['date']}"},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Review"},
                "action_id": f"review_{meeting['id']}"
            }
        })

    client.chat_postMessage(
        channel=command['channel_id'],
        blocks=blocks
    )

@app.action("review_*")
def handle_review(ack, body, client):
    # Show action items with approve/reject buttons
    pass
```

---

### **Option 3: Email-Based Workflow**

Send email summaries with approval links:

```python
# email_workflow.py
async def send_approval_email(meeting_analysis):
    html = f"""
    <h2>Meeting: {meeting_analysis.title}</h2>
    <h3>Action Items Found:</h3>
    <ul>
        {action_items_html}
    </ul>

    <p>
        <a href="https://pm-agent.com/approve/{token}">✅ Approve All</a> |
        <a href="https://pm-agent.com/review/{token}">🔍 Review Individual Items</a>
    </p>
    """

    send_email(to=manager_email, subject="Meeting Review Required", html=html)
```

---

## Hybrid Deployment Architecture

### **Recommended Setup**:

```mermaid
graph TD
    A[Fireflies Meetings] --> B[Cloud Function - Automated Processing]
    A --> C[Web App - Interactive Review]
    B --> D[Jira API]
    C --> D
    B --> E[Slack Notifications]
    C --> E
    F[Important Meetings] --> C
    G[Regular Status Meetings] --> B
```

**Implementation**:

1. **Automated Processing** (Cloud Function/Lambda):
   - Runs twice daily
   - Processes routine meetings automatically
   - Creates tickets for standard action items

2. **Interactive Review** (Web App/Slack Bot):
   - Triggered for important meetings
   - Manual review and approval
   - Custom categorization

3. **Smart Routing**:
   ```python
   def should_auto_process(meeting):
       auto_keywords = ['standup', 'status', 'sync', 'daily']
       return any(keyword in meeting['title'].lower() for keyword in auto_keywords)
   ```

---

## Environment Configuration

### **Production Environment Variables**

```bash
# Core APIs
FIREFLIES_API_KEY=prod_key_here
JIRA_URL=https://company.atlassian.net
JIRA_USERNAME=bot@company.com
JIRA_API_TOKEN=prod_token

# AI
OPENAI_API_KEY=prod_key
AI_TEMPERATURE=0.2  # Lower for production

# Database
DATABASE_URL=postgresql://user:pass@host:5432/pmbot

# Notifications
SLACK_BOT_TOKEN=xoxb-prod-token
SLACK_CHANNEL=#pm-updates

# Mode
DEPLOYMENT_ENV=production
LOG_LEVEL=INFO
```

### **Security Best Practices**

```bash
# Use secrets management
aws secretsmanager get-secret-value --secret-id pm-agent/api-keys

# Or environment-specific configs
helm install pm-agent ./helm-chart \
  --set secrets.fireflies_key=$FIREFLIES_KEY \
  --set secrets.openai_key=$OPENAI_KEY
```

---

## Monitoring & Maintenance

### **Health Checks**
```python
@app.route('/health')
def health_check():
    return {
        'status': 'healthy',
        'last_processed': get_last_processing_time(),
        'api_status': check_api_connections()
    }
```

### **Logging**
```python
import structlog
logger = structlog.get_logger()

logger.info("meeting_processed",
           meeting_id=meeting_id,
           action_items_count=len(items),
           tickets_created=len(tickets))
```

### **Alerting**
```python
# CloudWatch/DataDog alerts
if processing_failures > 3:
    send_alert("PM Agent: Multiple processing failures")
```

---

## Cost Optimization

### **Serverless** (Recommended for small teams)
- AWS Lambda: ~$5-10/month
- Cloud Functions: ~$3-8/month
- No server maintenance

### **Container Platform** (For larger teams)
- Cloud Run: ~$10-30/month
- Kubernetes: ~$50-100/month
- Full control and features

### **VM** (For maximum flexibility)
- Small VPS: ~$20-50/month
- Full interactive access
- Custom deployment options