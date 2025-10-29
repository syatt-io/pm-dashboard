#!/bin/bash
# Run Alembic migration for include_context field
cd /workspace
alembic upgrade head
