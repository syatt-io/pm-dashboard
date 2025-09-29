import React, { useState } from 'react';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import { Card, Box, Alert, Typography, Checkbox, FormControlLabel } from '@mui/material';
import { useAuth } from '../context/AuthContext';

const GOOGLE_CLIENT_ID = '557251748262-oi3pqm1o265eblprbau8n2kq7kkrmgai.apps.googleusercontent.com';

const Login: React.FC = () => {
  const [error, setError] = useState<string | null>(null);
  const [rememberMe, setRememberMe] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSuccess = async (credentialResponse: any) => {
    try {
      setError(null);
      await login(credentialResponse.credential, rememberMe);
      navigate('/');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleError = () => {
    setError('Google login failed. Please try again.');
  };


  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          backgroundColor: '#f5f5f5'
        }}
      >
        <Card
          sx={{
            padding: 4,
            minWidth: 400,
            textAlign: 'center',
            borderRadius: 2,
            boxShadow: 3
          }}
        >
          <Typography variant="h4" component="h1" gutterBottom sx={{ color: '#554DFF', fontWeight: 700 }}>
            PM Agent
          </Typography>

          <Typography variant="subtitle1" color="text.secondary" gutterBottom sx={{ mb: 4 }}>
            Sign in with your Syatt account
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box sx={{ mb: 2 }}>
            <GoogleLogin
              onSuccess={handleSuccess}
              onError={handleError}
              useOneTap={false}
              hosted_domain="syatt.io"
              text="signin_with"
              shape="rectangular"
              size="large"
              theme="outline"
              width="350"
            />
          </Box>

          <FormControlLabel
            control={
              <Checkbox
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                color="primary"
              />
            }
            label="Remember me for 7 days"
          />

          <Typography variant="caption" display="block" sx={{ mt: 3, color: 'text.secondary' }}>
            Only @syatt.io email addresses are allowed
          </Typography>
        </Card>
      </Box>
    </GoogleOAuthProvider>
  );
};

export default Login;