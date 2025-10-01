import React, { useState, useEffect } from 'react';
import {
  Alert,
  AlertTitle,
  Button,
  Box,
  Snackbar,
  Slide,
  Typography,
} from '@mui/material';
import { Settings, Close } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

interface UserSettings {
  has_fireflies_key: boolean;
  fireflies_key_valid: boolean;
}

interface OnboardingAlertProps {
  onDismiss?: () => void;
}

const OnboardingAlert: React.FC<OnboardingAlertProps> = ({ onDismiss }) => {
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(true);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    checkUserSettings();
  }, []);

  const checkUserSettings = async () => {
    try {
      const API_BASE_URL = process.env.REACT_APP_API_URL || '' + (window.location.hostname === 'localhost' ? 'http://localhost:4000' : 'https://agent-pm-tsbbb.ondigitalocean.app') + '';
      const response = await fetch(`${API_BASE_URL}/api/user/settings`, {
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success && data.data) {
          setUserSettings(data.data.settings);

          // Show onboarding if user doesn't have a valid Fireflies key
          const needsOnboarding = !data.data.settings.has_fireflies_key || !data.data.settings.fireflies_key_valid;
          setShow(needsOnboarding);
        }
      }
    } catch (error) {
      // Error checking settings - will be handled by UI
    } finally {
      setLoading(false);
    }
  };

  const handleGoToSettings = () => {
    navigate('/settings');
    handleDismiss();
  };

  const handleDismiss = () => {
    setShow(false);
    if (onDismiss) {
      onDismiss();
    }
  };

  if (loading || !show || !userSettings) {
    return null;
  }

  const isInvalid = userSettings.has_fireflies_key && !userSettings.fireflies_key_valid;

  return (
    <Snackbar
      open={show}
      anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      TransitionComponent={Slide}
      TransitionProps={{ direction: 'down' } as any}
    >
      <Alert
        severity={isInvalid ? 'warning' : 'info'}
        action={
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              color="inherit"
              size="small"
              onClick={handleGoToSettings}
              startIcon={<Settings />}
            >
              Setup
            </Button>
            <Button
              color="inherit"
              size="small"
              onClick={handleDismiss}
            >
              <Close />
            </Button>
          </Box>
        }
        sx={{ minWidth: 400 }}
      >
        <AlertTitle>
          {isInvalid ? '🔧 Fireflies Setup Required' : '👋 Welcome to PM Command Center!'}
        </AlertTitle>
        <Typography variant="body2">
          {isInvalid
            ? 'Your Fireflies API key is invalid. Please update it in Settings to access your meetings.'
            : 'To get started, configure your Fireflies API key in Settings to access your meeting transcripts.'
          }
        </Typography>
      </Alert>
    </Snackbar>
  );
};

export default OnboardingAlert;