/**
 * Thin fetch wrapper.
 *
 * - The access token lives in module memory only. It is never written to
 *   localStorage or sessionStorage, so an XSS bug cannot read it back later.
 *   Session continuity comes from the HttpOnly refresh cookie instead.
 * - A single in-flight refresh is shared by all callers, so a burst of 401s
 *   produces one refresh, not one per request.
 * - Every request carries the server's clock forward into the UI.
 */
import { ErrorCode } from '../utils/errorCodes.js';
import { syncServerClock } from '../utils/time.js';

/**
 * Same-origin by default.
 *
 * Keeping the API on the same origin as the app is a security decision, not a
 * convenience one: it lets the refresh token stay in a `SameSite=Lax` cookie.
 * Set VITE_API_BASE_URL only if the API genuinely lives on another origin, in
 * which case the cookie has to be relaxed to `SameSite=None` server-side and
 * the origin must be listed in CORS_ORIGINS.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const CROSS_ORIGIN = /^https?:\/\//i.test(BASE_URL);
const CREDENTIALS = CROSS_ORIGIN ? 'include' : 'same-origin';

let accessToken = null;
let onSessionLost = null;
let refreshPromise = null;

export class ApiError extends Error {
  constructor(code, message, { status = 0, details = {}, retryAfter = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
    this.retryAfter = retryAfter;
  }
}

export function setAccessToken(token) {
  accessToken = token || null;
}

export function getAccessToken() {
  return accessToken;
}

export function setSessionLostHandler(handler) {
  onSessionLost = handler;
}

async function parseBody(response) {
  const type = response.headers.get('content-type') || '';
  if (!type.includes('application/json')) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function toError(response, body) {
  const retryAfterHeader = response.headers.get('retry-after');
  return new ApiError(
    body?.code || ErrorCode.INTERNAL_ERROR,
    body?.message || 'Something went wrong. Please try again.',
    {
      status: response.status,
      details: body?.details || {},
      retryAfter: retryAfterHeader ? Number(retryAfterHeader) : null,
    },
  );
}

async function refreshSession() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: CREDENTIALS,
        headers: { Accept: 'application/json' },
      });
      const body = await parseBody(response);
      if (!response.ok) throw toError(response, body);
      accessToken = body.access_token;
      syncServerClock(body.server_time);
      return body;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function request(
  path,
  { method = 'GET', body, headers = {}, signal, auth = true, raw = false, retryOn401 = true } = {},
) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    throw new ApiError(ErrorCode.OFFLINE, 'You are offline. Check your connection and try again.');
  }

  const requestHeaders = { Accept: 'application/json', ...headers };
  if (body !== undefined) requestHeaders['Content-Type'] = 'application/json';
  if (auth && accessToken) requestHeaders.Authorization = `Bearer ${accessToken}`;

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: CREDENTIALS,
      cache: 'no-store',
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError(
      ErrorCode.NETWORK_ERROR,
      'Could not reach the server. Check your connection and try again.',
    );
  }

  if (response.status === 401 && auth && retryOn401) {
    const payload = await parseBody(response);
    const code = payload?.code;
    if (code === ErrorCode.TOKEN_EXPIRED || code === ErrorCode.NOT_AUTHENTICATED) {
      try {
        await refreshSession();
      } catch {
        accessToken = null;
        onSessionLost?.();
        throw toError(response, payload);
      }
      return request(path, { method, body, headers, signal, auth, raw, retryOn401: false });
    }
    accessToken = null;
    onSessionLost?.();
    throw toError(response, payload);
  }

  if (raw) {
    if (!response.ok) throw toError(response, await parseBody(response));
    return response;
  }

  const payload = await parseBody(response);
  if (!response.ok) {
    const error = toError(response, payload);
    if (error.status === 403 && error.code === ErrorCode.USER_DISABLED) {
      accessToken = null;
      onSessionLost?.();
    }
    throw error;
  }
  if (payload?.server_time) syncServerClock(payload.server_time);
  return payload;
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  refresh: refreshSession,
};
