# Google SSO Implementation Guide

This guide provides a comprehensive walkthrough for implementing Google Single Sign-On (SSO) in a React + Flask application, based on the implementation in the PM Agent project.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Backend Implementation (Flask)](#backend-implementation-flask)
4. [Frontend Implementation (React)](#frontend-implementation-react)
5. [Database Setup](#database-setup)
6. [Environment Configuration](#environment-configuration)
7. [Security Considerations](#security-considerations)
8. [Testing](#testing)
9. [Common Issues & Troubleshooting](#common-issues--troubleshooting)

## Overview

This implementation provides:
- Google OAuth 2.0 authentication
- JWT token-based session management
- Role-based access control (Admin, Member, No Access)
- Domain restriction (e.g., only @syatt.io emails)
- Automatic token refresh
- Remember me functionality
- Protected routes and role-based authorization

### Architecture Components

**Backend (Flask)**:
- Authentication service (`src/services/auth.py`)
- Authentication routes (`src/routes/auth.py`)
- User model with roles (`src/models/user.py`)

**Frontend (React)**:
- Auth context provider (`frontend/src/context/AuthContext.tsx`)
- Login component (`frontend/src/components/Login.tsx`)
- Protected route wrapper (`frontend/src/components/ProtectedRoute.tsx`)

## Prerequisites

### Google Cloud Console Setup

1. **Create a Google Cloud Project**
   ```bash
   # Go to https://console.cloud.google.com/
   # Create a new project or select existing one
   ```

2. **Enable Google+ API**
   ```bash
   # In Google Cloud Console:
   # APIs & Services > Library > Google+ API > Enable
   ```

3. **Create OAuth 2.0 Credentials**
   ```bash
   # APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client IDs
   # Application type: Web application
   # Authorized JavaScript origins: http://localhost:3000, http://localhost:4001
   # Authorized redirect URIs: http://localhost:3000, http://localhost:4001
   ```

4. **Get Client ID**
   ```bash
   # Copy the Client ID from the credentials page
   # Format: 557251748262-xxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com
   ```

## Backend Implementation (Flask)

### 1. Dependencies

Add to `requirements.txt`:
```txt
# Authentication
google-auth>=2.40.3
google-auth-oauthlib>=1.2.2
google-auth-httplib2>=0.2.0
PyJWT>=2.10.1

# Web framework
flask>=3.0.0
flask-cors>=4.0.0

# Database
sqlalchemy>=2.0.0
```

### 2. User Model (`src/models/user.py`)

```python
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    """User role enumeration."""
    NO_ACCESS = "no_access"
    MEMBER = "member"
    ADMIN = "admin"

class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    google_id = Column(String(255), unique=True, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.NO_ACCESS, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role': self.role.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }

    def can_access(self):
        """Check if user can access the system."""
        return self.role != UserRole.NO_ACCESS and self.is_active

    def is_admin(self):
        """Check if user is admin."""
        return self.role == UserRole.ADMIN
```

### 3. Authentication Service (`src/services/auth.py`)

```python
import os
import jwt
from datetime import datetime, timedelta
from google.oauth2 import id_token
from google.auth.transport import requests
from functools import wraps
from flask import request, jsonify, current_app
from sqlalchemy.orm import Session
from src.models.user import User, UserRole
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """Service for handling authentication and authorization."""

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY', 'change-in-production')
        self.jwt_expiry_hours = int(os.getenv('JWT_EXPIRY_HOURS', '24'))
        self.allowed_domain = '@yourdomain.com'  # Change this
        self.admin_email = 'admin@yourdomain.com'  # Change this

    def verify_google_token(self, token):
        """Verify Google OAuth token and return user info."""
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                self.google_client_id
            )

            # Check if email is from allowed domain
            email = idinfo.get('email', '')
            if not email.endswith(self.allowed_domain):
                raise ValueError(f"Email domain not allowed. Only {self.allowed_domain} emails are permitted.")

            return {
                'google_id': idinfo['sub'],
                'email': email,
                'name': idinfo.get('name', ''),
                'picture': idinfo.get('picture', '')
            }
        except Exception as e:
            logger.error(f"Google token verification failed: {e}")
            raise ValueError(f"Invalid Google token: {str(e)}")

    def create_or_update_user(self, user_info):
        """Create or update user from Google info."""
        # Try to find by google_id first
        user = self.db_session.query(User).filter_by(google_id=user_info['google_id']).first()

        # If not found by google_id, try by email
        if not user:
            user = self.db_session.query(User).filter_by(email=user_info['email']).first()
            if user:
                # Update existing user with real Google ID
                user.google_id = user_info['google_id']
                user.name = user_info['name']

        if not user:
            # Create new user
            role = UserRole.ADMIN if user_info['email'] == self.admin_email else UserRole.NO_ACCESS
            user = User(
                email=user_info['email'],
                name=user_info['name'],
                google_id=user_info['google_id'],
                role=role
            )
            self.db_session.add(user)

        # Update last login
        user.last_login = datetime.utcnow()
        self.db_session.commit()
        return user

    def generate_jwt_token(self, user, remember_me=False):
        """Generate JWT token for authenticated user."""
        expiry_hours = self.jwt_expiry_hours * 7 if remember_me else self.jwt_expiry_hours
        payload = {
            'user_id': user.id,
            'email': user.email,
            'role': user.role.value,
            'exp': datetime.utcnow() + timedelta(hours=expiry_hours),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')

    def verify_jwt_token(self, token):
        """Verify JWT token and return user info."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")

    def get_current_user(self, token):
        """Get current user from JWT token."""
        payload = self.verify_jwt_token(token)
        user = self.db_session.query(User).filter_by(id=payload['user_id']).first()

        if not user:
            raise ValueError("User not found")
        if not user.can_access():
            raise ValueError("User access denied")

        return user

# Decorators for route protection
def auth_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None

        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid authorization header format'}), 401

        # Get token from cookie as fallback
        if not token:
            token = request.cookies.get('auth_token')

        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        try:
            auth_service = current_app.auth_service
            user = auth_service.get_current_user(token)
            request.current_user = user
            return f(user, *args, **kwargs)
        except Exception as e:
            return jsonify({'error': str(e)}), 401

    return decorated_function

def admin_required(f):
    """Decorator to require admin role for routes."""
    @wraps(f)
    @auth_required
    def decorated_function(*args, **kwargs):
        user = request.current_user
        if not user.is_admin():
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function
```

### 4. Authentication Routes (`src/routes/auth.py`)

```python
from flask import Blueprint, request, jsonify, make_response
from src.services.auth import AuthService, auth_required, admin_required
from sqlalchemy.orm import Session

def create_auth_blueprint(db_session: Session):
    """Create authentication blueprint with database session."""
    auth_bp = Blueprint('auth', __name__)
    auth_service = AuthService(db_session)

    @auth_bp.route('/api/auth/google', methods=['POST'])
    def google_login():
        """Handle Google OAuth login."""
        try:
            data = request.get_json()
            token = data.get('credential')
            remember_me = data.get('rememberMe', False)

            if not token:
                return jsonify({'error': 'No Google token provided'}), 400

            # Verify Google token
            user_info = auth_service.verify_google_token(token)

            # Create or update user
            user = auth_service.create_or_update_user(user_info)

            # Check if user has access
            if not user.can_access():
                return jsonify({
                    'error': 'Access denied. Please contact an administrator for access.',
                    'status': 'no_access'
                }), 403

            # Generate JWT token
            jwt_token = auth_service.generate_jwt_token(user, remember_me)

            # Create response with secure cookie
            response_data = {
                'message': 'Login successful',
                'token': jwt_token,
                'user': user.to_dict()
            }
            response = make_response(jsonify(response_data))

            # Set secure cookie
            cookie_max_age = 604800 if remember_me else 86400  # 7 days or 1 day
            response.set_cookie(
                'auth_token',
                jwt_token,
                httponly=True,
                secure=True,  # Set to False for local development
                samesite='Strict',
                max_age=cookie_max_age
            )
            return response

        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': 'Login failed'}), 500

    @auth_bp.route('/api/auth/user', methods=['GET'])
    @auth_required
    def get_current_user(user):
        """Get current user information."""
        return jsonify({'user': user.to_dict()})

    @auth_bp.route('/api/auth/logout', methods=['POST'])
    def logout():
        """Handle logout."""
        response = make_response(jsonify({'message': 'Logged out successfully'}))
        response.set_cookie('auth_token', '', expires=0, httponly=True, secure=True, samesite='Strict')
        return response

    @auth_bp.route('/api/auth/refresh', methods=['POST'])
    def refresh_token():
        """Refresh JWT token."""
        try:
            # Get token from header or cookie
            token = None
            auth_header = request.headers.get('Authorization')
            if auth_header:
                token = auth_header.split(' ')[1]
            if not token:
                token = request.cookies.get('auth_token')

            if not token:
                return jsonify({'error': 'No token provided'}), 401

            # Handle expired tokens by decoding without verification
            try:
                user = auth_service.get_current_user(token)
            except ValueError:
                import jwt as jwt_lib
                payload = jwt_lib.decode(token, auth_service.jwt_secret, algorithms=['HS256'], options={"verify_exp": False})
                user = db_session.query(User).filter_by(id=payload['user_id']).first()
                if not user or not user.can_access():
                    raise ValueError("User not found or access denied")

            remember_me = request.get_json().get('rememberMe', False) if request.get_json() else False
            jwt_token = auth_service.generate_jwt_token(user, remember_me)

            response = make_response(jsonify({
                'message': 'Token refreshed',
                'token': jwt_token
            }))

            # Update cookie
            cookie_max_age = 604800 if remember_me else 86400
            response.set_cookie(
                'auth_token',
                jwt_token,
                httponly=True,
                secure=True,
                samesite='Strict',
                max_age=cookie_max_age
            )
            return response

        except Exception as e:
            return jsonify({'error': 'Token refresh failed'}), 500

    return auth_bp
```

### 5. Flask App Integration

```python
from flask import Flask
from flask_cors import CORS
from src.routes.auth import create_auth_blueprint
from src.services.auth import AuthService

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Database setup (adjust as needed)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///app.db')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize auth service
db_session = SessionLocal()
app.auth_service = AuthService(db_session)

# Register auth blueprint
auth_bp = create_auth_blueprint(db_session)
app.register_blueprint(auth_bp)
```

## Frontend Implementation (React)

### 1. Dependencies

Add to `package.json`:
```json
{
  "dependencies": {
    "@react-oauth/google": "^0.12.2",
    "@mui/material": "^5.18.0",
    "@mui/icons-material": "^5.18.0",
    "axios": "^1.12.2",
    "react": "^19.1.1",
    "react-dom": "^19.1.1",
    "react-router-dom": "^6.0.0"
  }
}
```

### 2. Auth Context (`src/context/AuthContext.tsx`)

```typescript
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';

interface User {
  id: number;
  email: string;
  name: string;
  role: 'admin' | 'member' | 'no_access';
  created_at: string;
  last_login: string;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credential: string, rememberMe: boolean) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  isAdmin: boolean;
  canAccess: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Configure axios defaults
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 'http://localhost:5000';
axios.defaults.withCredentials = true;

// Add auth token to all requests
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses with automatic token refresh
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      // Don't retry refresh token requests
      if (originalRequest.url?.includes('/api/auth/refresh')) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('rememberMe');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      // Try to refresh token
      try {
        const response = await axios.post('/api/auth/refresh', {
          rememberMe: localStorage.getItem('rememberMe') === 'true'
        });

        const { token } = response.data;
        localStorage.setItem('auth_token', token);

        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return axios(originalRequest);
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem('auth_token');
        localStorage.removeItem('rememberMe');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        setLoading(false);
        return;
      }

      const response = await axios.get('/api/auth/user');
      setUser(response.data.user);
    } catch (error) {
      console.error('Auth check failed:', error);
      localStorage.removeItem('auth_token');
    } finally {
      setLoading(false);
    }
  };

  const login = async (credential: string, rememberMe: boolean) => {
    try {
      const response = await axios.post('/api/auth/google', {
        credential,
        rememberMe
      });

      const { token, user } = response.data;

      localStorage.setItem('auth_token', token);
      localStorage.setItem('rememberMe', rememberMe.toString());

      setUser(user);

      // Check access
      if (user.role === 'no_access') {
        throw new Error('Access denied. Please contact an administrator.');
      }
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Login failed');
    }
  };

  const logout = async () => {
    try {
      await axios.post('/api/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('rememberMe');
      setUser(null);
      window.location.href = '/login';
    }
  };

  const refreshToken = async () => {
    try {
      const response = await axios.post('/api/auth/refresh', {
        rememberMe: localStorage.getItem('rememberMe') === 'true'
      });

      const { token } = response.data;
      localStorage.setItem('auth_token', token);
    } catch (error) {
      console.error('Token refresh failed:', error);
      throw error;
    }
  };

  const isAdmin = user?.role === 'admin';
  const canAccess = user?.role !== 'no_access' && user?.is_active === true;

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      logout,
      refreshToken,
      isAdmin,
      canAccess
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

### 3. Login Component (`src/components/Login.tsx`)

```typescript
import React, { useState } from 'react';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import { Card, Box, Alert, Typography, Checkbox, FormControlLabel } from '@mui/material';
import { useAuth } from '../context/AuthContext';

const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID || 'your-client-id-here';

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
          <Typography variant="h4" component="h1" gutterBottom>
            Your App Name
          </Typography>

          <Typography variant="subtitle1" color="text.secondary" gutterBottom sx={{ mb: 4 }}>
            Sign in with your company account
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
              hosted_domain="yourcompany.com"  // Change this
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
            Only @yourcompany.com email addresses are allowed
          </Typography>
        </Card>
      </Box>
    </GoogleOAuthProvider>
  );
};

export default Login;
```

### 4. Protected Route Component (`src/components/ProtectedRoute.tsx`)

```typescript
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { CircularProgress, Box } from '@mui/material';
import { useAuth } from '../context/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, requireAdmin = false }) => {
  const { user, loading, isAdmin, canAccess } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh'
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!canAccess) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          flexDirection: 'column'
        }}
      >
        <h2>Access Denied</h2>
        <p>Please contact an administrator for access to this application.</p>
      </Box>
    );
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
```

### 5. App Integration

```typescript
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import AdminPanel from './components/AdminPanel';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireAdmin>
                <AdminPanel />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
```

## Database Setup

### Create Tables
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    google_id VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(20) DEFAULT 'no_access' NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create index for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
```

### Migration Script
```python
from sqlalchemy import create_engine
from src.models.user import Base

# Create engine and tables
engine = create_engine('sqlite:///app.db')
Base.metadata.create_all(engine)
```

## Environment Configuration

### Backend (.env)
```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id-here

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-here
JWT_EXPIRY_HOURS=24

# Database
DATABASE_URL=sqlite:///app.db

# Flask
FLASK_ENV=development
FLASK_SECRET_KEY=your-flask-secret-key-here
```

### Frontend (.env)
```bash
# Google OAuth Configuration
REACT_APP_GOOGLE_CLIENT_ID=your-google-client-id-here

# API Configuration
REACT_APP_API_URL=http://localhost:5000
```

## Security Considerations

### 1. Domain Restriction
- Always restrict to your organization's domain
- Validate on both frontend and backend
- Example: `hosted_domain="yourcompany.com"` in GoogleLogin component

### 2. Token Security
- Use HttpOnly cookies for additional security
- Set Secure flag in production
- Implement proper CORS settings
- Use strong JWT secret keys

### 3. Environment Variables
- Never commit credentials to version control
- Use different credentials for development/production
- Rotate secrets regularly

### 4. Rate Limiting
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@auth_bp.route('/api/auth/google', methods=['POST'])
@limiter.limit("5 per minute")
def google_login():
    # ... login logic
```

### 5. HTTPS in Production
```python
# Force HTTPS in production
if not app.debug:
    @app.before_request
    def force_https():
        if not request.is_secure:
            return redirect(request.url.replace('http://', 'https://'))
```

## Testing

### Backend Tests
```python
import pytest
from src.services.auth import AuthService
from src.models.user import User, UserRole

def test_create_user():
    # Mock Google token verification
    user_info = {
        'google_id': '123456789',
        'email': 'test@yourcompany.com',
        'name': 'Test User'
    }

    auth_service = AuthService(db_session)
    user = auth_service.create_or_update_user(user_info)

    assert user.email == 'test@yourcompany.com'
    assert user.role == UserRole.NO_ACCESS

def test_jwt_token_generation():
    user = User(id=1, email='test@yourcompany.com', role=UserRole.MEMBER)
    auth_service = AuthService(db_session)
    token = auth_service.generate_jwt_token(user)

    payload = auth_service.verify_jwt_token(token)
    assert payload['user_id'] == 1
    assert payload['email'] == 'test@yourcompany.com'
```

### Frontend Tests
```typescript
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Login from '../components/Login';

test('renders login component', () => {
  render(
    <BrowserRouter>
      <Login />
    </BrowserRouter>
  );

  expect(screen.getByText('Sign in with your company account')).toBeInTheDocument();
});
```

## Common Issues & Troubleshooting

### 1. "Invalid Google token" Error
**Cause**: Client ID mismatch or token expired
**Solution**:
- Verify GOOGLE_CLIENT_ID in both frontend and backend
- Check token expiration
- Ensure domain matches Google Console configuration

### 2. CORS Issues
**Cause**: Incorrect CORS configuration
**Solution**:
```python
from flask_cors import CORS
CORS(app, supports_credentials=True, origins=['http://localhost:3000', 'http://localhost:4001'])
```

### 3. Cookie Not Set
**Cause**: SameSite/Secure cookie settings
**Solution**:
```python
# For local development
response.set_cookie(
    'auth_token',
    jwt_token,
    httponly=True,
    secure=False,  # Set to True in production
    samesite='Lax'  # Use 'Strict' in production
)
```

### 4. Token Refresh Loop
**Cause**: Axios interceptor trying to refresh expired refresh tokens
**Solution**: Check if request URL is refresh endpoint before attempting refresh

### 5. Database Migration Issues
**Cause**: Schema changes without proper migration
**Solution**:
```bash
# Drop and recreate tables (development only)
rm app.db
python -c "from src.models.user import Base; from sqlalchemy import create_engine; engine = create_engine('sqlite:///app.db'); Base.metadata.create_all(engine)"
```

## Deployment Considerations

### Production Environment Variables
```bash
# Use strong, unique secrets
JWT_SECRET_KEY=$(openssl rand -base64 64)
FLASK_SECRET_KEY=$(openssl rand -base64 32)

# Enable security features
FLASK_ENV=production
DATABASE_URL=postgresql://user:pass@host:port/db
```

### Docker Configuration
```dockerfile
# Dockerfile
FROM node:18 AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . ./
COPY --from=frontend-build /app/frontend/build ./static
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

### Nginx Configuration
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Summary

This implementation provides a robust Google SSO solution with:

✅ **Secure Authentication**: Google OAuth 2.0 with domain restriction
✅ **JWT Token Management**: Automatic refresh and secure storage
✅ **Role-Based Access Control**: Admin, Member, No Access roles
✅ **Production Ready**: Security headers, HTTPS, rate limiting
✅ **Developer Friendly**: Clear error handling and logging
✅ **Scalable**: Stateless JWT tokens, database persistence

### Key Files to Customize:
1. Change `self.allowed_domain` in `AuthService` (`src/services/auth.py:24`)
2. Update `self.admin_email` in `AuthService` (`src/services/auth.py:25`)
3. Set `hosted_domain` in Login component (`frontend/src/components/Login.tsx:69`)
4. Update Google Client ID in environment variables
5. Configure database connection string

This guide provides a complete, production-ready implementation that can be adapted for any React + Flask application requiring Google SSO authentication.