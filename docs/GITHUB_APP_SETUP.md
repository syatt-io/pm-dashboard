# GitHub App Setup Guide

This guide walks you through setting up a GitHub App for the Agent PM context search feature. GitHub Apps provide better security, higher rate limits, and organization-level authentication compared to personal access tokens.

## Benefits of GitHub App vs Personal Access Token

| Feature | Personal Access Token | GitHub App |
|---------|----------------------|------------|
| **Rate Limit** | 5,000 requests/hour | 15,000 requests/hour |
| **Ownership** | Tied to individual user | Organization-owned |
| **Permissions** | Broad access | Fine-grained, scoped |
| **Audit Trail** | Shows user name | Shows app name |
| **Security** | Personal account risk | App-level isolation |
| **Sustainability** | Breaks if user leaves | Persists with org |

---

## Step 1: Create the GitHub App

### A. Navigate to GitHub App Settings

1. Go to your **organization settings**:
   - URL: `https://github.com/organizations/YOUR_ORG_NAME/settings/apps`
   - Or navigate: Organization → Settings → Developer settings → GitHub Apps

2. Click **"New GitHub App"**

### B. Configure Basic Information

Fill in the following fields:

- **GitHub App name**: `Agent PM Context Search`
  - Must be globally unique across GitHub
  - If taken, try: `Agent PM Search - YOUR_ORG`, `YOUR_ORG Agent PM`, etc.

- **Homepage URL**:
  - Your production app URL, or
  - GitHub repo: `https://github.com/YOUR_ORG/pm-dashboard`

- **Description** (optional):
  ```
  Searches GitHub PRs and commits for project context and documentation to help engineering teams find relevant information across Slack, Jira, Fireflies, and GitHub.
  ```

