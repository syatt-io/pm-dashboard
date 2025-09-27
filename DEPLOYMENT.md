# DigitalOcean App Platform Deployment Guide

This guide will walk you through deploying the Agent PM application to DigitalOcean's App Platform using their CLI tool (`doctl`).

## Prerequisites

1. **DigitalOcean Account**: Sign up at https://cloud.digitalocean.com
2. **GitHub Repository**: Push your code to GitHub (make it public or grant DigitalOcean access)
3. **DigitalOcean CLI**: Install `doctl`

## Step 1: Install DigitalOcean CLI

```bash
# macOS
brew install doctl

# Linux
cd ~
wget https://github.com/digitalocean/doctl/releases/download/v1.94.0/doctl-1.94.0-linux-amd64.tar.gz
tar xf ~/doctl-1.94.0-linux-amd64.tar.gz
sudo mv ~/doctl /usr/local/bin

# Windows (via Chocolatey)
choco install doctl
```

## Step 2: Authenticate with DigitalOcean

```bash
# Generate a personal access token at:
# https://cloud.digitalocean.com/account/api/tokens

doctl auth init
# Paste your token when prompted
```

## Step 3: Prepare Environment Variables

Before deploying, gather all required credentials:

### Generate JWT Secret
```bash
openssl rand -hex 32
```

