import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';

interface User {
  id: number;
  email: string;
  name: string;
  role: 'admin' | 'pm' | 'member' | 'no_access';
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
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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
      if (originalRequest.url?.includes('/api/auth/refresh') || originalRequest.url?.includes('/api/auth/google')) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('rememberMe');
        // Let React Admin's authProvider handle the redirect
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
        // Refresh failed - clean up and let React Admin handle redirect
        localStorage.removeItem('auth_token');
        localStorage.removeItem('rememberMe');
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
      // Auth check failed - remove token and let user re-authenticate
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

      if (!token) {
        throw new Error('No token received from server');
      }

      localStorage.setItem('auth_token', token);
      localStorage.setItem('rememberMe', rememberMe.toString());

      setUser(user);

      // Redirect based on role
      if (user.role === 'NO_ACCESS') {
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
      // Logout endpoint may fail if token expired - proceed with local cleanup
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('rememberMe');
      setUser(null);
      // Let React Admin handle the redirect via authProvider
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
      // Token refresh failed - will be handled by axios interceptor
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