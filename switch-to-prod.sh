#!/bin/bash
# Switch to production PostgreSQL environment (DigitalOcean)

set -e

echo "🔄 Switching to production PostgreSQL environment..."

# Check if production backup exists
if [ ! -f .env.prod.backup ]; then
    echo "❌ Error: .env.prod.backup not found. Cannot restore production configuration."
    echo "   Please ensure you have a backup of your production .env file."
    exit 1
fi

# Backup current local .env
echo "📦 Backing up current .env to .env.local.backup..."
cp .env .env.local.backup

# Restore production environment
echo "✅ Restoring production configuration from .env.prod.backup..."
cp .env.prod.backup .env

# Verify production DATABASE_URL is set
if grep -q "DATABASE_URL=postgresql://agentpm-db.*ondigitalocean.com" .env; then
    echo "✅ Production DATABASE_URL configured (DigitalOcean)"
else
    echo "⚠️  Warning: DATABASE_URL may not be configured for production PostgreSQL"
fi

echo ""
echo "✅ Switched to production environment!"
echo ""
echo "📝 Next steps:"
echo "  1. Start Flask app (will connect to DigitalOcean):"
echo "     python src/web_interface.py"
echo ""
echo "  2. To switch back to local environment, run:"
echo "     ./switch-to-local.sh"
echo ""
echo "⚠️  WARNING: You are now connected to the PRODUCTION database!"
