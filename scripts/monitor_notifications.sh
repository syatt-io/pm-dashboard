#!/bin/bash
# Monitor notification task execution in production

APP_ID="a2255a3b-23cc-4fd0-baa8-91d622bb912a"

echo "================================"
echo "📊 Notification Tasks Monitor"
echo "================================"
echo ""

echo "🕐 Current Time (UTC): $(date -u '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "📅 Recent Celery Beat Schedules (last 10):"
echo "-------------------------------------------"
doctl apps logs $APP_ID celery-beat --tail 100 2>&1 | \
  grep "Scheduler: Sending" | \
  grep -E "(daily-todo-digest|overdue-reminders|due-today|weekly-summary|tempo-sync|urgent-items)" | \
  tail -10 | \
  sed 's/celery-beat //' | \
  sed 's/\[2025/  [2025/'

echo ""
echo "✅ Task Executions (last 10):"
echo "----------------------------"
doctl apps logs $APP_ID celery-worker --tail 200 2>&1 | \
  grep "notification_tasks" | \
  grep "succeeded" | \
  tail -10 | \
  sed 's/celery-worker //' | \
  sed 's/\[2025/  [2025/'

echo ""
echo "📋 Scheduled Tasks:"
echo "------------------"
echo "  Daily (Mon-Sun):"
echo "    • 08:00 UTC (4 AM EST)  - Tempo sync"
echo "    • 13:00 UTC (9 AM EST)  - Daily digest"
echo "    • 13:30 UTC (9:30 AM EST) - Due today reminders"
echo "    • 14:00 UTC (10 AM EST) - Overdue reminders (morning)"
echo "    • 18:00 UTC (2 PM EST)  - Overdue reminders (afternoon)"
echo "    • 13, 15, 17, 19, 21 UTC - Urgent items check"
echo ""
echo "  Weekly (Monday only):"
echo "    • 13:00 UTC (9 AM EST)  - Weekly summary"
echo "    • 14:00 UTC (10 AM EST) - Weekly hours reports"
echo ""
echo "💡 Tip: Run this script regularly to monitor task execution"
echo "💬 Check Slack #mikes-minion for actual notifications"
