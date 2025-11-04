#!/usr/bin/env python3
"""Test script to preview the digest format."""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import TodoItem

# Mock some TODOs for testing
mock_todos = [
    TodoItem(
        id="1",
        title="Update API documentation",
        description="Add examples for new endpoints and update parameter descriptions",
        assignee="John Doe",
        project_key="SUBS"
    ),
    TodoItem(
        id="2",
        title="Fix login bug",
        description="Users are getting 401 errors on login",
        assignee="Jane Smith",
        project_key="SUBS"
    ),
    TodoItem(
        id="3",
        title="Review PR #123",
        description="Code review for authentication feature",
        assignee="John Doe",
        project_key="SATG"
    ),
    TodoItem(
        id="4",
        title="Database migration",
        description="Add indexes for performance improvement on user queries",
        assignee="Bob Johnson",
        project_key="SATG"
    ),
    TodoItem(
        id="5",
        title="Update dependencies",
        description=None,
        assignee=None,
        project_key=None
    ),
]

# Group by project
todos_by_project = {}
for todo in mock_todos:
    project = todo.project_key or "No Project"
    if project not in todos_by_project:
        todos_by_project[project] = []
    todos_by_project[project].append(todo)

# Generate daily digest format
print("=" * 60)
print("DAILY DIGEST FORMAT PREVIEW")
print("=" * 60)
print()
body = f"📋 *Daily TODO Digest - {datetime.now().strftime('%B %d, %Y')}*\n\n"

for project in sorted(todos_by_project.keys()):
    todos = todos_by_project[project]
    body += f"*{project}*\n"
    for todo in todos:
        assignee = todo.assignee or "Unassigned"
        body += f"• {todo.title}"
        if todo.description:
            desc = todo.description[:50] + "..." if len(todo.description) > 50 else todo.description
            body += f" - {desc}"
        body += f" ({assignee})\n"
    body += "\n"

print(body)

# Generate weekly digest format
print("=" * 60)
print("WEEKLY DIGEST FORMAT PREVIEW")
print("=" * 60)
print()

week_start = datetime.now()
body = f"📊 *Weekly TODO Summary - Week of {week_start.strftime('%B %d, %Y')}*\n\n"

body += f"*✅ Completed Last Week (2 items):*\n\n"
body += f"*SUBS*\n"
body += f"• Fix login bug (Jane Smith)\n\n"

body += f"*📋 Active TODOs (5 items):*\n\n"
for project in sorted(todos_by_project.keys()):
    todos = todos_by_project[project]
    body += f"*{project}*\n"
    for todo in todos:
        assignee = todo.assignee or "Unassigned"
        body += f"• {todo.title}"
        if todo.description:
            desc = todo.description[:50] + "..." if len(todo.description) > 50 else todo.description
            body += f" - {desc}"
        body += f" ({assignee})\n"
    body += "\n"

print(body)

print("=" * 60)
print("✅ Format looks good! The digest will show:")
print("  - TODOs grouped by project")
print("  - Title + truncated description (if present)")
print("  - Assignee in parentheses")
print("  - Minimal, clean formatting")
print("=" * 60)
