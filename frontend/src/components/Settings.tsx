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
} from '@mui/icons-material';
import { useDataProvider, useNotify, Loading, Title } from 'react-admin';
import { getApiUrl } from '../config';

interface UserSettings {
  user: {
    id: number;
    email: string;
    name: string;
    role: string;
    has_fireflies_key: boolean;
  };
  settings: {
    has_fireflies_key: boolean;
    fireflies_key_valid: boolean;
  };
}

interface ApiResponse {
  success: boolean;
  data?: UserSettings;
  error?: string;
  message?: string;
}

export const Settings = () => {
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

  const dataProvider = useDataProvider();
  const notify = useNotify();

  // Load user settings on component mount
  useEffect(() => {
    loadSettings();
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

    // Validate first
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
        setApiKey(''); // Clear the input field
        setValidationResult(null);
        await loadSettings(); // Reload settings to update status
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
        await loadSettings(); // Reload settings to update status
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

      {/* Fireflies Integration */}
      <Card>
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

          {/* Current Status */}
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

          {/* API Key Management */}
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
                setValidationResult(null); // Clear previous validation
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

            {/* Validation Result */}
            {validationResult && (
              <Alert
                severity={validationResult.valid ? 'success' : 'error'}
                sx={{ mb: 2 }}
              >
                {validationResult.message}
              </Alert>
            )}

            {/* Action Buttons */}
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

          {/* Help Text */}
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

      {/* Delete Confirmation Dialog */}
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