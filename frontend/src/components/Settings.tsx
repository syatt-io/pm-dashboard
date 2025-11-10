import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  Button,
  Alert,
  Snackbar,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Chip,
  Divider,
  InputAdornment,
  IconButton,
  Tabs,
  Tab,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Slider,
  FormHelperText,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Save,
  Delete,
  Visibility,
  VisibilityOff,
  CheckCircle,
  Error as ErrorIcon,
  Warning,
  Launch,
  Settings as SettingsIcon,
  SmartToy,
  Work as WorkIcon,
  People as PeopleIcon,
  Notifications as NotificationsIcon,
  TrendingUp as EscalationIcon,
} from '@mui/icons-material';
import { Loading, Title, useDataProvider, useNotify, useRedirect } from 'react-admin';
import { getApiUrl } from '../config';
import UserManagement from './UserManagement';
import { useTabWithUrl } from '../hooks/useTabWithUrl';

interface Project {
  key: string;
  name: string;
  projectTypeKey?: string;
  is_active?: boolean;
  forecasted_hours_month?: number;
  project_work_type?: 'project-based' | 'growth-support' | 'n-a';
  total_hours?: number;
  description?: string;
  current_month_hours?: number;
  cumulative_hours?: number;
  slack_channel?: string;
  weekly_meeting_day?: string;
}

interface UserSettings {
  user: {
    id: number;
    email: string;
    name: string;
    role: string;
    has_fireflies_key: boolean;
    has_google_oauth: boolean;
    has_notion_key: boolean;
    has_slack_user_token: boolean;
  };
  settings: {
    has_fireflies_key: boolean;
    fireflies_key_valid: boolean;
    has_google_oauth: boolean;
    has_notion_key: boolean;
  };
}

interface AISettings {
  ai_provider: string;
  ai_model: string | null;
  ai_temperature: number;
  ai_max_tokens: number;
  has_openai_key: boolean;
  has_anthropic_key: boolean;
  has_google_key: boolean;
  epic_auto_update_enabled: boolean;
  updated_at: string | null;
  updated_by_user_id: number | null;
}

interface AvailableModels {
  openai: Array<{ value: string; label: string }>;
  anthropic: Array<{ value: string; label: string }>;
  google: Array<{ value: string; label: string }>;
}

interface EscalationPreferences {
  user_id: number;
  enable_auto_escalation: boolean;
  enable_dm_escalation: boolean;
  enable_channel_escalation: boolean;
  enable_github_escalation: boolean;
  dm_threshold_days: number;
  channel_threshold_days: number;
  critical_threshold_days: number;
}

