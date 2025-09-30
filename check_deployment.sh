#!/bin/bash

echo "🔍 Checking deployment status..."
echo ""

# Check health endpoint
echo "1. Health Check:"
curl -s https://agent-pm-tsbbb.ondigitalocean.app/api/health | python3 -m json.tool
echo ""

# Check if frontend loads
echo "2. Frontend Status:"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://agent-pm-tsbbb.ondigitalocean.app/)
if [ "$STATUS" -eq 200 ]; then
    echo "✅ Frontend is accessible (HTTP $STATUS)"
else
    echo "❌ Frontend returned HTTP $STATUS"
fi
echo ""

# Check API endpoint (should return 401 without auth)
echo "3. API Authentication:"
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://agent-pm-tsbbb.ondigitalocean.app/api/meetings)
if [ "$API_STATUS" -eq 401 ]; then
    echo "✅ API authentication is working (returns 401 as expected)"
else
    echo "⚠️  API returned HTTP $API_STATUS (expected 401)"
fi
echo ""

echo "4. Deployment Time:"
echo "   Started: Tue Sep 30 11:29:56 EDT 2025"
echo "   Current: $(date)"
echo ""
echo "📋 If all checks pass, deployment is successful!"
echo "🔗 Access your app: https://agent-pm-tsbbb.ondigitalocean.app"