import { apiClient, setStoredToken, clearStoredToken } from './api';

/**
 * Authentication API Service
 */

export async function loginUser(email, password) {
  const data = await apiClient('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  if (data.access_token) {
    setStoredToken(data.access_token);
  }
  return data;
}

export async function getCurrentUser() {
  return await apiClient('/auth/me');
}

export function logoutUser() {
  clearStoredToken();
}
