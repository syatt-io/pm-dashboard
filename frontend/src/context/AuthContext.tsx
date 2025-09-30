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
axios.defaults.baseURL = process.env.REACT_APP_API_URL ||
  (window.location.hostname === 'localhost'
    ? 'http://localhost:4000'
    : 'https://agent-pm-tsbbb.ondigitalocean.app');
axios.defaults.withCredentials = true;

// Add auth token to all requests
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  console.log('[axios interceptor] Request to:', config.url);
  console.log('[axios interceptor] Token exists:', !!token);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
    console.log('[axios interceptor] Authorization header set');
  } else {
    console.log('[axios interceptor] No token, skipping Authorization header');
  }
  return config;
});

// Handle 401 responses
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      // Don't retry refresh token requests to avoid infinite loops
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
      console.log('[AuthContext] login - Sending login request with credential:', credential.substring(0, 50) + '...');
      const response = await axios.post('/api/auth/google', {
        credential,
        rememberMe
      });

      console.log('[AuthContext] login - Login response received:', response);
      console.log('[AuthContext] login - Response status:', response.status);
      console.log('[AuthContext] login - Response data:', response.data);

      const { token, user } = response.data;

      if (!token) {
        console.error('[AuthContext] login - No token in response!');
        throw new Error('No token received from server');
      }

      console.log('[AuthContext] login - Token received, length:', token.length);
      console.log('[AuthContext] login - Token preview:', token.substring(0, 20) + '...');

      localStorage.setItem('auth_token', token);
      localStorage.setItem('rememberMe', rememberMe.toString());

      // Verify token was stored
      const storedToken = localStorage.getItem('auth_token');
      console.log('[AuthContext] login - Token stored in localStorage:', !!storedToken);
      console.log('[AuthContext] login - Stored token matches:', storedToken === token);

      setUser(user);

      // Redirect based on role
      if (user.role === 'no_access') {
        throw new Error('Access denied. Please contact an administrator.');
      }
    } catch (error: any) {
      console.error('Login failed:', error);
      console.error('Error response:', error.response);
      console.error('Error status:', error.response?.status);
      console.error('Error data:', error.response?.data);
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