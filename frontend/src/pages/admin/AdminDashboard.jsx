import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, Users } from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  SegmentedControl,
  SkeletonCard,
  StatTile,
} from '../../components/common/index.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useLiveTimer } from '../../hooks/useLiveTimer.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { getDashboard } from '../../services/adminService.js';
import { formatDuration, formatTime } from '../../utils/time.js';
import { initials, teamLabel, teamShort } from '../../utils/format.js';

const TABS = [
  { value: 'present', label: 'Present' },
  { value: 'absent', label: 'Absent' },
  { value: 'checked_out', label: 'Out' },
];

/**
 * One line of the branch breakdown.
 *
 * The bar is present-over-total, so an executive turnout of 2/3 reads
 * differently from a member turnout of 2/40 at a glance.
 */
function TeamRow({ row }) {
  const share = row.total > 0 ? Math.round((row.present / row.total) * 100) : 0;
  return (
    <div>
      <div className="row row--between" style={{ marginBottom: 4 }}>
        <span style={{ fontWeight: 620, fontSize: 14 }}>{teamLabel(row.team)}</span>
        <span className="mono" style={{ fontSize: 13, fontWeight: 640 }}>
          <span style={{ color: 'var(--green-600)' }}>{row.present}</span>
          <span style={{ color: 'var(--text-muted)' }}> / {row.total} present</span>
        </span>
      </div>
      <div
        style={{
          height: 6,
          borderRadius: 999,
          background: 'var(--slate-100)',
          overflow: 'hidden',
        }}
        role="img"
        aria-label={`${row.present} of ${row.total} ${teamLabel(row.team)} present`}
      >
        <div
          style={{
            width: `${share}%`,
            height: '100%',
            borderRadius: 999,
            background: 'var(--green-600)',
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      <div className="tiny" style={{ marginTop: 3 }}>
        {row.absent} absent · {row.checked_out} checked out
      </div>
    </div>
  );
}

function PresentRow({ entry, timezone }) {
  // Ticks locally from the server-issued punch-in time; no polling required.
  const seconds = useLiveTimer(entry.punch_in, true);
  return (
    <Link to={`/admin/users/${entry.user_id}`} className="list-row" style={{ color: 'inherit' }}>
      <div className="avatar">{initials(entry.name)}</div>
      <div className="list-row__main">
        <div className="list-row__name">{entry.name}</div>
        <div className="list-row__meta">
          {teamShort(entry.team)} · IN {formatTime(entry.punch_in, timezone)} ·{' '}
          {entry.member_id}
          {entry.is_late ? ' · late' : ''}
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <Badge variant="present" dot>
          PRESENT
        </Badge>
        <div className="mono" style={{ fontSize: 13, marginTop: 4, fontWeight: 640 }}>
          {formatDuration(seconds)}
        </div>
      </div>
    </Link>
  );
}

function SimpleRow({ entry, variant, timezone }) {
  return (
    <Link to={`/admin/users/${entry.user_id}`} className="list-row" style={{ color: 'inherit' }}>
      <div className={`avatar${variant === 'absent' ? ' avatar--muted' : ''}`}>
        {initials(entry.name)}
      </div>
      <div className="list-row__main">
        <div className="list-row__name">{entry.name}</div>
        <div className="list-row__meta">
          {teamShort(entry.team)} ·{' '}
          {variant === 'checked-out'
            ? `${formatTime(entry.punch_in, timezone)} → ${formatTime(
                entry.last_punch_out,
                timezone,
              )}`
            : entry.member_id}
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <Badge variant={variant} dot>
          {variant === 'absent' ? 'ABSENT' : 'CHECKED OUT'}
        </Badge>
        {variant === 'checked-out' && (
          <div className="mono" style={{ fontSize: 13, marginTop: 4, fontWeight: 640 }}>
            {formatDuration(entry.total_seconds)}
          </div>
        )}
      </div>
    </Link>
  );
}

export default function AdminDashboard() {
  const { timezone } = useAuth();
  const [tab, setTab] = useState('present');
  const { data, error, loading, reload } = useAsync(() => getDashboard(), []);

  // Presence changes on its own as people punch, so poll gently while visible.
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') reload({ quiet: true });
    }, 30000);
    return () => window.clearInterval(id);
  }, [reload]);

  if (loading && !data) return <SkeletonCard lines={5} />;
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return null;

  const lists = {
    present: data.present,
    absent: data.absent,
    checked_out: data.checked_out,
  };
  const current = lists[tab];

  return (
    <>
      <div className="row row--between">
        <div>
          <div className="greeting" style={{ fontSize: 20 }}>
            Who is in
          </div>
          <div className="tiny">
            {data.date} · {data.timezone}
          </div>
        </div>
        <Button size="sm" variant="ghost" icon={RefreshCw} onClick={() => reload()}>
          Refresh
        </Button>
      </div>

      <div className="grid-4">
        <StatTile label="Total users" value={data.total_users} />
        <StatTile label="Present" value={data.present_count} tone="present" />
        <StatTile label="Absent" value={data.absent_count} tone="absent" />
        <StatTile label="Checked out" value={data.checked_out_count} tone="checked" />
      </div>

      <Card>
        <CardTitle>By team</CardTitle>
        <div className="stack stack--tight">
          {data.breakdown.map((row) => (
            <TeamRow key={row.team} row={row} />
          ))}
        </div>
      </Card>

      <SegmentedControl
        options={TABS.map((t) => ({
          ...t,
          label: `${t.label} (${lists[t.value].length})`,
        }))}
        value={tab}
        onChange={setTab}
        ariaLabel="Presence filter"
      />

      <Card flush>
        {current.length === 0 ? (
          <EmptyState
            icon={Users}
            title={
              tab === 'present'
                ? 'Nobody is present'
                : tab === 'absent'
                  ? 'Nobody is absent'
                  : 'Nobody has checked out'
            }
          >
            {data.total_users === 0
              ? 'No users have been created yet.'
              : 'This list updates as people punch in and out.'}
          </EmptyState>
        ) : (
          current.map((entry) =>
            tab === 'present' ? (
              <PresentRow key={entry.user_id} entry={entry} timezone={timezone} />
            ) : (
              <SimpleRow
                key={entry.user_id}
                entry={entry}
                variant={tab === 'absent' ? 'absent' : 'checked-out'}
                timezone={timezone}
              />
            ),
          )
        )}
      </Card>
    </>
  );
}