interface ApiResponse {
  success: boolean;
  data?: any;
  error?: string;
  message?: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`settings-tabpanel-${index}`}
      aria-labelledby={`settings-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

export const Settings = () => {
  const dataProvider = useDataProvider();
  const redirect = useRedirect();
  const [tabValue, setTabValue] = useTabWithUrl('settings-tab', 0);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);

  // Projects state
  const [allProjects, setAllProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' | 'warning' | 'info' });
  const [deleteDialog, setDeleteDialog] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; message: string } | null>(null);

  // Notion state
  const [notionApiKey, setNotionApiKey] = useState('');
  const [showNotionKey, setShowNotionKey] = useState(false);
  const [savingNotion, setSavingNotion] = useState(false);
  const [deletingNotion, setDeletingNotion] = useState(false);
  const [validatingNotion, setValidatingNotion] = useState(false);
  const [deleteNotionDialog, setDeleteNotionDialog] = useState(false);
  const [notionValidationResult, setNotionValidationResult] = useState<{ valid: boolean; message: string } | null>(null);

  // Google OAuth state
  const [deletingGoogle, setDeletingGoogle] = useState(false);
  const [deleteGoogleDialog, setDeleteGoogleDialog] = useState(false);

  // Slack OAuth state
  const [deletingSlack, setDeletingSlack] = useState(false);
  const [deleteSlackDialog, setDeleteSlackDialog] = useState(false);

  // Notification preferences state
  const [notificationPrefs, setNotificationPrefs] = useState({
    notify_daily_todo_digest: true,
    notify_project_hours_forecast: true,
    slack_connected: false,
    daily_brief_slack: true,
    daily_brief_email: false,
    enable_stale_pr_alerts: true,
    enable_budget_alerts: true,
    enable_missing_ticket_alerts: true,
    enable_anomaly_alerts: true,
    enable_meeting_prep: true,
    daily_brief_time: "09:00",
    timezone: "America/New_York"
  });
  const [loadingNotifPrefs, setLoadingNotifPrefs] = useState(false);
  const [savingNotifPrefs, setSavingNotifPrefs] = useState(false);

  // AI Settings state (admin only)
  const [aiSettings, setAISettings] = useState<AISettings | null>(null);
  const [availableModels, setAvailableModels] = useState<AvailableModels | null>(null);
  const [loadingAI, setLoadingAI] = useState(false);
  const [savingAI, setSavingAI] = useState(false);
  const [customModel, setCustomModel] = useState('');
  const [showCustomModelInput, setShowCustomModelInput] = useState(false);
  const [aiApiKeys, setAIApiKeys] = useState({
    openai: '',
    anthropic: '',
    google: ''
  });
  const [showAIKeys, setShowAIKeys] = useState({
    openai: false,
    anthropic: false,
    google: false
  });
  const [deleteAIKeyDialog, setDeleteAIKeyDialog] = useState<string | null>(null);
  const [deletingAIKey, setDeletingAIKey] = useState(false);

  // Escalation preferences state
  const [escalationPrefs, setEscalationPrefs] = useState<EscalationPreferences | null>(null);
  const [loadingEscalation, setLoadingEscalation] = useState(false);
  const [savingEscalation, setSavingEscalation] = useState(false);

  // Load user settings on component mount
  useEffect(() => {
    loadSettings();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load AI settings and models if user is admin
  useEffect(() => {
    if (settings?.user?.role === 'admin') {
      loadAISettings();
      loadAvailableModels();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings?.user?.role]);

  // Load projects when Project Settings tab is accessed
  useEffect(() => {
    if (tabValue === 1) { // Project Settings tab
      loadProjects();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabValue]);

  // Load notification preferences when Notifications tab is accessed
  useEffect(() => {
    if (tabValue === 2) { // Notifications tab
      loadNotificationPreferences();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabValue]);

  // Load escalation preferences when Auto-Escalation tab is accessed
  useEffect(() => {
    if (tabValue === 3) { // Auto-Escalation tab (index 3)
      loadEscalationPreferences();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabValue]);

  // Handle OAuth callback messages from URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const success = urlParams.get('success');
    const error = urlParams.get('error');

    if (success === 'google_workspace_connected') {
      showSnackbar('Google Workspace connected successfully!', 'success');
      loadSettings();
      window.history.replaceState({}, '', '/settings');
    } else if (success === 'slack_connected') {
      showSnackbar('Slack connected successfully!', 'success');
      loadSettings();
      window.history.replaceState({}, '', '/settings');
    } else if (error) {
      const errorMessages: { [key: string]: string } = {
        'oauth_denied': 'Authorization was denied',
        'oauth_failed': 'Failed to complete authorization',
      };
      showSnackbar(errorMessages[error] || 'An error occurred', 'error');
      window.history.replaceState({}, '', '/settings');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch(getApiUrl('/api/user/settings'), {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new globalThis.Error('Failed to load settings');
      }

      const data: ApiResponse = await response.json();
      if (data.success && data.data) {
        setSettings(data.data);
      } else {
        throw new globalThis.Error(data.error || 'Failed to load settings');
      }
    } catch (error) {
      showSnackbar('Failed to load settings', 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadProjects = async () => {
    setLoadingProjects(true);
    try {
      const { data } = await dataProvider.getList('jira_projects', {
        pagination: { page: 1, perPage: 200 },
        sort: { field: 'name', order: 'ASC' },
        filter: {},
      });
      setAllProjects(data);
    } catch (error) {
      showSnackbar('Error fetching projects', 'error');
    } finally {
      setLoadingProjects(false);
    }
  };

  const handleActiveToggle = async (project: Project) => {
    try {
      const updatedProject = {
        ...project,
        is_active: !project.is_active,
      };

      await dataProvider.update('jira_projects', {
        id: project.key,
        data: updatedProject,
        previousData: project,
      });

      // Update local state instead of reloading all projects
      setAllProjects(prevProjects =>
        prevProjects.map(p =>
          p.key === project.key ? { ...p, is_active: !p.is_active } : p
        )
      );

      showSnackbar(`Project ${project.name} is now ${updatedProject.is_active ? 'active' : 'inactive'}`, 'success');
    } catch (error) {
      showSnackbar('Error updating project status', 'error');
    }
  };

  const loadNotificationPreferences = async () => {
    try {
      setLoadingNotifPrefs(true);
      const response = await fetch(getApiUrl('/api/user/notification-preferences'), {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new globalThis.Error('Failed to load notification preferences');
      }

      const data: ApiResponse = await response.json();
      if (data.success && data.data) {
        setNotificationPrefs(data.data);
      }
    } catch (error) {
      console.error('Error loading notification preferences:', error);
      showSnackbar('Error loading notification preferences', 'error');
    } finally {
      setLoadingNotifPrefs(false);
    }
  };

  const saveNotificationPreferences = async () => {
    try {
      setSavingNotifPrefs(true);
      const response = await fetch(getApiUrl('/api/user/notification-preferences'), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          notify_daily_todo_digest: notificationPrefs.notify_daily_todo_digest,
          notify_project_hours_forecast: notificationPrefs.notify_project_hours_forecast,
          daily_brief_slack: notificationPrefs.daily_brief_slack,
          daily_brief_email: notificationPrefs.daily_brief_email,
          enable_stale_pr_alerts: notificationPrefs.enable_stale_pr_alerts,
          enable_budget_alerts: notificationPrefs.enable_budget_alerts,
          enable_missing_ticket_alerts: notificationPrefs.enable_missing_ticket_alerts,
          enable_anomaly_alerts: notificationPrefs.enable_anomaly_alerts,
          enable_meeting_prep: notificationPrefs.enable_meeting_prep,
          daily_brief_time: notificationPrefs.daily_brief_time,
          timezone: notificationPrefs.timezone
        }),
      });

      if (!response.ok) {
        throw new globalThis.Error('Failed to save notification preferences');
      }

      const data: ApiResponse = await response.json();
      if (data.success) {
        showSnackbar('Notification preferences saved successfully!', 'success');
        // Reload preferences from database to confirm save
        await loadNotificationPreferences();
      } else {
        throw new globalThis.Error(data.error || 'Failed to save preferences');
      }
    } catch (error) {
      console.error('Error saving notification preferences:', error);
      showSnackbar(error instanceof Error ? error.message : 'Error saving notification preferences', 'error');
    } finally {
      setSavingNotifPrefs(false);
    }
  };

  const loadEscalationPreferences = async () => {
    try {
      setLoadingEscalation(true);
      const response = await fetch(getApiUrl('/api/user/escalation-preferences'), {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new globalThis.Error('Failed to load escalation preferences');
      }

      const data: ApiResponse = await response.json();
      if (data.success && data.data) {
        setEscalationPrefs(data.data);
      }
    } catch (error) {
      console.error('Error loading escalation preferences:', error);
      showSnackbar('Error loading escalation preferences', 'error');
    } finally {
      setLoadingEscalation(false);
    }
  };

  const saveEscalationPreferences = async () => {
    if (!escalationPrefs) return;

    // Validate thresholds before sending
    if (escalationPrefs.dm_threshold_days < 1 ||
        escalationPrefs.channel_threshold_days < 1 ||
        escalationPrefs.critical_threshold_days < 1) {
      showSnackbar('All threshold values must be at least 1 day', 'error');
      return;
    }

    try {
      setSavingEscalation(true);
      const response = await fetch(getApiUrl('/api/user/escalation-preferences'), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(escalationPrefs),
      });

      if (!response.ok) {
        // Try to get the error message from the response
        const errorData = await response.json().catch(() => null);
        const errorMessage = errorData?.error || `Failed to save escalation preferences (${response.status})`;
        throw new globalThis.Error(errorMessage);
      }

      const data: ApiResponse = await response.json();
      if (data.success) {
        showSnackbar('Auto-escalation preferences saved successfully!', 'success');
        if (data.data) {
          setEscalationPrefs(data.data);
        }
      } else {
        throw new globalThis.Error(data.error || 'Failed to save preferences');
      }
    } catch (error) {
      console.error('Error saving escalation preferences:', error);
      showSnackbar(error instanceof Error ? error.message : 'Error saving escalation preferences', 'error');
    } finally {
      setSavingEscalation(false);
    }
  };

  const loadAISettings = async () => {
    try {
      setLoadingAI(true);
      const response = await fetch(getApiUrl('/api/admin/system-settings'), {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new globalThis.Error('Failed to load AI settings');
      }

      const data: ApiResponse = await response.json();
      if (data.success && data.data) {
        setAISettings(data.data);
      }
    } catch (error) {
      console.error('Failed to load AI settings:', error);
    } finally {
      setLoadingAI(false);
    }
  };

  const loadAvailableModels = async () => {
    try {
      const response = await fetch(getApiUrl('/api/admin/system-settings/ai/models'), {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new globalThis.Error('Failed to load available models');
      }

      const data: ApiResponse = await response.json();
      if (data.success && data.data) {
        setAvailableModels(data.data);
      }
    } catch (error) {
      console.error('Failed to load available models:', error);
    }
  };

  const saveAISettings = async () => {
    if (!aiSettings) return;

    try {
      setSavingAI(true);

      const response = await fetch(getApiUrl('/api/admin/system-settings/ai'), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          ai_provider: aiSettings.ai_provider,
          ai_model: aiSettings.ai_model,
          ai_temperature: aiSettings.ai_temperature,
          ai_max_tokens: aiSettings.ai_max_tokens,
        }),
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'AI settings saved successfully', 'success');
        setAISettings(data.data);
      } else {
        throw new globalThis.Error(data.error || 'Failed to save AI settings');
      }
    } catch (error) {
      showSnackbar('Failed to save AI settings', 'error');
    } finally {
      setSavingAI(false);
    }
  };

  const saveAIAPIKey = async (provider: string) => {
    const apiKey = aiApiKeys[provider as keyof typeof aiApiKeys];
    if (!apiKey.trim()) {
      showSnackbar('API key is required', 'error');
      return;
    }

    try {
      setSavingAI(true);

      const response = await fetch(getApiUrl('/api/admin/system-settings/ai/api-key'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ provider, api_key: apiKey }),
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'API key saved successfully', 'success');
        setAIApiKeys(prev => ({ ...prev, [provider]: '' }));
        await loadAISettings();
      } else {
        throw new globalThis.Error(data.error || 'Failed to save API key');
      }
    } catch (error) {
      showSnackbar('Failed to save API key', 'error');
    } finally {
      setSavingAI(false);
    }
  };

  const deleteAIAPIKey = async (provider: string) => {
    try {
      setDeletingAIKey(true);

      const response = await fetch(getApiUrl(`/api/admin/system-settings/ai/api-key/${provider}`), {
        method: 'DELETE',
        credentials: 'include',
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'API key deleted successfully', 'success');
        setDeleteAIKeyDialog(null);
        await loadAISettings();
      } else {
        throw new globalThis.Error(data.error || 'Failed to delete API key');
      }
    } catch (error) {
      showSnackbar('Failed to delete API key', 'error');
    } finally {
      setDeletingAIKey(false);
    }
  };

  const saveEpicSettings = async () => {
    if (!aiSettings) return;

    try {
      setSavingAI(true);

      const response = await fetch(getApiUrl('/api/admin/system-settings/epic'), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          epic_auto_update_enabled: aiSettings.epic_auto_update_enabled,
        }),
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'Epic reconciliation settings saved successfully', 'success');
        setAISettings(data.data);
      } else {
        throw new globalThis.Error(data.error || 'Failed to save epic settings');
      }
    } catch (error) {
      showSnackbar('Failed to save epic reconciliation settings', 'error');
    } finally {
      setSavingAI(false);
    }
  };

  const showSnackbar = (message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseSnackbar = () => {
    setSnackbar({ ...snackbar, open: false });
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const validateApiKey = async (keyToValidate?: string) => {
    const keyValue = keyToValidate || apiKey;
    if (!keyValue.trim()) {
      setValidationResult({ valid: false, message: 'API key is required' });
      return false;
    }

    try {
      setValidating(true);
      setValidationResult(null);

      const response = await fetch(getApiUrl('/api/user/fireflies-key/validate'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ api_key: keyValue }),
      });

      const data = await response.json();
      const isValid = data.valid;

      setValidationResult({
        valid: isValid,
        message: data.message || (isValid ? 'API key is valid' : 'API key is invalid')
      });

      return isValid;
    } catch (error) {
      setValidationResult({ valid: false, message: 'Failed to validate API key' });
      return false;
    } finally {
      setValidating(false);
    }
  };

  const saveApiKey = async () => {
    if (!apiKey.trim()) {
      showSnackbar('API key is required', 'error');
      return;
    }

    const isValid = await validateApiKey();
    if (!isValid) {
      showSnackbar('Please enter a valid Fireflies API key', 'error');
      return;
    }

    try {
      setSaving(true);

      const response = await fetch(getApiUrl('/api/user/fireflies-key'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ api_key: apiKey }),
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'API key saved successfully', 'success');
        setApiKey('');
        setValidationResult(null);
        await loadSettings();
      } else {
        throw new globalThis.Error(data.error || 'Failed to save API key');
      }
    } catch (error) {
      showSnackbar('Failed to save API key', 'error');
    } finally {
      setSaving(false);
    }
  };

  const deleteApiKey = async () => {
    try {
      setDeleting(true);

      const response = await fetch(getApiUrl('/api/user/fireflies-key'), {
        method: 'DELETE',
        credentials: 'include',
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'API key deleted successfully', 'success');
        setDeleteDialog(false);
        await loadSettings();
      } else {
        throw new globalThis.Error(data.error || 'Failed to delete API key');
      }
    } catch (error) {
      showSnackbar('Failed to delete API key', 'error');
    } finally {
      setDeleting(false);
    }
  };

  const handleOpenFirefliesHelp = () => {
    window.open('https://docs.fireflies.ai/fundamentals/authorization', '_blank');
  };

  // Notion handlers
  const validateNotionKey = async (keyToValidate?: string) => {
    const keyValue = keyToValidate || notionApiKey;
    if (!keyValue.trim()) {
      setNotionValidationResult({ valid: false, message: 'API key is required' });
      return false;
    }

    try {
      setValidatingNotion(true);
      setNotionValidationResult(null);

      const response = await fetch(getApiUrl('/api/user/notion-key/validate'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ api_key: keyValue }),
      });

      const data = await response.json();
      const isValid = data.valid;

      setNotionValidationResult({
        valid: isValid,
        message: data.message || (isValid ? 'API key format is valid' : 'API key format is invalid')
      });

      return isValid;
    } catch (error) {
      setNotionValidationResult({ valid: false, message: 'Failed to validate API key' });
      return false;
    } finally {
      setValidatingNotion(false);
    }
  };

  const saveNotionKey = async () => {
    if (!notionApiKey.trim()) {
      showSnackbar('API key is required', 'error');
      return;
    }

    const isValid = await validateNotionKey();
    if (!isValid) {
      showSnackbar('Please enter a valid Notion API key', 'error');
      return;
    }

    try {
      setSavingNotion(true);

      const response = await fetch(getApiUrl('/api/user/notion-key'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ api_key: notionApiKey }),
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'Notion API key saved successfully', 'success');
        setNotionApiKey('');
        setNotionValidationResult(null);
        await loadSettings();
      } else {
        throw new globalThis.Error(data.error || 'Failed to save API key');
      }
    } catch (error) {
      showSnackbar('Failed to save Notion API key', 'error');
    } finally {
      setSavingNotion(false);
    }
  };

  const deleteNotionKey = async () => {
    try {
      setDeletingNotion(true);

      const response = await fetch(getApiUrl('/api/user/notion-key'), {
        method: 'DELETE',
        credentials: 'include',
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'Notion API key deleted successfully', 'success');
        setDeleteNotionDialog(false);
        await loadSettings();
      } else {
        throw new globalThis.Error(data.error || 'Failed to delete API key');
      }
    } catch (error) {
      showSnackbar('Failed to delete Notion API key', 'error');
    } finally {
      setDeletingNotion(false);
    }
  };

  const handleOpenNotionHelp = () => {
    window.open('https://developers.notion.com/docs/create-a-notion-integration', '_blank');
  };

  // Google OAuth handlers
  const handleGoogleAuthorize = async () => {
    try {
      const response = await fetch(getApiUrl('/api/auth/google/workspace/authorize'), {
        method: 'GET',
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to initiate OAuth flow');
      }

      const data = await response.json();

      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        throw new Error('No authorization URL returned');
      }
    } catch (error) {
      console.error('Error initiating Google OAuth:', error);
      showSnackbar('Failed to start Google authorization', 'error');
    }
  };

  const deleteGoogleOAuth = async () => {
    try {
      setDeletingGoogle(true);

      const response = await fetch(getApiUrl('/api/user/google-oauth'), {
        method: 'DELETE',
        credentials: 'include',
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'Google OAuth token deleted successfully', 'success');
        setDeleteGoogleDialog(false);
        await loadSettings();
      } else {
        throw new globalThis.Error(data.error || 'Failed to delete OAuth token');
      }
    } catch (error) {
      showSnackbar('Failed to delete Google OAuth token', 'error');
    } finally {
      setDeletingGoogle(false);
    }
  };

  const handleOpenGoogleHelp = () => {
    window.open('https://console.cloud.google.com/apis/credentials', '_blank');
  };

  // Slack OAuth handlers
  const handleSlackAuthorize = async () => {
    try {
      const response = await fetch(getApiUrl('/api/auth/slack/authorize'), {
        method: 'GET',
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to initiate OAuth flow');
      }

      const data = await response.json();

      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        throw new Error('No authorization URL returned');
      }
    } catch (error) {
      console.error('Error initiating Slack OAuth:', error);
      showSnackbar('Failed to start Slack authorization', 'error');
    }
  };

  const deleteSlackToken = async () => {
    try {
      setDeletingSlack(true);

      const response = await fetch(getApiUrl('/api/user/slack-token'), {
        method: 'DELETE',
        credentials: 'include',
      });

      const data: ApiResponse = await response.json();

      if (data.success) {
        showSnackbar(data.message || 'Slack connection removed successfully', 'success');
        setDeleteSlackDialog(false);
        await loadSettings();
      } else {
        throw new globalThis.Error(data.error || 'Failed to disconnect Slack');
      }
    } catch (error) {
      showSnackbar('Failed to disconnect Slack', 'error');
    } finally {
      setDeletingSlack(false);
    }
  };

  const handleOpenSlackHelp = () => {
    window.open('https://api.slack.com/apps', '_blank');
  };

  if (loading) {
    return <Loading />;
  }

  if (!settings) {
    return (
      <Box p={3}>
        <Alert severity="error">Failed to load settings</Alert>
      </Box>
    );
  }

  return (
    <Box p={3}>
      <Title title="Settings" />

      {/* User Information */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            👤 User Information
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
            <Box>
              <Typography variant="body2" color="text.secondary">Name</Typography>
              <Typography variant="body1">{settings.user.name}</Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">Email</Typography>
              <Typography variant="body1">{settings.user.email}</Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">Role</Typography>
              <Chip
                label={settings.user.role}
                color={settings.user.role === 'admin' ? 'primary' : 'default'}
                size="small"
              />
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={handleTabChange} aria-label="settings tabs">
          <Tab icon={<SettingsIcon />} label="My Integrations" iconPosition="start" />
          <Tab icon={<WorkIcon />} label="Project Settings" iconPosition="start" />
          <Tab icon={<NotificationsIcon />} label="Notifications" iconPosition="start" />
          <Tab icon={<EscalationIcon />} label="Auto-Escalation" iconPosition="start" />
          {settings.user.role === 'admin' && <Tab icon={<SmartToy />} label="AI Configuration" iconPosition="start" />}
          {settings.user.role === 'admin' && <Tab icon={<PeopleIcon />} label="User Management" iconPosition="start" />}
        </Tabs>
      </Box>

      {/* Tab 1: My Integrations */}
      <TabPanel value={tabValue} index={0}>
        {/* Fireflies Integration */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">
                🔥 Fireflies.ai Integration
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<Launch />}
                onClick={handleOpenFirefliesHelp}
              >
                Get API Key
              </Button>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Current Status
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  icon={settings.settings.has_fireflies_key ? <CheckCircle /> : <ErrorIcon />}
                  label={settings.settings.has_fireflies_key ? 'API Key Configured' : 'No API Key'}
                  color={settings.settings.has_fireflies_key ? 'success' : 'error'}
                  size="small"
                />
                {settings.settings.has_fireflies_key && (
                  <Chip
                    icon={settings.settings.fireflies_key_valid ? <CheckCircle /> : <Warning />}
                    label={settings.settings.fireflies_key_valid ? 'Valid' : 'Invalid'}
                    color={settings.settings.fireflies_key_valid ? 'success' : 'warning'}
                    size="small"
                  />
                )}
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="body2" color="text.secondary" gutterBottom>
              Configure your Fireflies API key to access your meeting transcripts
            </Typography>

            <Box sx={{ mt: 2 }}>
              <TextField
                fullWidth
                label="Fireflies API Key"
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setValidationResult(null);
                }}
                placeholder="Enter your Fireflies API key"
                helperText="Your API key will be encrypted and stored securely"
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        aria-label="toggle password visibility"
                        onClick={() => setShowApiKey(!showApiKey)}
                        edge="end"
                      >
                        {showApiKey ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
                sx={{ mb: 2 }}
              />

              {validationResult && (
                <Alert
                  severity={validationResult.valid ? 'success' : 'error'}
                  sx={{ mb: 2 }}
                >
                  {validationResult.message}
                </Alert>
              )}

              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Button
                  variant="outlined"
                  onClick={() => validateApiKey()}
                  disabled={!apiKey.trim() || validating}
                  startIcon={validating ? <CircularProgress size={16} /> : <CheckCircle />}
                >
                  {validating ? 'Validating...' : 'Validate'}
                </Button>

                <Button
                  variant="contained"
                  onClick={saveApiKey}
                  disabled={!apiKey.trim() || saving}
                  startIcon={saving ? <CircularProgress size={16} /> : <Save />}
                >
                  {saving ? 'Saving...' : 'Save API Key'}
                </Button>

                {settings.settings.has_fireflies_key && (
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={() => setDeleteDialog(true)}
                    startIcon={<Delete />}
                  >
                    Delete API Key
                  </Button>
                )}
              </Box>
            </Box>

            <Alert severity="info" sx={{ mt: 3 }}>
              <Typography variant="body2">
                <strong>How to get your Fireflies API key:</strong>
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                1. Log into your Fireflies.ai account<br />
                2. Go to Settings → Integrations → API<br />
                3. Copy your API key and paste it above<br />
                4. Click "Save API Key" to secure it
              </Typography>
            </Alert>
          </CardContent>
        </Card>

        {/* Notion Integration */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">
                📝 Notion Integration
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<Launch />}
                onClick={handleOpenNotionHelp}
              >
                Get API Key
              </Button>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Current Status
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  icon={settings.settings.has_notion_key ? <CheckCircle /> : <ErrorIcon />}
                  label={settings.settings.has_notion_key ? 'API Key Configured' : 'No API Key'}
                  color={settings.settings.has_notion_key ? 'success' : 'error'}
                  size="small"
                />
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="body2" color="text.secondary" gutterBottom>
              Configure your Notion API key to access your pages and databases
            </Typography>

            <Box sx={{ mt: 2 }}>
              <TextField
                fullWidth
                label="Notion API Key"
                type={showNotionKey ? 'text' : 'password'}
                value={notionApiKey}
                onChange={(e) => {
                  setNotionApiKey(e.target.value);
                  setNotionValidationResult(null);
                }}
                placeholder="secret_..."
                helperText="Your API key will be encrypted and stored securely"
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        aria-label="toggle password visibility"
                        onClick={() => setShowNotionKey(!showNotionKey)}
                        edge="end"
                      >
                        {showNotionKey ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
                sx={{ mb: 2 }}
              />

              {notionValidationResult && (
                <Alert
                  severity={notionValidationResult.valid ? 'success' : 'error'}
                  sx={{ mb: 2 }}
                >
                  {notionValidationResult.message}
                </Alert>
              )}

              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Button
                  variant="outlined"
                  onClick={() => validateNotionKey()}
                  disabled={!notionApiKey.trim() || validatingNotion}
                  startIcon={validatingNotion ? <CircularProgress size={16} /> : <CheckCircle />}
                >
                  {validatingNotion ? 'Validating...' : 'Validate'}
                </Button>

                <Button
                  variant="contained"
                  onClick={saveNotionKey}
                  disabled={!notionApiKey.trim() || savingNotion}
                  startIcon={savingNotion ? <CircularProgress size={16} /> : <Save />}
                >
                  {savingNotion ? 'Saving...' : 'Save API Key'}
                </Button>

                {settings.settings.has_notion_key && (
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={() => setDeleteNotionDialog(true)}
                    startIcon={<Delete />}
                  >
                    Delete API Key
                  </Button>
                )}
              </Box>
            </Box>

            <Alert severity="info" sx={{ mt: 3 }}>
              <Typography variant="body2">
                <strong>How to get your Notion API key:</strong>
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                1. Go to <a href="https://www.notion.so/my-integrations" target="_blank" rel="noopener noreferrer">My Integrations</a><br />
                2. Click "+ New integration"<br />
                3. Give it a name and select your workspace<br />
                4. Copy the "Internal Integration Token"<br />
                5. Share the pages/databases you want to access with your integration
              </Typography>
            </Alert>
          </CardContent>
        </Card>

        {/* Google Workspace Integration */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">
                📊 Google Workspace Integration
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<Launch />}
                onClick={handleOpenGoogleHelp}
              >
                Setup OAuth
              </Button>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Current Status
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  icon={settings.settings.has_google_oauth ? <CheckCircle /> : <ErrorIcon />}
                  label={settings.settings.has_google_oauth ? 'OAuth Configured' : 'No OAuth Token'}
                  color={settings.settings.has_google_oauth ? 'success' : 'error'}
                  size="small"
                />
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="body2" color="text.secondary" gutterBottom>
              Connect your Google account to access Docs and Sheets
            </Typography>

            <Box sx={{ mt: 2 }}>
              {!settings.settings.has_google_oauth ? (
                <>
                  <Alert severity="info" sx={{ mb: 2 }}>
                    <strong>Note:</strong> This is separate from your login credentials.
                    To enable automatic access to your Google Docs and Sheets, you'll need to grant additional permissions.
                  </Alert>
                  <Button
                    variant="contained"
                    onClick={() => handleGoogleAuthorize()}
                    startIcon={<Launch />}
                    disabled={validating}
                  >
                    Authorize Google Workspace Access
                  </Button>
                </>
              ) : (
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={() => setDeleteGoogleDialog(true)}
                    startIcon={<Delete />}
                  >
                    Disconnect Google Account
                  </Button>
                </Box>
              )}
            </Box>

            <Alert severity="info" sx={{ mt: 3 }}>
              <Typography variant="body2">
                <strong>Google Workspace Integration:</strong>
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                This integration allows the app to read and write Google Docs and Sheets on your behalf.
                You will need to authorize access through Google OAuth.
              </Typography>
            </Alert>
          </CardContent>
        </Card>

        {/* Slack Integration */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">
                💬 Slack Integration
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<Launch />}
                onClick={handleOpenSlackHelp}
              >
                Setup OAuth
              </Button>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Current Status
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  icon={settings.user.has_slack_user_token ? <CheckCircle /> : <ErrorIcon />}
                  label={settings.user.has_slack_user_token ? 'Connected' : 'Not Connected'}
                  color={settings.user.has_slack_user_token ? 'success' : 'error'}
                  size="small"
                />
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="body2" color="text.secondary" gutterBottom>
              Connect your Slack account for better search results in /find-context
            </Typography>

            <Box sx={{ mt: 2 }}>
              {!settings.user.has_slack_user_token ? (
                <>
                  <Alert severity="info" sx={{ mb: 2 }}>
                    <strong>Enhanced Search:</strong> Connecting your Slack account enables the powerful search.messages API
                    for much better results in the /find-context command, instead of the limited bot-only search.
                  </Alert>
                  <Button
                    variant="contained"
                    onClick={() => handleSlackAuthorize()}
                    startIcon={<Launch />}
                  >
                    Connect Slack Account
                  </Button>
                </>
              ) : (
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={() => setDeleteSlackDialog(true)}
                    startIcon={<Delete />}
                  >
                    Disconnect Slack
                  </Button>
                </Box>
              )}
            </Box>

            <Alert severity="info" sx={{ mt: 3 }}>
              <Typography variant="body2">
                <strong>Slack Search Integration:</strong>
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                This integration allows the /find-context Slack command to search your messages using Slack's powerful search API.
                Without this connection, searches are limited to channels the bot has been added to.
              </Typography>
            </Alert>
          </CardContent>
        </Card>
      </TabPanel>

      {/* Tab 2: Project Settings */}
      <TabPanel value={tabValue} index={1}>
        {loadingProjects ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                🏢 All Projects
              </Typography>
              <Alert severity="info" sx={{ mb: 2 }}>
                Toggle the "Active" switch to sync projects to local database and enable additional fields.
              </Alert>

              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Project Name</TableCell>
                      <TableCell>Key</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {allProjects.map((project) => (
                      <TableRow
                        key={project.key}
                        sx={{
                          '&:hover': {
                            backgroundColor: 'rgba(85, 77, 255, 0.08)'
                          }
                        }}
                      >
                        <TableCell
                          sx={{
                            cursor: 'pointer',
                            '&:hover': {
                              textDecoration: 'underline',
                              color: 'primary.main'
                            }
                          }}
                          onClick={() => redirect('show', 'projects', project.key)}
                        >
                          {project.name}
                        </TableCell>
                        <TableCell>
                          <Chip label={project.key} size="small" />
                        </TableCell>
                        <TableCell>{project.projectTypeKey || 'Unknown'}</TableCell>
                        <TableCell>
                          <FormControlLabel
                            control={
                              <Switch
                                checked={project.is_active || false}
                                onChange={() => handleActiveToggle(project)}
                                color="primary"
                                size="small"
                              />
                            }
                            label={project.is_active ? 'Active' : 'Inactive'}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        )}
      </TabPanel>

      {/* Tab 3: Notifications */}
      <TabPanel value={tabValue} index={2}>
        {loadingNotifPrefs ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Notification Preferences
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Choose which notifications you'd like to receive
              </Typography>

              {!notificationPrefs.slack_connected && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                  <Typography variant="body2">
                    <strong>Slack Connection Required</strong>
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    Connect your Slack account in the "My Integrations" tab to receive DM notifications.
                  </Typography>
                </Alert>
              )}

              {/* Daily Digests Section */}
              <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
                📋 Daily Digests
              </Typography>

              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.notify_daily_todo_digest}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        notify_daily_todo_digest: e.target.checked
                      })}
                      disabled={!notificationPrefs.slack_connected}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1" fontWeight={500}>
                        Daily TODO Digest (9am EST)
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Receive a daily Slack DM with your assigned TODOs
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.notify_project_hours_forecast}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        notify_project_hours_forecast: e.target.checked
                      })}
                      disabled={!notificationPrefs.slack_connected}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1" fontWeight={500}>
                        Project Hours vs Forecast (4am EST)
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Receive a daily Slack DM with monthly hours tracking for all projects
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Divider sx={{ my: 3 }} />

              {/* Proactive Insights Section */}
              <Typography variant="h6" sx={{ mb: 2 }}>
                🔍 Proactive Insights
              </Typography>

              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Configure how you receive daily proactive insights (stale PRs, budget alerts, etc.) Default time: 9am EST
              </Typography>

              {/* Delivery Channels */}
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                Delivery Channels
              </Typography>

              <Box sx={{ mb: 2, ml: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.daily_brief_slack}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        daily_brief_slack: e.target.checked
                      })}
                      disabled={!notificationPrefs.slack_connected}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        Slack Direct Messages
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Receive insights via Slack DM
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Box sx={{ mb: 3, ml: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.daily_brief_email}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        daily_brief_email: e.target.checked
                      })}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        Email
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Receive insights via email
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              {/* Insight Types */}
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                Insight Types
              </Typography>

              <Box sx={{ mb: 1, ml: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.enable_stale_pr_alerts}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        enable_stale_pr_alerts: e.target.checked
                      })}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        Stale PR Alerts
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Alert when PRs are &gt;3 days old without reviews
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Box sx={{ mb: 1, ml: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.enable_budget_alerts}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        enable_budget_alerts: e.target.checked
                      })}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        Budget Alerts
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Alert when projects use &gt;75% budget with &gt;40% month remaining
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Box sx={{ mb: 1, ml: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.enable_missing_ticket_alerts}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        enable_missing_ticket_alerts: e.target.checked
                      })}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        Missing Ticket Alerts
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Alert when work is done without associated tickets
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Box sx={{ mb: 1, ml: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.enable_anomaly_alerts}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        enable_anomaly_alerts: e.target.checked
                      })}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        Anomaly Alerts
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Alert on unusual patterns in project activity
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Box sx={{ mb: 3, ml: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={notificationPrefs.enable_meeting_prep}
                      onChange={(e) => setNotificationPrefs({
                        ...notificationPrefs,
                        enable_meeting_prep: e.target.checked
                      })}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        Meeting Preparation
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Reminders and prep materials for upcoming meetings
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Button
                variant="contained"
                onClick={saveNotificationPreferences}
                disabled={savingNotifPrefs || !notificationPrefs.slack_connected}
                startIcon={savingNotifPrefs ? <CircularProgress size={16} /> : <Save />}
              >
                {savingNotifPrefs ? 'Saving...' : 'Save Preferences'}
              </Button>
            </CardContent>
          </Card>
        )}
      </TabPanel>

      {/* Tab 4: Auto-Escalation */}
      <TabPanel value={tabValue} index={3}>
        {loadingEscalation ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : escalationPrefs ? (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Auto-Escalation Settings
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Configure automatic escalation of stale proactive insights
              </Typography>

              <Alert severity="info" sx={{ mb: 3 }}>
                Auto-escalation automatically notifies you about PR insights that haven't been addressed within specified timeframes.
                Escalations are tiered: DM → Slack Channel → GitHub Comment.
              </Alert>

              <Box sx={{ mb: 3 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={escalationPrefs.enable_auto_escalation}
                      onChange={(e) => setEscalationPrefs({
                        ...escalationPrefs,
                        enable_auto_escalation: e.target.checked
                      })}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1" fontWeight={500}>
                        Enable Auto-Escalation
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Automatically escalate stale insights through multiple notification tiers
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle1" fontWeight={500} sx={{ mb: 2 }}>
                Escalation Types
              </Typography>

              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={escalationPrefs.enable_dm_escalation}
                      onChange={(e) => setEscalationPrefs({
                        ...escalationPrefs,
                        enable_dm_escalation: e.target.checked
                      })}
                      disabled={!escalationPrefs.enable_auto_escalation}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1" fontWeight={500}>
                        Slack DM Notifications
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Receive direct messages for insights requiring attention
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={escalationPrefs.enable_channel_escalation}
                      onChange={(e) => setEscalationPrefs({
                        ...escalationPrefs,
                        enable_channel_escalation: e.target.checked
                      })}
                      disabled={!escalationPrefs.enable_auto_escalation}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1" fontWeight={500}>
                        Slack Channel Posts
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Post to internal project channels for visibility (only internal-safe channels)
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Box sx={{ mb: 3 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={escalationPrefs.enable_github_escalation}
                      onChange={(e) => setEscalationPrefs({
                        ...escalationPrefs,
                        enable_github_escalation: e.target.checked
                      })}
                      disabled={!escalationPrefs.enable_auto_escalation}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1" fontWeight={500}>
                        GitHub PR Comments
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Post comments directly on the pull request for critical insights
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle1" fontWeight={500} sx={{ mb: 2 }}>
                Escalation Thresholds
              </Typography>

              <TextField
                fullWidth
                type="number"
                label="DM After (days)"
                value={escalationPrefs.dm_threshold_days}
                onChange={(e) => {
                  const value = parseInt(e.target.value);
                  setEscalationPrefs({
                    ...escalationPrefs,
                    dm_threshold_days: !isNaN(value) && value >= 1 ? value : escalationPrefs.dm_threshold_days
                  });
                }}
                disabled={!escalationPrefs.enable_auto_escalation || !escalationPrefs.enable_dm_escalation}
                helperText="Send Slack DM after this many days"
                InputProps={{ inputProps: { min: 1 } }}
                sx={{ mb: 2 }}
              />

              <TextField
                fullWidth
                type="number"
                label="Channel Post After (days)"
                value={escalationPrefs.channel_threshold_days}
                onChange={(e) => {
                  const value = parseInt(e.target.value);
                  setEscalationPrefs({
                    ...escalationPrefs,
                    channel_threshold_days: !isNaN(value) && value >= 1 ? value : escalationPrefs.channel_threshold_days
                  });
                }}
                disabled={!escalationPrefs.enable_auto_escalation || !escalationPrefs.enable_channel_escalation}
                helperText="Post to Slack channel after this many days (includes DM)"
                InputProps={{ inputProps: { min: 1 } }}
                sx={{ mb: 2 }}
              />

              <TextField
                fullWidth
                type="number"
                label="GitHub Comment After (days)"
                value={escalationPrefs.critical_threshold_days}
                onChange={(e) => {
                  const value = parseInt(e.target.value);
                  setEscalationPrefs({
                    ...escalationPrefs,
                    critical_threshold_days: !isNaN(value) && value >= 1 ? value : escalationPrefs.critical_threshold_days
                  });
                }}
                disabled={!escalationPrefs.enable_auto_escalation || !escalationPrefs.enable_github_escalation}
                helperText="Post GitHub comment after this many days (includes DM + Channel)"
                InputProps={{ inputProps: { min: 1 } }}
                sx={{ mb: 3 }}
              />

              <Button
                variant="contained"
                onClick={saveEscalationPreferences}
                disabled={savingEscalation}
                startIcon={savingEscalation ? <CircularProgress size={16} /> : <Save />}
              >
                {savingEscalation ? 'Saving...' : 'Save Preferences'}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Alert severity="info">No escalation preferences configured yet.</Alert>
        )}
      </TabPanel>

      {/* Tab 5: AI Configuration (Admin Only) */}
      {settings.user.role === 'admin' && (
        <TabPanel value={tabValue} index={4}>
          {loadingAI ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress />
            </Box>
          ) : aiSettings ? (
            <>
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    🤖 AI Provider Configuration
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Configure which AI model the system uses for meeting analysis and other AI-powered features.
                  </Typography>

                  <Alert severity="warning" sx={{ my: 2 }}>
                    <strong>Admin Only:</strong> These settings affect all users. Changes will apply to all future AI operations.
                  </Alert>

                  <Box sx={{ mt: 3 }}>
                    <FormControl fullWidth sx={{ mb: 3 }}>
                      <InputLabel>AI Provider</InputLabel>
                      <Select
                        value={aiSettings.ai_provider}
                        label="AI Provider"
                        onChange={(e) => {
                          setAISettings({ ...aiSettings, ai_provider: e.target.value, ai_model: null });
                          setShowCustomModelInput(false);
                          setCustomModel('');
                        }}
                      >
                        <MenuItem value="openai">OpenAI (GPT)</MenuItem>
                        <MenuItem value="anthropic">Anthropic (Claude)</MenuItem>
                        <MenuItem value="google">Google (Gemini)</MenuItem>
                      </Select>
                      <FormHelperText>Select the AI provider to use for analysis</FormHelperText>
                    </FormControl>

                    <FormControl fullWidth sx={{ mb: 3 }}>
                      <InputLabel>Model</InputLabel>
                      <Select
                        value={showCustomModelInput ? '__custom__' : (aiSettings.ai_model || '')}
                        label="Model"
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === '__custom__') {
                            setShowCustomModelInput(true);
                            setCustomModel(aiSettings.ai_model || '');
                          } else {
                            setShowCustomModelInput(false);
                            setAISettings({ ...aiSettings, ai_model: value });
                          }
                        }}
                      >
                        {availableModels && availableModels[aiSettings.ai_provider as keyof AvailableModels]?.map((model) => (
                          <MenuItem key={model.value} value={model.value}>
                            {model.label}
                          </MenuItem>
                        ))}
                      </Select>
                      <FormHelperText>Select the specific model version</FormHelperText>
                    </FormControl>

                    {showCustomModelInput && (
                      <TextField
                        fullWidth
                        label="Custom Model ID"
                        value={customModel}
                        onChange={(e) => {
                          setCustomModel(e.target.value);
                          setAISettings({ ...aiSettings, ai_model: e.target.value });
                        }}
                        placeholder={`e.g., ${aiSettings.ai_provider === 'anthropic' ? 'claude-3-5-sonnet-20241022' : 'gemini-1.5-pro-002'}`}
                        helperText="Enter the exact model ID from the provider's documentation"
                        sx={{ mb: 3 }}
                      />
                    )}

                    <Box sx={{ mb: 3 }}>
                      <Typography gutterBottom>
                        Temperature: {aiSettings.ai_temperature}
                      </Typography>
                      <Slider
                        value={aiSettings.ai_temperature}
                        onChange={(e, value) => setAISettings({ ...aiSettings, ai_temperature: value as number })}
                        min={0}
                        max={2}
                        step={0.1}
                        marks={[
                          { value: 0, label: '0 (Focused)' },
                          { value: 1, label: '1' },
                          { value: 2, label: '2 (Creative)' },
                        ]}
                        valueLabelDisplay="auto"
                      />
                      <FormHelperText>Controls randomness: 0 = focused and deterministic, 2 = creative and random</FormHelperText>
                    </Box>

                    <TextField
                      fullWidth
                      label="Max Tokens"
                      type="number"
                      value={aiSettings.ai_max_tokens}
                      onChange={(e) => setAISettings({ ...aiSettings, ai_max_tokens: parseInt(e.target.value) })}
                      helperText="Maximum number of tokens in the response"
                      sx={{ mb: 3 }}
                    />

                    <Button
                      variant="contained"
                      onClick={saveAISettings}
                      disabled={savingAI}
                      startIcon={savingAI ? <CircularProgress size={16} /> : <Save />}
                    >
                      {savingAI ? 'Saving...' : 'Save AI Configuration'}
                    </Button>
                  </Box>
                </CardContent>
              </Card>

              {/* API Keys Management */}
              {['openai', 'anthropic', 'google'].map((provider) => (
                <Card key={provider} sx={{ mb: 3 }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                      <Typography variant="h6">
                        {provider === 'openai' && '🔵 OpenAI API Key'}
                        {provider === 'anthropic' && '🟣 Anthropic (Claude) API Key'}
                        {provider === 'google' && '🔴 Google (Gemini) API Key'}
                      </Typography>
                      <Chip
                        icon={aiSettings[`has_${provider}_key` as keyof AISettings] ? <CheckCircle /> : <ErrorIcon />}
                        label={aiSettings[`has_${provider}_key` as keyof AISettings] ? 'Configured' : 'Not Configured'}
                        color={aiSettings[`has_${provider}_key` as keyof AISettings] ? 'success' : 'error'}
                        size="small"
                      />
                    </Box>

                    <TextField
                      fullWidth
                      label={`${provider.charAt(0).toUpperCase() + provider.slice(1)} API Key`}
                      type={showAIKeys[provider as keyof typeof showAIKeys] ? 'text' : 'password'}
                      value={aiApiKeys[provider as keyof typeof aiApiKeys]}
                      onChange={(e) => setAIApiKeys({ ...aiApiKeys, [provider]: e.target.value })}
                      placeholder={`Enter your ${provider} API key`}
                      helperText="Your API key will be encrypted and stored securely"
                      InputProps={{
                        endAdornment: (
                          <InputAdornment position="end">
                            <IconButton
                              onClick={() => setShowAIKeys({ ...showAIKeys, [provider]: !showAIKeys[provider as keyof typeof showAIKeys] })}
                              edge="end"
                            >
                              {showAIKeys[provider as keyof typeof showAIKeys] ? <VisibilityOff /> : <Visibility />}
                            </IconButton>
                          </InputAdornment>
                        ),
                      }}
                      sx={{ mb: 2 }}
                    />

                    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                      <Button
                        variant="contained"
                        onClick={() => saveAIAPIKey(provider)}
                        disabled={!aiApiKeys[provider as keyof typeof aiApiKeys].trim() || savingAI}
                        startIcon={savingAI ? <CircularProgress size={16} /> : <Save />}
                      >
                        Save API Key
                      </Button>

                      {aiSettings[`has_${provider}_key` as keyof AISettings] && (
                        <Button
                          variant="outlined"
                          color="error"
                          onClick={() => setDeleteAIKeyDialog(provider)}
                          startIcon={<Delete />}
                        >
                          Delete API Key
                        </Button>
                      )}
                    </Box>
                  </CardContent>
                </Card>
              ))}

              {/* Epic Reconciliation Settings */}
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    📊 Epic Reconciliation Settings
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Configure how the Monthly Epic Reconciliation job handles unassigned tickets.
                  </Typography>

                  <Alert severity="info" sx={{ my: 2 }}>
                    <Typography variant="body2" paragraph>
                      <strong>Monthly Epic Reconciliation</strong> runs on the 3rd of every month to ensure all tickets are properly associated with epics before generating reports.
                    </Typography>
                    <Typography variant="body2">
                      <strong>Summary Mode (OFF):</strong> AI will analyze tickets and show suggestions without making changes to Jira.
                      <br />
                      <strong>Auto-Update Mode (ON):</strong> AI will automatically update Jira tickets with suggested epic associations.
                    </Typography>
                  </Alert>

                  <Box sx={{ mt: 3 }}>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={aiSettings.epic_auto_update_enabled}
                          onChange={(e) => setAISettings({ ...aiSettings, epic_auto_update_enabled: e.target.checked })}
                          color="primary"
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body1">
                            {aiSettings.epic_auto_update_enabled ? '✅ Auto-Update Mode (ON)' : '📋 Summary Mode (OFF)'}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {aiSettings.epic_auto_update_enabled
                              ? 'AI will automatically update tickets in Jira with suggested epics'
                              : 'AI will only show suggestions without making changes to Jira'}
                          </Typography>
                        </Box>
                      }
                    />
                  </Box>

                  <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
                    <Button
                      variant="contained"
                      onClick={saveEpicSettings}
                      disabled={savingAI}
                      startIcon={savingAI ? <CircularProgress size={16} /> : <Save />}
                    >
                      {savingAI ? 'Saving...' : 'Save Epic Settings'}
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            </>
          ) : (
            <Alert severity="info">No AI settings configured yet.</Alert>
          )}
        </TabPanel>
      )}

      {/* Tab 6: User Management (Admin Only) */}
      {settings.user.role === 'admin' && (
        <TabPanel value={tabValue} index={5}>
          <UserManagement />
        </TabPanel>
      )}

      {/* Delete Confirmation Dialogs */}
      <Dialog open={deleteDialog} onClose={() => setDeleteDialog(false)}>
        <DialogTitle>Delete Fireflies API Key</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete your Fireflies API key?
            You will no longer be able to access your meeting transcripts until you add a new key.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialog(false)}>Cancel</Button>
          <Button
            onClick={deleteApiKey}
            color="error"
            disabled={deleting}
            startIcon={deleting ? <CircularProgress size={16} /> : <Delete />}
          >
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteNotionDialog} onClose={() => setDeleteNotionDialog(false)}>
        <DialogTitle>Delete Notion API Key</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete your Notion API key?
            You will no longer be able to access your Notion pages and databases until you add a new key.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteNotionDialog(false)}>Cancel</Button>
          <Button
            onClick={deleteNotionKey}
            color="error"
            disabled={deletingNotion}
            startIcon={deletingNotion ? <CircularProgress size={16} /> : <Delete />}
          >
            {deletingNotion ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteGoogleDialog} onClose={() => setDeleteGoogleDialog(false)}>
        <DialogTitle>Disconnect Google Account</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to disconnect your Google account?
            You will no longer be able to access Google Docs and Sheets until you reconnect.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteGoogleDialog(false)}>Cancel</Button>
          <Button
            onClick={deleteGoogleOAuth}
            color="error"
            disabled={deletingGoogle}
            startIcon={deletingGoogle ? <CircularProgress size={16} /> : <Delete />}
          >
            {deletingGoogle ? 'Disconnecting...' : 'Disconnect'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleteSlackDialog} onClose={() => setDeleteSlackDialog(false)}>
        <DialogTitle>Disconnect Slack</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to disconnect your Slack account?
            The /find-context command will use limited bot-only search until you reconnect.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteSlackDialog(false)}>Cancel</Button>
          <Button
            onClick={deleteSlackToken}
            color="error"
            disabled={deletingSlack}
            startIcon={deletingSlack ? <CircularProgress size={16} /> : <Delete />}
          >
            {deletingSlack ? 'Disconnecting...' : 'Disconnect'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete AI API Key Dialog */}
      <Dialog open={deleteAIKeyDialog !== null} onClose={() => setDeleteAIKeyDialog(null)}>
        <DialogTitle>Delete {deleteAIKeyDialog?.toUpperCase()} API Key</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this API key? This will affect all users if this provider is currently selected.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteAIKeyDialog(null)}>Cancel</Button>
          <Button
            onClick={() => deleteAIKeyDialog && deleteAIAPIKey(deleteAIKeyDialog)}
            color="error"
            disabled={deletingAIKey}
            startIcon={deletingAIKey ? <CircularProgress size={16} /> : <Delete />}
          >
            {deletingAIKey ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Settings;
