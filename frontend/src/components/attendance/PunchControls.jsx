import { Fingerprint, LogOut, MapPin, ShieldCheck } from 'lucide-react';
import { Badge } from '../common/index.jsx';
import { formatDuration, formatDurationLong, formatTime } from '../../utils/time.js';
import { useLiveTimer } from '../../hooks/useLiveTimer.js';

export function PunchButton({ direction, onPunch, busy, phase, disabled }) {
  const isIn = direction === 'in';
  const label = busy
    ? phase === 'locating'
      ? 'Getting your location…'
      : 'Verifying with the server…'
    : isIn
      ? 'PUNCH IN'
      : 'PUNCH OUT';

  return (
    <button
      type="button"
      className={`punch punch--${isIn ? 'in' : 'out'}`}
      onClick={() => onPunch(direction)}
      disabled={busy || disabled}
      aria-busy={busy}
    >
      {busy ? (
        <span className="spinner" style={{ width: 26, height: 26, borderWidth: 3 }} />
      ) : isIn ? (
        <Fingerprint size={30} strokeWidth={2.2} />
      ) : (
        <LogOut size={30} strokeWidth={2.2} />
      )}
      <span>{label}</span>
      {!busy && (
        <span className="punch__hint">
          <MapPin size={13} style={{ verticalAlign: '-2px' }} /> Location is checked when you tap
        </span>
      )}
    </button>
  );
}

export function LiveTimer({ startIso, active }) {
  const seconds = useLiveTimer(startIso, active);
  return (
    <div className="value-lg mono" aria-live="off">
      {formatDurationLong(seconds)}
    </div>
  );
}

export function StatusCard({ state, activeSession, totalSeconds, lastSession, timezone }) {
  if (state === 'PRESENT' && activeSession) {
    return (
      <div className="stack">
        <div className="row row--between">
          <Badge variant="present" dot>
            PRESENT
          </Badge>
          <Badge variant="info">
            <ShieldCheck size={13} /> Workspace verified
          </Badge>
        </div>
        <div>
          <div className="tiny">Punched in</div>
          <div className="value-md">{formatTime(activeSession.punch_in, timezone)}</div>
        </div>
        <div>
          <div className="tiny">Time in workspace</div>
          <LiveTimer startIso={activeSession.punch_in} active />
        </div>
      </div>
    );
  }

  if (state === 'CHECKED_OUT') {
    return (
      <div className="stack">
        <Badge variant="checked-out" dot>
          CHECKED OUT
        </Badge>
        <div>
          <div className="tiny">Today&apos;s total</div>
          <div className="value-lg mono">{formatDuration(totalSeconds)}</div>
        </div>
        {lastSession && (
          <div>
            <div className="tiny">Last session</div>
            <div className="value-md">
              {formatTime(lastSession.punch_in, timezone)} →{' '}
              {formatTime(lastSession.punch_out, timezone)}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="stack">
      <Badge variant="absent" dot>
        NOT PRESENT
      </Badge>
      <p className="muted" style={{ margin: 0 }}>
        You have not punched in today.
      </p>
    </div>
  );
}

export function SessionRow({ session, index, timezone }) {
  const active = session.is_active || !session.punch_out;
  const seconds = useLiveTimer(session.punch_in, active);
  const duration = active ? seconds : session.duration_seconds || 0;
  return (
    <div className="session">
      <div style={{ minWidth: 0 }}>
        <div className="session__index">Session {index + 1}</div>
        <div className="session__time">
          {formatTime(session.punch_in, timezone)} →{' '}
          {active ? (
            <span style={{ color: 'var(--green-600)', fontWeight: 650 }}>Active</span>
          ) : (
            formatTime(session.punch_out, timezone)
          )}
        </div>
      </div>
      <div className="session__duration">{formatDuration(duration)}</div>
    </div>
  );
}

export function SessionList({ sessions, timezone }) {
  return (
    <div>
      {sessions.map((session, index) => (
        <SessionRow key={session.id} session={session} index={index} timezone={timezone} />
      ))}
    </div>
  );
}
