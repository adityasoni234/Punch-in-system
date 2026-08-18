import { useEffect, useState } from 'react';
import { elapsedSeconds, serverNow } from '../utils/time.js';

/**
 * Ticks a display-only counter derived from the server-issued punch-in
 * timestamp and the measured server/device clock offset.
 *
 * No GPS is involved. Nothing here is authoritative -- the backend recomputes
 * every duration from its own timestamps.
 */
export function useLiveTimer(startIso, active = true) {
  const [seconds, setSeconds] = useState(() => (startIso ? elapsedSeconds(startIso) : 0));

  useEffect(() => {
    if (!startIso || !active) {
      setSeconds(startIso ? elapsedSeconds(startIso) : 0);
      return undefined;
    }
    setSeconds(elapsedSeconds(startIso));

    const tick = () => setSeconds(elapsedSeconds(startIso));
    const interval = window.setInterval(tick, 1000);
    // Coming back from a locked screen or a background tab: re-derive rather
    // than assume the interval kept firing.
    const onVisible = () => {
      if (document.visibilityState === 'visible') tick();
    };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', tick);

    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', tick);
    };
  }, [startIso, active]);

  return seconds;
}

export function useServerTick(intervalMs = 1000) {
  const [now, setNow] = useState(() => serverNow());
  useEffect(() => {
    const id = window.setInterval(() => setNow(serverNow()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}
