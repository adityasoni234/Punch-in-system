import { api, request } from './apiClient.js';

export function getToday() {
  return api.get('/attendance/today');
}

/**
 * Punch in or out.
 *
 * Only raw sensor values are sent. Distance, validity, duration and attendance
 * state are all decided by the server. The idempotency key makes a retry after
 * a flaky network safe: the server replays the original outcome instead of
 * creating a second session.
 */
export function punch(direction, { latitude, longitude, accuracy }, idempotencyKey) {
  return request(`/attendance/${direction === 'in' ? 'punch-in' : 'punch-out'}`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: {
      latitude,
      longitude,
      accuracy,
      captured_at: new Date().toISOString(),
    },
  });
}

export function getHistory({ period = 'month', fromDate, toDate } = {}) {
  const params = new URLSearchParams({ period });
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  return api.get(`/attendance/history?${params}`);
}

export function getSummary({ period = 'week', fromDate, toDate } = {}) {
  const params = new URLSearchParams({ period });
  if (fromDate) params.set('from_date', fromDate);
  if (toDate) params.set('to_date', toDate);
  return api.get(`/attendance/summary?${params}`);
}
