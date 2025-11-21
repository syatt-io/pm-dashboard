import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, Switch, Checkbox, FormControlLabel, CircularProgress, Alert, Paper } from '@mui/material';
import axios from 'axios';
import { getApiUrl } from '../config';

interface NotificationPreferencesData {
  user_id: number;
  enable_todo_reminders: boolean;
  todo_reminders_slack: boolean;
  todo_reminders_email: boolean;
  enable_urgent_notifications: boolean;
  urgent_notifications_slack: boolean;
  urgent_notifications_email: boolean;
  enable_weekly_reports: boolean;
  weekly_summary_slack: boolean;
  weekly_summary_email: boolean;
  weekly_hours_reports_slack: boolean;
  weekly_hours_reports_email: boolean;
  enable_escalations: boolean;
  enable_meeting_notifications: boolean;
  meeting_analysis_slack: boolean;
  meeting_analysis_email: boolean;
  enable_pm_reports: boolean;
  pm_reports_slack: boolean;
  pm_reports_email: boolean;
  daily_brief_slack: boolean;
  daily_brief_email: boolean;
  enable_stale_pr_alerts: boolean;
  enable_budget_alerts: boolean;
  enable_missing_ticket_alerts: boolean;
  enable_anomaly_alerts: boolean;
  enable_meeting_prep: boolean;
}

interface NotificationPreferencesProps {
  userRole?: 'ADMIN' | 'PM' | 'MEMBER' | 'NO_ACCESS';
}

