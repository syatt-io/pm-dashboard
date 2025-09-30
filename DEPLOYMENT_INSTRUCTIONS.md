# Deployment Instructions

## 🚨 BEFORE DEPLOYING - CRITICAL

### Missing Environment Variables on DigitalOcean

The following environment variables need to be added manually through DigitalOcean App Platform console:

#### 1. **GOOGLE_CLIENT_SECRET** (CRITICAL - OAuth won't work without this!)
```
Value: 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
Type: SECRET
Scope: RUN_AND_BUILD_TIME
```

#### 2. **ALLOWED_EMAIL_DOMAIN**
```
Value: @syatt.io
Type: PLAIN TEXT
Scope: RUN_AND_BUILD_TIME
```

#### 3. **ADMIN_EMAIL**
```
Value: mike.samimi@syatt.io
Type: PLAIN TEXT
Scope: RUN_AND_BUILD_TIME
```

**Note**: The ENCRYPTION_KEY is already configured in app-spec.yaml

---

## 📋 Steps to Add Environment Variables

1. Go to: https://cloud.digitalocean.com/apps
2. Select your `agent-pm` app
3. Click on "Settings" tab
4. Scroll to "Environment Variables" section under the app component
5. Click "Edit" next to your app service
6. Add each variable listed above using the "Add Variable" button
7. For SECRET types, check the "Encrypt" checkbox
8. Click "Save"
9. DO NOT deploy yet - wait for code push

---

## 🚀 Deployment Process

### Step 1: Push Code
```bash
# Code is already committed, now push
git push origin main
```

This will trigger automatic deployment since `deploy_on_push: true` is configured.

### Step 2: Monitor Deployment

Watch the deployment at: https://cloud.digitalocean.com/apps/[your-app-id]/deployments

**Expected deployment time**: 5-10 minutes

### Step 3: Verify Deployment

After deployment completes, check:

1. **Health Check**: https://agent-pm-tsbbb.ondigitalocean.app/api/health
   - Should return `{"status": "healthy"}`

2. **Frontend**: https://agent-pm-tsbbb.ondigitalocean.app
   - Should load login page with Google OAuth button

3. **Application Logs**:
   - Check for: "AuthService initialized - Domain: @syatt.io, Admin: mike.samimi@syatt.io"
   - Check for: "Database engine initialized for production"
   - NO errors about missing JWT_SECRET_KEY or other env vars

---

## 🔍 Troubleshooting

### If deployment fails:

1. **Check Application Logs**
   - Look for "CRITICAL: JWT_SECRET_KEY is not set" (shouldn't happen)
   - Look for database connection errors
   - Look for missing environment variable errors

2. **Common Issues**:

   **Issue**: "GOOGLE_CLIENT_SECRET not set"
   - **Fix**: Add GOOGLE_CLIENT_SECRET env var (see above)

   **Issue**: OAuth login fails
   - **Fix**: Verify GOOGLE_CLIENT_SECRET is correct
   - **Fix**: Check ALLOWED_EMAIL_DOMAIN is set

   **Issue**: Admin can't access
   - **Fix**: Verify ADMIN_EMAIL matches your Google account

   **Issue**: Database connection errors
   - **Fix**: Check DATABASE_URL is correct
   - **Fix**: Verify database is running

3. **Rollback if needed**:
   ```bash
   git revert HEAD
   git push origin main
   ```

---

## ✅ Post-Deployment Verification

After successful deployment, test:

### 1. Authentication Flow
- [ ] Visit https://agent-pm-tsbbb.ondigitalocean.app
- [ ] Click "Sign in with Google"
- [ ] Should redirect to Google OAuth
- [ ] Should redirect back and show dashboard
- [ ] Your email (mike.samimi@syatt.io) should have admin access

### 2. API Endpoints
```bash
# Health check
curl https://agent-pm-tsbbb.ondigitalocean.app/api/health

# Should require auth
curl https://agent-pm-tsbbb.ondigitalocean.app/api/meetings
# Should return 401 without token
```

### 3. Database Connection
- Check that meetings, todos, and learnings load
- Try creating a todo item
- Verify data persists after refresh

### 4. Jira Integration
- Check projects load: /api/jira/projects
- Verify tickets can be created

---

## 🎯 What Changed in This Deployment

### Security Improvements
- ✅ All API credentials rotated
- ✅ JWT validation enforced (app fails if misconfigured)
- ✅ Hardcoded values removed
- ✅ Encryption key added for data persistence
- ✅ Database connection pooling optimized

### Code Quality
- ✅ TypeScript type safety restored
- ✅ API URL configuration centralized
- ✅ Better error handling and logging

### New Requirements
- ⚠️ JWT_SECRET_KEY (already set)
- ⚠️ GOOGLE_CLIENT_SECRET (ADD THIS!)
- ⚠️ ALLOWED_EMAIL_DOMAIN (ADD THIS!)
- ⚠️ ADMIN_EMAIL (ADD THIS!)
- ⚠️ ENCRYPTION_KEY (already set)

---

## 📞 Need Help?

If deployment fails or you encounter issues:

1. Check DigitalOcean application logs
2. Verify all environment variables are set correctly
3. Review SECURITY_UPDATES.md for complete list of changes
4. Check that GOOGLE_CLIENT_SECRET was added (this is the most likely missing piece!)

---

## 🚦 Ready to Deploy?

1. ✅ Security fixes committed
2. ⏳ Add GOOGLE_CLIENT_SECRET to DigitalOcean (DO THIS NOW!)
3. ⏳ Add ALLOWED_EMAIL_DOMAIN to DigitalOcean
4. ⏳ Add ADMIN_EMAIL to DigitalOcean
5. ⏳ Push code: `git push origin main`
6. ⏳ Monitor deployment
7. ⏳ Test authentication flow

**Let's deploy!**