-- Quick SQL queries to check insights storage issue
-- Run with: psql $DATABASE_URL -f scripts/check_insights.sql

\echo '========================================='
\echo 'INSIGHTS STORAGE DIAGNOSTIC'
\echo '========================================='
\echo ''

\echo '1. Total insights in database:'
SELECT COUNT(*) as total_insights FROM proactive_insights;
\echo ''

\echo '2. Insights created in last 24 hours:'
SELECT COUNT(*) as recent_insights
FROM proactive_insights
WHERE created_at >= NOW() - INTERVAL '24 hours';
\echo ''

\echo '3. Insights by type:'
SELECT
    insight_type,
    COUNT(*) as count,
    COUNT(CASE WHEN dismissed_at IS NULL THEN 1 END) as active
FROM proactive_insights
GROUP BY insight_type
ORDER BY count DESC;
\echo ''

\echo '4. Insights by severity (active only):'
SELECT
    severity,
    COUNT(*) as count
FROM proactive_insights
WHERE dismissed_at IS NULL
GROUP BY severity
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'warning' THEN 2
        WHEN 'info' THEN 3
    END;
\echo ''

\echo '5. Most recent insights (last 10):'
SELECT
    id,
    insight_type,
    severity,
    title,
    project_key,
    created_at,
    LEFT(description, 80) || '...' as description_preview
FROM proactive_insights
ORDER BY created_at DESC
LIMIT 10;
\echo ''

\echo '6. Active users with watched projects:'
SELECT
    u.id,
    u.email,
    COUNT(DISTINCT uwp.project_key) as watched_projects
FROM users u
LEFT JOIN user_watched_projects uwp ON u.id = uwp.user_id
WHERE u.is_active = true
GROUP BY u.id, u.email
ORDER BY watched_projects DESC;
\echo ''

\echo '7. Insights per user (last 24 hours):'
SELECT
    u.email,
    COUNT(pi.id) as insights_count,
    COUNT(CASE WHEN pi.dismissed_at IS NULL THEN 1 END) as active_count
FROM users u
LEFT JOIN proactive_insights pi ON u.id = pi.user_id
    AND pi.created_at >= NOW() - INTERVAL '24 hours'
WHERE u.is_active = true
GROUP BY u.email
ORDER BY insights_count DESC;
\echo ''

\echo '8. Check for storage errors (look for gaps in IDs or timestamps):'
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as insights_created
FROM proactive_insights
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC
LIMIT 24;
\echo ''

\echo '========================================='
\echo 'DIAGNOSTIC COMPLETE'
\echo '========================================='
