#!/bin/bash
# Diagnostic script to check vector sync status and trigger backfills
# Usage: ./diagnose_vector_sync.sh <ADMIN_API_KEY>

set -e

if [ -z "$1" ]; then
    echo "❌ Error: ADMIN_API_KEY required"
    echo "Usage: $0 <ADMIN_API_KEY>"
    echo ""
    echo "Get the key from DigitalOcean:"
    echo "  doctl apps spec get a2255a3b-23cc-4fd0-baa8-91d622bb912a --format json | jq '.services[0].envs[] | select(.key==\"ADMIN_API_KEY\")'"
    exit 1
fi

ADMIN_KEY="$1"
BASE_URL="https://agent-pm-tsbbb.ondigitalocean.app"

echo "🔍 Vector Database Sync Diagnostic"
echo "===================================="
echo ""

# Step 1: Check sync status
echo "📊 Step 1: Checking sync status..."
SYNC_RESPONSE=$(curl -s -H "X-Admin-Key: $ADMIN_KEY" "$BASE_URL/api/backfill/sync-status")
echo "$SYNC_RESPONSE" | python3 -m json.tool

echo ""
echo "📈 Parsing results..."
STALE_COUNT=$(echo "$SYNC_RESPONSE" | python3 -c "import json, sys; data = json.load(sys.stdin); print(data.get('stale_count', 'unknown'))")
TOTAL_SOURCES=$(echo "$SYNC_RESPONSE" | python3 -c "import json, sys; data = json.load(sys.stdin); print(data.get('total_sources', 'unknown'))")

echo ""
if [ "$STALE_COUNT" = "unknown" ] || [ "$TOTAL_SOURCES" = "unknown" ]; then
    echo "⚠️  Could not parse sync status"
    exit 1
elif [ "$STALE_COUNT" -eq 0 ] && [ "$TOTAL_SOURCES" -gt 0 ]; then
    echo "✅ All sources are fresh!"
    exit 0
elif [ "$TOTAL_SOURCES" -eq 0 ]; then
    echo "🔴 No sync records found - vector ingestion has NEVER run!"
    echo ""
    echo "💡 Recommendation: Trigger initial backfill for all sources"
    echo ""
    read -p "Would you like to trigger backfills now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "🚀 Triggering backfills..."
        echo ""

        echo "  📝 Jira (30 days)..."
        curl -s -X POST -H "X-Admin-Key: $ADMIN_KEY" "$BASE_URL/api/backfill/jira?days=30" | python3 -m json.tool

        echo ""
        echo "  💬 Slack (30 days)..."
        curl -s -X POST -H "X-Admin-Key: $ADMIN_KEY" "$BASE_URL/api/backfill/slack?days=30" | python3 -c "import json, sys; data = json.load(sys.stdin); print(f\"Status: {data.get('status', 'unknown')}\")"

        echo ""
        echo "  📄 Notion (30 days)..."
        curl -s -X POST -H "X-Admin-Key: $ADMIN_KEY" "$BASE_URL/api/backfill/notion?days=30" | python3 -c "import json, sys; data = json.load(sys.stdin); print(f\"Status: {data.get('status', 'unknown')}\")"

        echo ""
        echo "  🎙️  Fireflies (30 days)..."
        curl -s -X POST -H "X-Admin-Key: $ADMIN_KEY" "$BASE_URL/api/backfill/fireflies?days=30" | python3 -c "import json, sys; data = json.load(sys.stdin); print(f\"Status: {data.get('status', 'unknown')}\")"

        echo ""
        echo "✅ Backfill tasks started!"
        echo "⏳ Check Celery worker logs for progress:"
        echo "   doctl apps logs a2255a3b-23cc-4fd0-baa8-91d622bb912a celery-worker --tail 100"
    fi
else
    echo "⚠️  Found $STALE_COUNT stale sources out of $TOTAL_SOURCES total"
    echo ""
    echo "💡 Recommendation: Check Celery Beat scheduler and worker logs"
fi
