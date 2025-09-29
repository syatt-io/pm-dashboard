// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL ||
  (window.location.hostname === 'localhost'
    ? 'http://localhost:4000'
    : 'https://agent-pm-tsbbb.ondigitalocean.app');

export default API_BASE_URL;

// Export as named export for use with fetch
export const getApiUrl = (path: string = '') => `${API_BASE_URL}${path}`;