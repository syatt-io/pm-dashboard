#!/bin/bash
# Quick test to manually trigger a Jira ingestion and monitor it

echo "🧪 Testing Nightly Ingestion Jobs"
echo "=================================="
echo ""

# Get admin key
ADMIN_KEY=$(doctl apps spec get a2255a3b-23cc-4fd0-baa8-91d622bb912a --format json 2>/dev/null | python3 -c "import json, sys; spec = json.load(sys.stdin); envs = spec['services'][0]['envs']; admin_key = next((e for e in envs if e['key'] == 'ADMIN_API_KEY'), None); print(admin_key.get('value', '')) if admin_key else print('')" 2>/dev/null)

if [ -z "$ADMIN_KEY" ]; then
    echo "❌ Could not retrieve ADMIN_API_KEY"
    exit 1
fi

echo "✅ Retrieved admin key"
echo ""

# Step 1: Check current sync status
echo "📊 Step 1: Checking current sync status..."
echo ""
curl -s -H "X-Admin-Key: $ADMIN_KEY" "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/sync-status" | python3 -m json.tool
echo ""
echo ""

# Step 2: Trigger a test ingestion (1 day of Jira data)
echo "🚀 Step 2: Triggering test Jira ingestion (1 day)..."
echo ""
TRIGGER_RESPONSE=$(curl -s -X POST -H "X-Admin-Key: $ADMIN_KEY" "https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/jira?days=1")
echo "$TRIGGER_RESPONSE" | python3 -m json.tool
echo ""

# Extract task ID if it's a Celery task
TASK_ID=$(echo "$TRIGGER_RESPONSE" | python3 -c "import json, sys; data = json.load(sys.stdin); print(data.get('task_id', 'background'))" 2>/dev/null)

if [ "$TASK_ID" != "background" ] && [ -n "$TASK_ID" ]; then
    echo "📋 Task ID: $TASK_ID"
    echo ""
    echo "⏳ Step 3: Monitoring Celery worker for task execution..."
    echo "   (This may take 30-60 seconds)"
    echo ""

    # Monitor for 60 seconds
    doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker --tail 100 2>&1 | grep -E "Jira|$TASK_ID|succeeded|failed|ERROR" &
    MONITOR_PID=$!

    sleep 60
    kill $MONITOR_PID 2>/dev/null || true
else
    echo "⏳ Step 3: Monitoring app logs for background task..."
    echo "   (This may take 2-3 minutes for async task)"
    echo ""

    # Monitor app logs for background thread execution
    doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a app --tail 200 2>&1 | grep -E "Jira backfill|Starting|complete|ingested|ERROR" | tail -20
fi

echo ""
echo "✅ Test complete!"
echo ""
echo "💡 To verify:"
echo "   1. Check sync status again to see if timestamp updated"
echo "   2. Run: curl -s -H 'X-Admin-Key: \$ADMIN_KEY' 'https://agent-pm-tsbbb.ondigitalocean.app/api/backfill/sync-status'"
