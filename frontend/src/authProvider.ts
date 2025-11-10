import { AuthProvider } from 'react-admin';
import axios from 'axios';

// React-admin compatible auth provider
export const authProvider: AuthProvider = {
  // Called when the user attempts to log in
  login: async ({ username, password }) => {
    // This is handled by Google OAuth in Login component, not used directly
    return Promise.resolve();
  },

  // Called when the user clicks on the logout button
  logout: async () => {
    try {
      await axios.post('/api/auth/logout');
    } catch (error) {
      // Logout endpoint may fail if token expired - proceed with local cleanup
    } finally {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('rememberMe');
    }
    return Promise.resolve();
  },

  // Called when the API returns an error
  checkError: async ({ status }: { status: number }) => {
    if (status === 401 || status === 403) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('rememberMe');
      return Promise.reject();
    }
    return Promise.resolve();
  },

  // Called when the user navigates to a new location to check for authentication
  checkAuth: async () => {
    const token = localStorage.getItem('auth_token');
    return token ? Promise.resolve() : Promise.reject();
  },

  // Called when the user navigates to a new location to check for permissions
  getPermissions: async (params: any) => {
    // Don't even try to fetch permissions if there's no token
    const token = localStorage.getItem('auth_token');
    if (!token) {
      return Promise.reject({ message: 'No auth token', redirectTo: '/login' });
    }

    try {
      const response = await axios.get('/api/auth/user');
      const user = response.data.user;
      return Promise.resolve(user.role);
    } catch (error: any) {
      // If 401, clear token and force login
      if (error?.response?.status === 401) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('rememberMe');
      }
      return Promise.reject({ message: 'Auth failed', redirectTo: '/login' });
    }
  },

  // Get user identity
  getIdentity: async () => {
    // Don't even try to fetch identity if there's no token
    const token = localStorage.getItem('auth_token');
    if (!token) {
      return Promise.reject({ message: 'No auth token', redirectTo: '/login' });
    }

    try {
      const response = await axios.get('/api/auth/user');
      const user = response.data.user;
      return Promise.resolve({
        id: user.id,
        fullName: user.name,
        avatar: user.picture
      });
    } catch (error: any) {
      // If 401, clear token and force login
      if (error?.response?.status === 401) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('rememberMe');
      }
      return Promise.reject({ message: 'Auth failed', redirectTo: '/login' });
    }
  }
};