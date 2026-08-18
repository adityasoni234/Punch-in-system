import { api, request, setAccessToken } from './apiClient.js';
import { syncServerClock } from '../utils/time.js';

export async function login(email, password) {
  const session = await request('/auth/login', {
    method: 'POST',
    body: { email, password },
    auth: false,
  });
  setAccessToken(session.access_token);
  syncServerClock(session.server_time);
  return session;
}

export async function restoreSession() {
  const session = await api.refresh();
  syncServerClock(session.server_time);
  return session;
}

export async function me() {
  return api.get('/auth/me');
}

export async function logout() {
  try {
    await api.post('/auth/logout');
  } finally {
    setAccessToken(null);
  }
}

export async function changePassword(currentPassword, newPassword) {
  return api.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
