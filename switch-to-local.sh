#!/bin/bash
# Switch to local PostgreSQL environment

set -e

echo "🔄 Switching to local PostgreSQL environment..."

# Backup current .env if not already backed up
if [ ! -f .env.prod.backup ]; then
    echo "📦 Backing up current .env to .env.prod.backup..."
    cp .env .env.prod.backup
fi

# Copy local environment configuration
if [ -f .env.bak3 ]; then
    echo "✅ Restoring local configuration from .env.bak3..."
    cp .env.bak3 .env
else
    echo "❌ Error: .env.bak3 not found. Cannot restore local configuration."
    exit 1
fi

# Verify local DATABASE_URL is set correctly
if grep -q "DATABASE_URL=postgresql://pm_agent:changeme@127.0.0.1:5433/pm_agent" .env; then
    echo "✅ Local DATABASE_URL configured (port 5433)"
else
    echo "⚠️  Warning: DATABASE_URL may not be configured for local PostgreSQL"
fi

echo ""
echo "✅ Switched to local environment!"
echo ""
echo "📝 Next steps:"
echo "  1. Ensure Docker containers are running:"
echo "     docker-compose up -d"
echo ""
echo "  2. Start Flask app:"
echo "     python src/web_interface.py"
echo ""
echo "  3. To switch back to production environment, run:"
echo "     ./switch-to-prod.sh"
