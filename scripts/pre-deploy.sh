#!/bin/bash

# Pre-deployment validation script
# Run this before every deployment to catch issues early

set -e  # Exit on any error

echo "🔍 Starting pre-deployment checks..."

# 1. Run Python tests
echo "\n✅ Running Python tests..."
python -m pytest tests/ -v --tb=short

# 2. Run frontend build
echo "\n🏗️  Building frontend..."
cd frontend && npm run build && cd ..

# 3. Type checking (if you have mypy configured)
echo "\n🔎 Running type checks..."
python -m mypy src/ --ignore-missing-imports || echo "⚠️  Type check warnings (non-blocking)"

# 4. Linting
echo "\n🧹 Running linter..."
python -m flake8 src/ --max-line-length=120 --extend-ignore=E203,W503 || echo "⚠️  Lint warnings (non-blocking)"

# 5. Check for common issues
echo "\n🔍 Checking for common issues..."
# Check for print statements (should use logger)
if grep -r "print(" src/ --include="*.py" | grep -v "__pycache__" | grep -v ".pyc" | grep -v "# OK to print"; then
    echo "⚠️  Warning: Found print() statements. Use logger instead."
fi

# Check for unhandled exceptions
if grep -r "except:" src/ --include="*.py" | grep -v "__pycache__" | grep -v "except Exception" | grep -v "except.*as"; then
    echo "⚠️  Warning: Found bare except: clauses. Be specific about exceptions."
fi

echo "\n✅ All pre-deployment checks passed!"
echo "🚀 Safe to deploy"