- **Webhook**:
  - ✅ **Uncheck "Active"** (we don't need webhooks for search-only functionality)

### C. Set Repository Permissions

These are the **minimum required permissions** for PR and commit search:

| Permission | Access Level | Why Needed |
|------------|--------------|------------|
| **Contents** | Read-only ✅ | Search commit messages and content |
| **Issues** | Read-only ✅ | GitHub treats PRs as issues for search API |
| **Pull requests** | Read-only ✅ | Search PR titles and descriptions |
| **Metadata** | Read-only ✅ | Automatically required |

**Important**: Do NOT grant write access to any permissions.

### D. Set Installation Options

- **Where can this GitHub App be installed?**
  - Select: ✅ **"Only on this account"** (your organization)
  - This prevents other organizations from installing your app

### E. Create the App

1. Click **"Create GitHub App"** at the bottom
2. You'll be redirected to your new app's settings page

---

## Step 2: Generate Private Key

After creating the app:

1. Scroll down to the **"Private keys"** section
2. Click **"Generate a private key"**
3. A `.pem` file will automatically download (e.g., `agent-pm-context-search.2025-10-08.private-key.pem`)
4. **⚠️ Save this file securely** - you cannot download it again!

### Copy the App ID

At the top of the settings page, you'll see:
```
App ID: 123456
```
**Copy this number** - you'll need it for configuration.

---

## Step 3: Install the App to Your Organization

### A. Install the App

1. In the left sidebar of your app settings, click **"Install App"**
2. Click **"Install"** next to your organization name
3. Choose **repository access**:
   - ✅ **All repositories** (recommended for comprehensive search)
   - OR **Only select repositories** (choose specific repos to search)
4. Click **"Install"**

### B. Get the Installation ID

After installation, you'll be redirected to a URL like:
```
https://github.com/organizations/YOUR_ORG/settings/installations/12345678
```

The **Installation ID** is the number at the end: `12345678`

**Copy this number** - you'll need it for configuration.

---

## Step 4: Configure Environment Variables

Now you need to add three values to your production environment:

### Values You Collected

- **App ID**: `123456` (from Step 2)
- **Installation ID**: `12345678` (from Step 3B)
- **Private Key**: Contents of the `.pem` file (from Step 2)

### Option A: Add to DigitalOcean App Platform (Production)

1. Go to your **DigitalOcean App Platform** dashboard
2. Select your app → **Settings** tab
3. Scroll to **"App-Level Environment Variables"**
4. Click **"Edit"** → **"Add Variable"**

Add these three variables:

#### 1. GITHUB_APP_ID
```
Key: GITHUB_APP_ID
Value: 123456
Type: Secret (optional, but recommended)
```

#### 2. GITHUB_APP_INSTALLATION_ID
```
Key: GITHUB_APP_INSTALLATION_ID
Value: 12345678
Type: Secret (optional, but recommended)
```

#### 3. GITHUB_APP_PRIVATE_KEY

For the private key, you have two options:

**Option 3A: Base64 Encode (Recommended for DigitalOcean)**

This ensures the multi-line PEM key works in environment variables:

```bash
# macOS/Linux
base64 < agent-pm-context-search.2025-10-08.private-key.pem | pbcopy

# The key is now in your clipboard
```

Then add:
```
Key: GITHUB_APP_PRIVATE_KEY
Value: [paste base64-encoded key]
Type: Secret ✅
```

**Option 3B: Raw PEM Key**

Copy the entire contents of the `.pem` file, including the header and footer:

```
Key: GITHUB_APP_PRIVATE_KEY
Value: -----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
...
-----END RSA PRIVATE KEY-----
Type: Secret ✅
```

#### 4. GITHUB_ORGANIZATION (Optional)

```
Key: GITHUB_ORGANIZATION
Value: your-org-name
Type: Plain text
```

5. Click **"Save"** - this will trigger a redeploy

### Option B: Add to Local Development (.env)

For local testing, add to your `.env` file:

```bash
# GitHub App Configuration (RECOMMENDED)
GITHUB_APP_ID=123456
GITHUB_APP_INSTALLATION_ID=12345678

# For local development, you can use the file path:
GITHUB_APP_PRIVATE_KEY=/path/to/agent-pm-context-search.2025-10-08.private-key.pem

# OR paste the raw key (make sure to quote it):
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
...
-----END RSA PRIVATE KEY-----"

GITHUB_ORGANIZATION=syatt-io
```

---

## Step 5: Verify Installation

### A. Check Logs

After deploying, check your application logs for:

```
✅ Using GitHub App authentication
✅ Successfully obtained GitHub App installation token
```

If you see errors like:
```
❌ GitHub App authentication failed: 401
```

Check:
1. App ID is correct
2. Installation ID is correct
3. Private key is properly formatted
4. App is installed on your organization

### B. Test with /find-context

Run a search in Slack:
```
/find-context subscriptions feature --days 30
```

Check that the results include:
```
Found X results: Y Slack, Z Fireflies, A Jira, B GitHub
```

The GitHub count confirms it's working!

---

## Step 6: Remove Personal Access Token (Optional)

Once the GitHub App is working, you can remove the old Personal Access Token:

### From DigitalOcean:
1. Go to Settings → App-Level Environment Variables
2. Remove `GITHUB_API_TOKEN`
3. Save (triggers redeploy)

### From .env:
1. Comment out or remove: `GITHUB_API_TOKEN=...`

The app will automatically use GitHub App authentication when available.

---

## Troubleshooting

### Error: "Failed to get installation token: 404"

**Cause**: Installation ID is incorrect or app isn't installed

**Fix**:
1. Go to: `https://github.com/organizations/YOUR_ORG/settings/installations`
2. Click on your app
3. Check the URL for the correct Installation ID

### Error: "GitHub App authentication failed: 401"

**Cause**: App ID or private key is incorrect

**Fix**:
1. Verify App ID in GitHub App settings
2. Regenerate private key if needed:
   - GitHub App settings → Private keys → Generate new
   - Update `GITHUB_APP_PRIVATE_KEY` environment variable
   - Redeploy

### Error: "Error searching GitHub: 403"

**Cause**: Missing permissions

**Fix**:
1. Go to GitHub App settings → Permissions & events
2. Verify you have:
   - Contents: Read-only
   - Issues: Read-only
   - Pull requests: Read-only
3. Save changes
4. Organization owner must approve permission changes

### Private Key Format Issues

If you see base64 decode errors:

**Fix**:
```bash
# Verify your private key file is valid PEM format:
openssl rsa -in agent-pm-context-search.2025-10-08.private-key.pem -check

# Try base64 encoding without line breaks (if copy/paste has issues):
base64 < private-key.pem | tr -d '\n' | pbcopy
```

---

## Rate Limits

GitHub App rate limits are much higher than Personal Access Tokens:

| Endpoint | Personal Token | GitHub App |
|----------|---------------|------------|
| `/search/issues` | 30 requests/min | 30 requests/min |
| `/search/commits` | 30 requests/min | 30 requests/min |
| **Overall** | 5,000/hour | 15,000/hour |

Search endpoints have per-minute limits, but the overall hourly limit is 3x higher with GitHub Apps.

---

## Security Best Practices

1. ✅ **Never commit** the private key to git
2. ✅ **Store as secret** in DigitalOcean (not plain text)
3. ✅ **Use base64 encoding** for environment variables
4. ✅ **Rotate keys** every 90 days (optional, but recommended)
5. ✅ **Monitor usage** in GitHub App settings → Advanced → Rate limit

---

## Next Steps

- Test searches across different projects to verify repo auto-detection
- Monitor GitHub search results in Slack `/find-context` responses
- Consider adding GitHub code search in Phase 2 (requires additional permissions)

---

## Support

If you encounter issues:
1. Check application logs for detailed error messages
2. Verify all three environment variables are set correctly
3. Confirm the app is installed and has correct permissions
4. Test with a simple query first to isolate issues
