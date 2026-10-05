/**
 * Application constants and environment configuration
 */

const configuredApiUrl = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL;
const fallbackApiUrl = import.meta.env.PROD
  ? 'https://kredobook.onrender.com'
  : 'http://127.0.0.1:8000';

// Remove a trailing slash so endpoint paths such as `/auth/login` are always valid.
export const API_BASE_URL = (configuredApiUrl || fallbackApiUrl).replace(/\/$/, '');