### Required Environment Variables
- `JWT_SECRET_KEY` - Generate with command above
- `GOOGLE_CLIENT_ID` - From Google Cloud Console
- `FIREFLIES_API_KEY` - From Fireflies.ai
- `OPENAI_API_KEY` - From OpenAI
- `JIRA_URL` - Your Atlassian URL (e.g., https://yourcompany.atlassian.net)
- `JIRA_USERNAME` - Your Jira email
- `JIRA_API_TOKEN` - From Jira account settings
- `JIRA_PROJECT_KEY` - Default project key

### Optional (but recommended):
- `SLACK_BOT_TOKEN` - From Slack API
- `SLACK_SIGNING_SECRET` - From Slack API
- `SLACK_CHANNEL` - Default channel (e.g., #pm-updates)
- `TEMPO_API_TOKEN` - For Tempo time tracking

## Step 4: Update Configuration Files

### 4.1 Update `.do/app.yaml`

Edit `.do/app.yaml` and replace these values:

```yaml
github:
  repo: YOUR_GITHUB_USERNAME/agent-pm  # Change this
  branch: main
```

### 4.2 Add Production Domain to CORS

If you have a custom domain, update `src/web_interface.py`:

```python
# Add your production domain
if os.getenv('FLASK_ENV') == 'production':
    production_domain = os.getenv('PRODUCTION_DOMAIN')
    if production_domain:
        cors_origins.append(f"https://{production_domain}")
```

## Step 5: Create the App on DigitalOcean

```bash
# Create the app from the config file
doctl apps create --spec .do/app.yaml

# This will output an app ID - save it!
# Example output: Notice: App created
# ID: abc123-def456-ghi789
```

## Step 6: Set Environment Variables

You have two options:

### Option A: Via CLI (Recommended for secrets)
```bash
# Set your app ID
APP_ID="your-app-id-here"

# Set backend environment variables
doctl apps update $APP_ID --spec .do/app.yaml

# Or set individual variables
doctl apps update $APP_ID \
  --env "JWT_SECRET_KEY=your-generated-secret" \
  --env "GOOGLE_CLIENT_ID=your-google-client-id" \
  --env "OPENAI_API_KEY=your-openai-key"
```

### Option B: Via Web Console
1. Go to https://cloud.digitalocean.com/apps
2. Click on your app
3. Go to Settings → Environment Variables
4. Add all required variables

## Step 7: Update Frontend Configuration

After deployment, you'll get URLs for your services:
- Backend: `https://backend-xxxxx.ondigitalocean.app`
- Frontend: `https://frontend-xxxxx.ondigitalocean.app` (or your custom domain)

Update the frontend environment variables in the DigitalOcean console:
- `REACT_APP_API_URL` - Your backend URL
- `REACT_APP_GOOGLE_CLIENT_ID` - Your Google OAuth client ID

## Step 8: Deploy

```bash
# Trigger a deployment
doctl apps create-deployment $APP_ID

# Monitor deployment progress
doctl apps get-deployment $APP_ID <deployment-id>
```

Or simply push to your GitHub repository - DigitalOcean will auto-deploy!

## Step 9: Configure Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to APIs & Services → Credentials
3. Edit your OAuth 2.0 Client ID
4. Add authorized JavaScript origins:
   - `https://your-frontend-url.ondigitalocean.app`
   - Your custom domain (if any)
5. Add authorized redirect URIs:
   - `https://your-frontend-url.ondigitalocean.app`

## Step 10: Verify Deployment

```bash
# Check app status
doctl apps get $APP_ID

# View logs
doctl apps logs $APP_ID --follow

# Test health endpoint
curl https://backend-xxxxx.ondigitalocean.app/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-27T10:30:00.123456"
}
```

## Common Commands

```bash
# List all apps
doctl apps list

# Get app details
doctl apps get $APP_ID

# View logs
doctl apps logs $APP_ID --type run --follow

# Update app configuration
doctl apps update $APP_ID --spec .do/app.yaml

# Delete app
doctl apps delete $APP_ID
```

## Database Migration

DigitalOcean automatically creates and manages your PostgreSQL database. To run migrations:

```bash
# Connect to your database (get connection string from console)
DATABASE_URL="postgresql://user:pass@host:port/db"

# The app will auto-create tables on first run via SQLAlchemy
# If you need to run manual migrations:
doctl databases db exec $DB_ID --command "SELECT * FROM users;"
```

## Custom Domain (Optional)

1. Go to your app in DigitalOcean console
2. Settings → Domains
3. Add your custom domain
4. Update your DNS provider with the CNAME records shown
5. Wait for DNS propagation (up to 24 hours)

## Troubleshooting

### App won't start
```bash
# Check build logs
doctl apps logs $APP_ID --type build --follow

# Check runtime logs
doctl apps logs $APP_ID --type run --follow
```

### Database connection issues
- Verify `DATABASE_URL` is set correctly
- Check database is in the same region as your app
- Ensure database is trusted source for your app

### Frontend can't reach backend
- Verify `REACT_APP_API_URL` points to backend URL
- Check CORS settings in `src/web_interface.py`
- Ensure both services are running

### Authentication issues
- Verify Google OAuth redirect URIs match your deployment URL
- Check `GOOGLE_CLIENT_ID` is set in both backend and frontend
- Ensure `JWT_SECRET_KEY` is properly set

## Monitoring & Scaling

### View metrics
```bash
# App metrics
doctl apps get $APP_ID

# Database metrics
doctl databases get $DB_ID
```

### Scale your app
Edit `.do/app.yaml`:
```yaml
services:
  - name: backend
    instance_count: 2  # Scale to 2 instances
    instance_size_slug: professional-m  # Upgrade size
```

Then update:
```bash
doctl apps update $APP_ID --spec .do/app.yaml
```

## Cost Estimate

- **Basic Plan** (~$17/month):
  - Backend: Professional XS ($12)
  - Frontend: Basic XS ($5)
  - Database: Managed PostgreSQL (~$15)
  - **Total: ~$32/month**

- **Production Plan** (~$50/month):
  - Backend: Professional S ($24)
  - Frontend: Basic XXS ($3)
  - Database: Managed PostgreSQL (~$15)
  - **Total: ~$42/month**

## Security Best Practices

1. **Never commit secrets**: Use environment variables
2. **Enable HTTPS**: DigitalOcean provides free SSL certificates
3. **Rotate secrets regularly**: Update JWT keys, API tokens periodically
4. **Use database backups**: Enable automated backups in console
5. **Monitor logs**: Set up alerts for errors and suspicious activity
6. **Restrict access**: Use security groups to limit database access

## Support

- **DigitalOcean Docs**: https://docs.digitalocean.com/products/app-platform/
- **Community**: https://www.digitalocean.com/community/
- **App Platform Status**: https://status.digitalocean.com/

## Quick Reference

```bash
# Essential commands
doctl apps list                              # List apps
doctl apps get $APP_ID                       # Get app details
doctl apps logs $APP_ID --follow             # Stream logs
doctl apps update $APP_ID --spec .do/app.yaml  # Update config
doctl apps create-deployment $APP_ID         # Trigger deployment
doctl apps delete $APP_ID                    # Delete app
```