export const NotificationPreferences: React.FC<NotificationPreferencesProps> = ({ userRole = 'ADMIN' }) => {
  const [preferences, setPreferences] = useState<NotificationPreferencesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const debounceTimer = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${getApiUrl()}/api/user/notifications/preferences`, {
        withCredentials: true,
      });
      setPreferences(response.data);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load notification preferences');
    } finally {
      setLoading(false);
    }
  };

  const updatePreference = async (updates: Partial<NotificationPreferencesData>) => {
    if (!preferences) return;

    // Update local state immediately
    setPreferences({ ...preferences, ...updates });

    // Clear existing timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Debounce API call
    debounceTimer.current = setTimeout(async () => {
      try {
        setSaving(true);
        await axios.put(`${getApiUrl()}/api/user/notifications/preferences`, updates, {
          withCredentials: true,
        });
        setSaving(false);
      } catch (err: any) {
        setError(err.response?.data?.error || 'Failed to update preferences');
        setSaving(false);
        // Refetch to restore correct values
        fetchPreferences();
      }
    }, 1000);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={3}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={2}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (!preferences) return null;

  // Determine which notifications to show based on user role
  const shouldShowNotification = (notificationType: string): boolean => {
    if (userRole === 'ADMIN') {
      // Admins see all notifications
      return true;
    }

    if (userRole === 'PM') {
      // PMs see only: Weekly Hours Reports, PM Reports, and Proactive Insights
      const pmNotifications = [
        'weekly_hours_reports',
        'pm_reports',
        'budget_alerts',
        'anomaly_alerts',
        'meeting_prep'
      ];
      return pmNotifications.includes(notificationType);
    }

    if (userRole === 'MEMBER') {
      // Members see only: TODO Reminders, Meeting Analysis, and Meeting Prep
      const memberNotifications = [
        'todo_reminders',
        'meeting_analysis',
        'meeting_prep'
      ];
      return memberNotifications.includes(notificationType);
    }

    // Default: no access
    return false;
  };

  const NotificationGroup = ({
    title,
    description,
    enableKey,
    slackKey,
    emailKey,
    slackOnly = false
  }: {
    title: string;
    description: string;
    enableKey: keyof NotificationPreferencesData;
    slackKey?: keyof NotificationPreferencesData;
    emailKey?: keyof NotificationPreferencesData;
    slackOnly?: boolean;
  }) => {
    const isEnabled = Boolean(preferences[enableKey]);

    return (
      <Paper elevation={0} sx={{ p: 2, mb: 2, backgroundColor: 'grey.50', border: '1px solid', borderColor: 'grey.200', borderRadius: '8px' }}>
        <Box display="flex" alignItems="flex-start" justifyContent="space-between">
          <Box flex={1} mr={2}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              {title}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {description}
            </Typography>
            {slackOnly && (
              <Typography variant="caption" color="warning.main" sx={{ fontStyle: 'italic' }}>
                Note: Email delivery not yet implemented
              </Typography>
            )}
          </Box>
          <Box display="flex" alignItems="center" gap={2}>
            <FormControlLabel
              control={
                <Switch
                  checked={isEnabled}
                  onChange={(e) => updatePreference({ [enableKey]: e.target.checked })}
                  color="primary"
                />
              }
              label="Enable"
            />
            {slackKey && (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={Boolean(preferences[slackKey])}
                    onChange={(e) => updatePreference({ [slackKey]: e.target.checked })}
                    disabled={!isEnabled}
                    size="small"
                  />
                }
                label="Slack"
              />
            )}
            {emailKey && !slackOnly && (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={Boolean(preferences[emailKey])}
                    onChange={(e) => updatePreference({ [emailKey]: e.target.checked })}
                    disabled={!isEnabled}
                    size="small"
                  />
                }
                label="Email"
              />
            )}
          </Box>
        </Box>
      </Paper>
    );
  };

  return (
    <Box p={3} sx={{ backgroundColor: 'background.default' }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Typography variant="h6" fontWeight={600}>
          Notification Preferences
        </Typography>
        {saving && (
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress size={16} />
            <Typography variant="caption" color="text.secondary">
              Saving...
            </Typography>
          </Box>
        )}
      </Box>

      {shouldShowNotification('todo_reminders') && (
        <NotificationGroup
          title="TODO Reminders"
          description="Daily digest at 9 AM, due today reminders at 9:30 AM, and overdue reminders at 10 AM & 2 PM EST. Lists active TODOs grouped by project."
          enableKey="enable_todo_reminders"
          slackKey="todo_reminders_slack"
          emailKey="todo_reminders_email"
        />
      )}

      {shouldShowNotification('urgent_notifications') && (
        <NotificationGroup
          title="Urgent Notifications"
          description="Sent every 2 hours during work hours (9 AM - 5 PM EST). Alerts for items needing immediate attention."
          enableKey="enable_urgent_notifications"
          slackKey="urgent_notifications_slack"
          emailKey="urgent_notifications_email"
        />
      )}

      {shouldShowNotification('weekly_summary') && (
        <NotificationGroup
          title="Weekly Summary"
          description="Sent Mondays at 9 AM EST. Summary of completed and pending TODOs from previous week."
          enableKey="enable_weekly_reports"
          slackKey="weekly_summary_slack"
          emailKey="weekly_summary_email"
        />
      )}

      {shouldShowNotification('weekly_hours_reports') && (
        <NotificationGroup
          title="Weekly Hours Reports"
          description="Sent Mondays at 10 AM EST. Hours tracking compliance report with team member hours and compliance percentages."
          enableKey="enable_weekly_reports"
          slackKey="weekly_hours_reports_slack"
          emailKey="weekly_hours_reports_email"
        />
      )}

      {shouldShowNotification('escalations') && (
        <NotificationGroup
          title="Escalations"
          description="Sent every 6 hours (6 AM, 12 PM, 6 PM, 12 AM EST). Auto-escalation of stale insights with increasing severity levels."
          enableKey="enable_escalations"
          slackKey="urgent_notifications_slack"
          emailKey="urgent_notifications_email"
        />
      )}

      {shouldShowNotification('meeting_analysis') && (
        <NotificationGroup
          title="Meeting Analysis"
          description="Sent after nightly meeting analysis (7 AM UTC / 3 AM EST). AI-generated summary, topics, action items, and decisions."
          enableKey="enable_meeting_notifications"
          slackKey="meeting_analysis_slack"
          emailKey="meeting_analysis_email"
        />
      )}

      {shouldShowNotification('pm_reports') && (
        <NotificationGroup
          title="PM Reports"
          description="Comprehensive PM insights including time tracking compliance (Mondays 10 AM), epic reconciliation (3rd of month 9 AM), and job monitoring digest (daily 9 AM EST)."
          enableKey="enable_pm_reports"
          slackKey="pm_reports_slack"
          emailKey="pm_reports_email"
        />
      )}

      {shouldShowNotification('daily_brief') && (
        <NotificationGroup
          title="Daily Brief"
          description="Sent daily at 9:05 AM EST. Top 5 insights grouped by severity (critical/warning/info) with dashboard link."
          enableKey="enable_budget_alerts"
          slackKey="daily_brief_slack"
          emailKey="daily_brief_email"
        />
      )}

      {(shouldShowNotification('budget_alerts') || shouldShowNotification('anomaly_alerts') || shouldShowNotification('meeting_prep')) && (
        <Typography variant="subtitle2" fontWeight={600} mt={3} mb={2}>
          Proactive Insights (delivered via Daily Brief)
        </Typography>
      )}

      {shouldShowNotification('budget_alerts') && (
        <NotificationGroup
          title="Budget Alerts"
          description="Projects using >75% of monthly budget with >40% time remaining."
          enableKey="enable_budget_alerts"
          slackKey="daily_brief_slack"
          emailKey="daily_brief_email"
        />
      )}

      {shouldShowNotification('anomaly_alerts') && (
        <NotificationGroup
          title="Anomaly Alerts"
          description="Unusual patterns in hours, velocity, or meetings based on historical data."
          enableKey="enable_anomaly_alerts"
          slackKey="daily_brief_slack"
          emailKey="daily_brief_email"
        />
      )}

      {shouldShowNotification('meeting_prep') && (
        <NotificationGroup
          title="Meeting Prep"
          description="Project activity digest for meetings scheduled today."
          enableKey="enable_meeting_prep"
          slackKey="meeting_analysis_slack"
          emailKey="meeting_analysis_email"
        />
      )}
    </Box>
  );
};
