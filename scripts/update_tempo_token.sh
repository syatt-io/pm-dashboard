#!/bin/bash
# Script to update TEMPO_API_TOKEN in DigitalOcean App Platform
#
# The Tempo hours sync job is failing with a 401 Unauthorized error because
# the production TEMPO_API_TOKEN is expired or invalid.
#
# ROOT CAUSE:
# - Production has encrypted token: EV[1:jTcGznvtiZKxsAA9GEEw3HkNV2JY6BAa:...]
# - Local working token: PBl9AfH5qz7MuDjh2brtBnUt2SgzgQ-us
# - The production token needs to be updated to match the working local token
#
# SOLUTION:
# Update the TEMPO_API_TOKEN environment variable in DigitalOcean console

APP_ID="a2255a3b-23cc-4fd0-baa8-91d622bb912a"
NEW_TOKEN="PBl9AfH5qz7MuDjh2brtBnUt2SgzgQ-us"

echo "=== Tempo API Token Update Required ==="
echo ""
echo "The nightly Tempo hours sync job failed with:"
echo "  401 Client Error: Unauthorized for url: https://api.tempo.io/4/worklogs"
echo ""
echo "Root Cause:"
echo "  - Production TEMPO_API_TOKEN is expired or invalid"
echo "  - Local token ($NEW_TOKEN) is working correctly"
echo ""
echo "To fix this, update the environment variable using ONE of these methods:"
echo ""
echo "METHOD 1: DigitalOcean Console (Recommended)"
echo "  1. Go to: https://cloud.digitalocean.com/apps/$APP_ID/settings"
echo "  2. Click on 'Environment Variables' or 'app' component settings"
echo "  3. Find TEMPO_API_TOKEN and click 'Edit'"
echo "  4. Update the value to: $NEW_TOKEN"
echo "  5. Save and allow the app to redeploy"
echo ""
echo "METHOD 2: DigitalOcean API"
echo "  Use the DigitalOcean API to update the app spec"
echo "  (Requires DIGITALOCEAN_ACCESS_TOKEN)"
echo ""
echo "After updating, verify the fix by:"
echo "  1. Wait for app to redeploy (check active deployment status)"
echo "  2. Check logs: doctl apps logs $APP_ID app --type run --tail=100"
echo "  3. Manually trigger the sync job to test"
echo ""
echo "To manually test the Tempo sync job after update:"
echo "  curl -s 'https://agent-pm-tsbbb.ondigitalocean.app/api/admin/tempo-sync' \\"
echo "       -H 'X-Admin-Key: YOUR_ADMIN_KEY'"
echo ""
