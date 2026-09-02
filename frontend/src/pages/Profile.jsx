import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, LogOut, MapPin, TrendingUp } from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  CardTitle,
  ErrorState,
  KeyValue,
  SegmentedControl,
  SkeletonCard,
  StatTile,
} from '../components/common/index.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { getSummary } from '../services/attendanceService.js';
import { formatDuration, minutesToClock } from '../utils/time.js';
import { initials, metres } from '../utils/format.js';

const PERIODS = [
  { value: 'week', label: 'This week' },
  { value: 'month', label: 'This month' },
];

export default function Profile() {
  const { user, workspace, signOut } = useAuth();
  const navigate = useNavigate();
  const [period, setPeriod] = useState('week');
  const { data, error, loading, reload } = useAsync(() => getSummary({ period }), [period]);

  const handleSignOut = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <>
      <Card>
        <div className="row">
          <div className="avatar" style={{ width: 52, height: 52, fontSize: 18 }}>
            {initials(user?.name)}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 680, fontSize: 17 }}>{user?.name}</div>
            <div className="tiny">{user?.email}</div>
          </div>
          <Badge variant={user?.role === 'ADMIN' ? 'info' : 'default'}>{user?.role}</Badge>
        </div>
        <div style={{ marginTop: 'var(--sp-4)' }}>
          <KeyValue label="Member ID">{user?.member_id}</KeyValue>
          <KeyValue label="Status">{user?.status}</KeyValue>
        </div>
      </Card>

      <Card>
        <CardTitle>Analytics</CardTitle>
        <SegmentedControl
          options={PERIODS}
          value={period}
          onChange={setPeriod}
          ariaLabel="Analytics period"
        />
        <div style={{ height: 'var(--sp-3)' }} />
        {loading && !data && <SkeletonCard lines={3} />}
        {error && <ErrorState error={error} onRetry={reload} />}
        {data && (
          <>
            <div className="grid-2">
              <StatTile label="Days present" value={data.days_present} />
              <StatTile label="Days absent" value={data.days_absent} />
              <StatTile label="Total time" value={formatDuration(data.total_seconds)} />
              <StatTile
                label="Average / day"
                value={formatDuration(data.average_seconds_per_present_day)}
              />
            </div>
            <div style={{ marginTop: 'var(--sp-4)' }}>
              <KeyValue label="Late arrivals">{data.late_arrivals}</KeyValue>
              <KeyValue label="Longest session">
                {formatDuration(data.longest_session_seconds)}
              </KeyValue>
              <KeyValue label="Average arrival">
                {minutesToClock(data.average_arrival_minutes)}
              </KeyValue>
              <KeyValue label="Average departure">
                {minutesToClock(data.average_departure_minutes)}
              </KeyValue>
              <KeyValue label="Working days counted">{data.working_days}</KeyValue>
            </div>
            <p className="tiny" style={{ marginTop: 'var(--sp-3)' }}>
              <TrendingUp size={12} style={{ verticalAlign: '-1px' }} /> Figures are computed by the
              server from your verified punches only.
            </p>
          </>
        )}
      </Card>

      <Card>
        <CardTitle>Workspace &amp; privacy</CardTitle>
        <KeyValue label="Workspace">{workspace?.name}</KeyValue>
        <KeyValue label="Geofence radius">{metres(workspace?.radius_meters)}</KeyValue>
        <KeyValue label="Accuracy limit">{metres(workspace?.accuracy_threshold_meters)}</KeyValue>
        <KeyValue label="Timezone">{workspace?.timezone}</KeyValue>
        <p className="tiny" style={{ marginTop: 'var(--sp-3)', lineHeight: 1.5 }}>
          <MapPin size={12} style={{ verticalAlign: '-1px' }} /> Your location is captured only at
          the moment you punch in or out. There is no background or continuous tracking, and the
          live timer is calculated from timestamps, not from your position.
        </p>
      </Card>

      <Button
        variant="outline"
        block
        icon={KeyRound}
        onClick={() => navigate('/change-password')}
      >
        Change password
      </Button>

      <Button variant="outline" block icon={LogOut} onClick={handleSignOut}>
        Sign out
      </Button>
    </>
  );
}
