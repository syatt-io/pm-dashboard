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
} from '@mui/icons-material';
import { Loading, Title } from 'react-admin';
import { getApiUrl } from '../config';

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
  updated_at: string | null;
  updated_by_user_id: number | null;
}

interface AvailableModels {
  openai: Array<{ value: string; label: string }>;
  anthropic: Array<{ value: string; label: string }>;
  google: Array<{ value: string; label: string }>;
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
  const [tabValue, setTabValue] = useState(0);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
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
  const [googleOAuthToken, setGoogleOAuthToken] = useState('');
  const [deletingGoogle, setDeletingGoogle] = useState(false);
  const [deleteGoogleDialog, setDeleteGoogleDialog] = useState(false);

  // Slack OAuth state
  const [deletingSlack, setDeletingSlack] = useState(false);
  const [deleteSlackDialog, setDeleteSlackDialog] = useState(false);

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
          {settings.user.role === 'admin' && (
            <Tab icon={<SmartToy />} label="AI Configuration" iconPosition="start" />
          )}
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

      {/* Tab 2: AI Configuration (Admin Only) */}
      {settings.user.role === 'admin' && (
        <TabPanel value={tabValue} index={1}>
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
            </>
          ) : (
            <Alert severity="info">No AI settings configured yet.</Alert>
          )}
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
