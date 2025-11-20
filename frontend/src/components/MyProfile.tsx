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
  FormControlLabel,
  Switch,
} from '@mui/material';
import { PillTabs, Tab } from './common/PillTabs';
import {
  Save,
  Delete,
  Visibility,
  VisibilityOff,
  CheckCircle,
  Error as ErrorIcon,
  Warning,
  Launch,
} from '@mui/icons-material';
import { Loading, Title } from 'react-admin';
import { getApiUrl } from '../config';
import { useTabWithUrl } from '../hooks/useTabWithUrl';
import { NotificationPreferences } from './NotificationPreferences';

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
      id={`profile-tabpanel-${index}`}
      aria-labelledby={`profile-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
}

export const MyProfile = () => {
  const [tabValue, setTabValue] = useTabWithUrl('profile-tab', 0);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);

  // Fireflies state
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

  // Notification preferences loading state (preferences managed by NotificationPreferences component)
  const [loadingNotifPrefs, setLoadingNotifPrefs] = useState(false);

  // Load user settings on component mount
  useEffect(() => {
    loadSettings();
    // NotificationPreferences component handles its own data loading
    setLoadingNotifPrefs(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle OAuth callback messages from URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const success = urlParams.get('success');
    const error = urlParams.get('error');

    if (success === 'google_workspace_connected') {
      showSnackbar('Google Workspace connected successfully!', 'success');
      loadSettings();
      window.history.replaceState({}, '', '/profile');
    } else if (success === 'slack_connected') {
      showSnackbar('Slack connected successfully!', 'success');
      loadSettings();
      window.history.replaceState({}, '', '/profile');
    } else if (error) {
      const errorMessages: { [key: string]: string } = {
        'oauth_denied': 'Authorization was denied',
        'oauth_failed': 'Failed to complete authorization',
      };
      showSnackbar(errorMessages[error] || 'An error occurred', 'error');
      window.history.replaceState({}, '', '/profile');
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
        <Alert severity="error">Failed to load profile</Alert>
      </Box>
    );
  }

  return (
    <Box p={2}>
      <Title title="My Profile" />

      {/* Tabs */}
      <Box sx={{ mb: 3 }}>
        <PillTabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="profile tabs"
        >
          <Tab label="Profile" />
          <Tab label="My Integrations" />
        </PillTabs>
      </Box>

      {/* Tab 1: Profile (User Info + 3 Notification Preferences) */}
      <TabPanel value={tabValue} index={0}>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              👤 User Information
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Your profile information is managed by your Google account.
            </Typography>
            <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 2 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">Name</Typography>
                <Typography variant="body1" fontWeight={500}>{settings.user.name}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">Email</Typography>
                <Typography variant="body1" fontWeight={500}>{settings.user.email}</Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              🔔 Notification Preferences
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose which notifications you'd like to receive.
            </Typography>

            {loadingNotifPrefs ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
              </Box>
            ) : (
              // All users see full NotificationPreferences component with channel selection
              <NotificationPreferences userRole={settings.user.role.toUpperCase() as 'ADMIN' | 'PM' | 'MEMBER' | 'NO_ACCESS'} />
            )}
          </CardContent>
        </Card>
      </TabPanel>

      {/* Tab 2: My Integrations */}
      <TabPanel value={tabValue} index={1}>
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

export default MyProfile;
