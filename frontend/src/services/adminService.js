import { api, request } from './apiClient.js';

export function getDashboard() {
  return api.get('/admin/dashboard');
}

export function listUsers({ search, role, status, page = 1, pageSize = 50 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set('search', search);
  if (role) params.set('role', role);
  if (status) params.set('status', status);
  return api.get(`/admin/users?${params}`);
}

export function getUser(userId) {
  return api.get(`/admin/users/${userId}`);
}

export function createUser(payload) {
  return api.post('/admin/users', payload);
}

export function updateUser(userId, payload) {
  return api.patch(`/admin/users/${userId}`, payload);
}

export function setUserStatus(userId, status) {
  return api.patch(`/admin/users/${userId}/status`, { status });
}

export function resetPassword(userId) {
  return api.post(`/admin/users/${userId}/reset-password`);
}

export function getUserAttendance(userId, { period = 'month', fromDate, toDate } = {}) {
  const params = new URLSearchParams({ period });
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  return api.get(`/admin/attendance/${userId}?${params}`);
}

export function getAttendance({ fromDate, toDate, userId, status } = {}) {
  const params = new URLSearchParams();
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  if (userId) params.set('user_id', userId);
  if (status) params.set('status', status);
  return api.get(`/admin/attendance?${params}`);
}

export function getPunchEvents({ userId, sessionId, validationStatus, page = 1 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: '50' });
  if (userId) params.set('user_id', userId);
  if (sessionId) params.set('session_id', sessionId);
  if (validationStatus) params.set('validation_status', validationStatus);
  return api.get(`/admin/punch-events?${params}`);
}

export function getWorkspace() {
  return api.get('/admin/workspace');
}

export function updateWorkspace(payload) {
  return api.patch('/admin/workspace', payload);
}

export function getAuditLogs({ action, result, userId, fromDate, toDate, page = 1 } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: '50' });
  if (action) params.set('action', action);
  if (result) params.set('result', result);
  if (userId) params.set('user_id', userId);
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  return api.get(`/admin/audit-logs?${params}`);
}

/** Streams the CSV through fetch so the Authorization header is applied, then
 *  hands the browser a blob to save. */
export async function downloadAttendanceCsv({ fromDate, toDate, userId }) {
  const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
  if (userId) params.set('user_id', userId);
  const response = await request(`/admin/reports/attendance.csv?${params}`, { raw: true });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `attendance_${fromDate}_to_${toDate}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
