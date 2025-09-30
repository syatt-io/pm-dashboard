#!/usr/bin/env python3
"""
Run Alembic migration on production database.
"""
import os
import subprocess
import sys

# Set the DATABASE_URL environment variable from .env if available
from dotenv import load_dotenv
load_dotenv()

# Run the migration
try:
    result = subprocess.run(
        ['alembic', 'upgrade', 'head'],
        capture_output=True,
        text=True,
        check=True
    )
    print("Migration successful!")
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print(f"Migration failed: {e}")
    print(e.stdout)
    print(e.stderr)
    sys.exit(1)
