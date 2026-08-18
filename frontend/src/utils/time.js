/**
 * Time helpers.
 *
 * The server is the only clock that matters. `syncServerClock` records the
 * offset between the device clock and the server clock so the live timer keeps
 * counting correctly even on a device whose clock is wrong or was changed.
 */

let clockOffsetMs = 0;

export function syncServerClock(serverTimeIso) {
  if (!serverTimeIso) return;
  const serverMs = new Date(serverTimeIso).getTime();
  if (Number.isFinite(serverMs)) {
    clockOffsetMs = serverMs - Date.now();
  }
}

export function serverNow() {
  return Date.now() + clockOffsetMs;
}

export function getClockOffsetMs() {
  return clockOffsetMs;
}

export function parseIso(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function elapsedSeconds(startIso) {
  const start = parseIso(startIso);
  if (!start) return 0;
  return Math.max(0, Math.floor((serverNow() - start.getTime()) / 1000));
}

/** "05h 27m" */
export function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${String(hours).padStart(2, '0')}h ${String(minutes).padStart(2, '0')}m`;
}

/** "05h 27m 14s" -- used only for the live timer. */
export function formatDurationLong(totalSeconds) {
  const seconds = Math.max(0, Math.floor(totalSeconds || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return `${String(hours).padStart(2, '0')}h ${String(minutes).padStart(2, '0')}m ${String(
    secs,
  ).padStart(2, '0')}s`;
}

export function formatTime(iso, timeZone) {
  const date = parseIso(iso);
  if (!date) return '--:--';
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone,
  })
    .format(date)
    .toUpperCase();
}

export function formatDateLong(value, timeZone) {
  const date = value instanceof Date ? value : parseIso(dateOnlyToIso(value));
  if (!date) return '';
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: timeZone || 'UTC',
  }).format(date);
}

export function formatWeekday(value, timeZone) {
  const date = parseIso(dateOnlyToIso(value));
  if (!date) return '';
  return new Intl.DateTimeFormat('en-GB', { weekday: 'short', timeZone: timeZone || 'UTC' }).format(
    date,
  );
}

/** A plain YYYY-MM-DD is a calendar date, not an instant; anchor it at noon UTC
 *  so no timezone can shift it onto the neighbouring day. */
function dateOnlyToIso(value) {
  if (!value) return null;
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return `${value}T12:00:00Z`;
  }
  return value;
}

export function minutesToClock(minutes) {
  if (minutes === null || minutes === undefined) return '--:--';
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  const suffix = hours >= 12 ? 'PM' : 'AM';
  const display = hours % 12 === 0 ? 12 : hours % 12;
  return `${display}:${String(mins).padStart(2, '0')} ${suffix}`;
}

export function greeting(timeZone) {
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hour12: false, timeZone }).format(
      new Date(serverNow()),
    ),
  );
  if (hour < 12) return 'Good Morning';
  if (hour < 17) return 'Good Afternoon';
  return 'Good Evening';
}

export function todayIso(timeZone) {
  return new Intl.DateTimeFormat('en-CA', { timeZone }).format(new Date(serverNow()));
}

export function shiftDays(isoDate, days) {
  const date = new Date(`${isoDate}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
