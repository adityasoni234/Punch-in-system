import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Clock, MapPin, RefreshCw } from 'lucide-react';
import {
  Button,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  Notice,
  Sheet,
  SkeletonCard,
} from '../components/common/index.jsx';
import {
  PunchButton,
  SessionList,
  StatusCard,
} from '../components/attendance/PunchControls.jsx';
import {
  LocationPermissionPrompt,
  PunchFailure,
} from '../components/location/LocationStates.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { useOnlineStatus } from '../hooks/useOnlineStatus.js';
import { usePermissionState } from '../hooks/useGeolocation.js';
import { usePunch } from '../hooks/usePunch.js';
import { getToday } from '../services/attendanceService.js';
import { formatDuration, formatTime, greeting } from '../utils/time.js';
import { metres } from '../utils/format.js';

export default function Dashboard() {
  const { user, workspace, timezone } = useAuth();
  const online = useOnlineStatus();
  const { permissionState, refreshPermissionState } = usePermissionState();
  const { data, error, loading, reload } = useAsync(() => getToday(), []);
  const [resultOpen, setResultOpen] = useState(false);

  const onSuccess = useCallback(() => {
    reload({ quiet: true });
    setResultOpen(true);
  }, [reload]);

  const onStateChanged = useCallback(() => reload({ quiet: true }), [reload]);

  const { punch, busy, phase, failure, success, reset } = usePunch({
    online,
    onSuccess,
    onStateChanged,
  });

  // Refresh when the app comes back to the foreground: the session may have
  // been closed elsewhere, or the day may have rolled over.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') reload({ quiet: true });
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [reload]);

  if (loading && !data) {
    return (
      <>
        <SkeletonCard lines={4} />
        <SkeletonCard lines={2} />
      </>
    );
  }

  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return null;

  const state = data.status;
  const direction = state === 'PRESENT' ? 'out' : 'in';
  const completed = data.sessions.filter((session) => !session.is_active);
  const lastSession = completed[completed.length - 1] || null;

  const handlePunch = async (which) => {
    await punch(which);
    refreshPermissionState();
  };

  return (
    <>
      <div>
        <div className="greeting">
          {greeting(timezone)}, {user?.name?.split(' ')[0]}
        </div>
        <div className="muted">{workspace?.name}</div>
      </div>

      <Card accent={state === 'PRESENT'}>
        <StatusCard
          state={state}
          activeSession={data.active_session}
          totalSeconds={data.total_seconds}
          lastSession={lastSession}
          timezone={timezone}
        />
      </Card>

      {permissionState === 'prompt' && (
        <LocationPermissionPrompt onEnable={() => handlePunch(direction)} busy={busy} />
      )}

      <PunchFailure failure={failure} onRetry={() => handlePunch(direction)} />

      <PunchButton
        direction={direction}
        onPunch={handlePunch}
        busy={busy}
        phase={phase}
        disabled={!online}
      />

      {!online && (
        <Notice variant="warn" title="Offline">
          Punching requires an active internet connection.
        </Notice>
      )}

      <Card flush>
        <div className="day-card__head">
          <span className="day-card__date">Today</span>
          <span className="day-card__total">{formatDuration(data.total_seconds)}</span>
        </div>
        {data.sessions.length === 0 ? (
          <EmptyState icon={Clock} title="No sessions yet">
            Your punches will appear here as soon as you punch in.
          </EmptyState>
        ) : (
          <SessionList sessions={data.sessions} timezone={timezone} />
        )}
      </Card>

      <Card>
        <CardTitle
          action={
            <Button size="sm" variant="ghost" icon={RefreshCw} onClick={() => reload()}>
              Refresh
            </Button>
          }
        >
          Verification
        </CardTitle>
        <p className="tiny" style={{ margin: 0, lineHeight: 1.5 }}>
          <MapPin size={12} style={{ verticalAlign: '-1px' }} /> Your location is read only when you
          punch, and is checked by the server against the workspace geofence (radius{' '}
          {metres(workspace?.radius_meters)}, accuracy limit{' '}
          {metres(workspace?.accuracy_threshold_meters)}). You are not tracked at any other time.
        </p>
      </Card>

      <Sheet
        open={resultOpen && Boolean(success)}
        onClose={() => {
          setResultOpen(false);
          reset();
        }}
        title={success?.direction === 'in' ? 'Punched in' : 'Punched out'}
      >
        {success && (
          <div className="stack">
            <div className="row" style={{ color: 'var(--green-700)' }}>
              <CheckCircle2 size={22} />
              <strong>Workspace verified</strong>
            </div>
            <div className="stack stack--tight">
              <div className="kv">
                <span className="kv__key">
                  {success.direction === 'in' ? 'Punched in at' : 'Punched out at'}
                </span>
                <span className="kv__value">
                  {formatTime(
                    success.direction === 'in'
                      ? success.result.punch_in
                      : success.result.punch_out,
                    timezone,
                  )}
                </span>
              </div>
              {success.direction === 'out' && (
                <div className="kv">
                  <span className="kv__key">Session duration</span>
                  <span className="kv__value">
                    {formatDuration(success.result.duration_seconds)}
                  </span>
                </div>
              )}
              <div className="kv">
                <span className="kv__key">Today&apos;s total</span>
                <span className="kv__value">
                  {formatDuration(success.result.today_total_seconds)}
                </span>
              </div>
              <div className="kv">
                <span className="kv__key">Distance from workspace</span>
                <span className="kv__value">
                  {metres(success.result.verification.distance_meters)}
                </span>
              </div>
              <div className="kv">
                <span className="kv__key">GPS accuracy</span>
                <span className="kv__value">
                  {metres(success.result.verification.accuracy_meters)}
                </span>
              </div>
            </div>
            <Button
              variant="primary"
              block
              onClick={() => {
                setResultOpen(false);
                reset();
              }}
            >
              Done
            </Button>
          </div>
        )}
      </Sheet>
    </>
  );
}
