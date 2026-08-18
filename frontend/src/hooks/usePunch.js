import { useCallback, useRef, useState } from 'react';
import { capturePosition, GeolocationError, isSecureContextOk } from './useGeolocation.js';
import { punch as punchApi } from '../services/attendanceService.js';
import { ApiError } from '../services/apiClient.js';
import { ErrorCode } from '../utils/errorCodes.js';

/**
 * The full punch pipeline, in order:
 *
 *   online check -> permission check -> real GPS fix -> POST to the server
 *
 * The server has the final say on every one of those steps that matters. The
 * client-side checks exist to give a useful message before a round trip, never
 * to decide whether the punch is valid.
 */

const PHASE = {
  IDLE: 'idle',
  LOCATING: 'locating',
  VERIFYING: 'verifying',
};

function newIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function usePunch({ online, onSuccess, onStateChanged }) {
  const [phase, setPhase] = useState(PHASE.IDLE);
  const [failure, setFailure] = useState(null);
  const [success, setSuccess] = useState(null);
  // A key survives retries of the SAME user intent, so a retry after a network
  // blip cannot create a second session.
  const pendingKey = useRef(null);

  const reset = useCallback(() => {
    setFailure(null);
    setSuccess(null);
    setPhase(PHASE.IDLE);
  }, []);

  const run = useCallback(
    async (direction) => {
      setFailure(null);
      setSuccess(null);

      if (!online) {
        setFailure({
          code: ErrorCode.OFFLINE,
          message:
            'Punching requires an active internet connection so the server can verify your location.',
        });
        return null;
      }

      // An insecure origin is the one case worth short-circuiting: the browser
      // will never release a position, so prompting would only produce a
      // confusing "denied". Everything else goes straight to the real API so
      // the browser -- not this app -- decides, and the user gets the native
      // permission prompt rather than being told by us that they are blocked.
      if (!isSecureContextOk()) {
        setFailure({
          code: ErrorCode.LOCATION_INSECURE_CONTEXT,
          message:
            'This page is not being served over HTTPS, so the browser will not release '
            + 'your location.',
        });
        return null;
      }

      setPhase(PHASE.LOCATING);
      let position;
      try {
        position = await capturePosition();
      } catch (error) {
        setPhase(PHASE.IDLE);
        if (error instanceof GeolocationError) {
          setFailure({ code: error.code, message: error.message });
        } else {
          setFailure({
            code: ErrorCode.LOCATION_UNAVAILABLE,
            message: 'Your location could not be read. Please try again.',
          });
        }
        return null;
      }

      setPhase(PHASE.VERIFYING);
      if (!pendingKey.current) pendingKey.current = newIdempotencyKey();

      try {
        const result = await punchApi(direction, position, pendingKey.current);
        pendingKey.current = null;
        setPhase(PHASE.IDLE);
        setSuccess({ direction, result, accuracy: position.accuracy });
        onSuccess?.(result);
        return result;
      } catch (error) {
        setPhase(PHASE.IDLE);
        if (error instanceof ApiError) {
          // A conflict means our view of the state was stale; a fresh key is
          // needed for the next attempt.
          if (
            error.code === ErrorCode.ALREADY_PUNCHED_IN ||
            error.code === ErrorCode.NO_ACTIVE_SESSION ||
            error.code === ErrorCode.DUPLICATE_REQUEST
          ) {
            pendingKey.current = null;
            onStateChanged?.();
          }
          if (
            error.code === ErrorCode.OUTSIDE_GEOFENCE ||
            error.code === ErrorCode.ACCURACY_TOO_LOW ||
            error.code === ErrorCode.INVALID_COORDINATES ||
            error.code === ErrorCode.IMPOSSIBLE_MOVEMENT
          ) {
            // The reading itself was rejected, so the next attempt is a new
            // intent and must not replay this one.
            pendingKey.current = null;
          }
          setFailure({
            code: error.code,
            message: error.message,
            retryAfter: error.retryAfter,
            accuracy: position.accuracy,
          });
        } else {
          setFailure({
            code: ErrorCode.NETWORK_ERROR,
            message: 'Could not reach the server. You have not been punched in or out.',
          });
        }
        return null;
      }
    },
    [online, onSuccess, onStateChanged],
  );

  return {
    phase,
    busy: phase !== PHASE.IDLE,
    locating: phase === PHASE.LOCATING,
    verifying: phase === PHASE.VERIFYING,
    failure,
    success,
    punch: run,
    reset,
  };
}
