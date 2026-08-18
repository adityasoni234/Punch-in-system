import { useCallback, useEffect, useState } from 'react';
import { ErrorCode } from '../utils/errorCodes.js';

/**
 * One-shot location capture. Deliberately NOT `watchPosition`.
 *
 * The app reads the device location only at the moment the user punches (or
 * explicitly asks to verify). There is no polling, no background tracking and
 * nothing is captured after a punch succeeds -- the live timer runs on
 * timestamps alone.
 */

export class GeolocationError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'GeolocationError';
    this.code = code;
  }
}

const OPTIONS = {
  enableHighAccuracy: true,
  timeout: 15000,
  maximumAge: 0, // never reuse a cached fix for an attendance decision
};

export function isSupported() {
  return typeof navigator !== 'undefined' && 'geolocation' in navigator;
}

/**
 * Browsers only expose location on a "secure context": HTTPS, or localhost.
 *
 * Opening the app over plain HTTP on a LAN address (http://192.168.x.x) is the
 * single most common reason location fails on a phone even though Location
 * Services are switched on system-wide. iOS Safari in particular reports the
 * permission as grantable and then denies the actual call, which looks
 * identical to the user having blocked the site.
 */
export function isSecureContextOk() {
  if (typeof window === 'undefined') return true;
  if (window.isSecureContext) return true;
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1' || host === '[::1]';
}

export async function readPermissionState() {
  if (!isSupported()) return 'unsupported';
  if (!isSecureContextOk()) return 'insecure';
  if (!navigator.permissions?.query) return 'unknown';
  try {
    const status = await navigator.permissions.query({ name: 'geolocation' });
    return status.state; // 'granted' | 'prompt' | 'denied'
  } catch {
    return 'unknown';
  }
}

export function capturePosition() {
  return new Promise((resolve, reject) => {
    if (!isSecureContextOk()) {
      reject(
        new GeolocationError(
          ErrorCode.LOCATION_INSECURE_CONTEXT,
          'This page is not being served over HTTPS, so the browser will not '
            + 'release your location.',
        ),
      );
      return;
    }
    if (!isSupported()) {
      reject(
        new GeolocationError(
          ErrorCode.LOCATION_UNSUPPORTED,
          'This browser cannot provide a location. Open the app in Chrome or Safari.',
        ),
      );
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude, accuracy } = position.coords;
        if (
          !Number.isFinite(latitude) ||
          !Number.isFinite(longitude) ||
          !Number.isFinite(accuracy)
        ) {
          reject(
            new GeolocationError(
              ErrorCode.LOCATION_UNAVAILABLE,
              'Your device returned an incomplete location. Please try again.',
            ),
          );
          return;
        }
        resolve({ latitude, longitude, accuracy, capturedAt: position.timestamp });
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          reject(
            new GeolocationError(
              ErrorCode.LOCATION_PERMISSION_DENIED,
              'Location permission is blocked for this site.',
            ),
          );
        } else if (error.code === error.TIMEOUT) {
          reject(
            new GeolocationError(
              ErrorCode.LOCATION_TIMEOUT,
              'Getting your location took too long. Move to an open area and try again.',
            ),
          );
        } else {
          reject(
            new GeolocationError(
              ErrorCode.LOCATION_UNAVAILABLE,
              'Your device could not determine its location right now.',
            ),
          );
        }
      },
      OPTIONS,
    );
  });
}

/** Watches only the PERMISSION state (not the position) so the UI can explain
 *  itself before the user taps anything. */
export function usePermissionState() {
  const [state, setState] = useState('unknown');

  const refresh = useCallback(async () => {
    setState(await readPermissionState());
  }, []);

  useEffect(() => {
    let cancelled = false;
    let permissionStatus = null;
    const onChange = () => {
      if (!cancelled && permissionStatus) setState(permissionStatus.state);
    };

    (async () => {
      if (!isSupported()) {
        if (!cancelled) setState('unsupported');
        return;
      }
      if (!isSecureContextOk()) {
        if (!cancelled) setState('insecure');
        return;
      }
      if (!navigator.permissions?.query) {
        if (!cancelled) setState('unknown');
        return;
      }
      try {
        permissionStatus = await navigator.permissions.query({ name: 'geolocation' });
        if (cancelled) return;
        setState(permissionStatus.state);
        permissionStatus.addEventListener('change', onChange);
      } catch {
        if (!cancelled) setState('unknown');
      }
    })();

    return () => {
      cancelled = true;
      permissionStatus?.removeEventListener('change', onChange);
    };
  }, []);

  return { permissionState: state, refreshPermissionState: refresh };
}
