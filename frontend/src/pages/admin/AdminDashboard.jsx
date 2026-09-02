import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, Users, X } from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  SkeletonCard,
} from '../../components/common/index.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useLiveTimer } from '../../hooks/useLiveTimer.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { getDashboard } from '../../services/adminService.js';
import { formatDuration, formatTime } from '../../utils/time.js';
import { initials, TEAMS, teamLabel, teamShort } from '../../utils/format.js';

const STATUSES = [
  { value: 'all', label: 'Everyone', badge: 'default' },
  { value: 'present', label: 'Present', badge: 'present' },
  { value: 'absent', label: 'Absent', badge: 'absent' },
  { value: 'checked_out', label: 'Checked out', badge: 'checked-out' },
];

function statusLabel(value) {
  return STATUSES.find((s) => s.value === value)?.label ?? 'Everyone';
}

/** A stat tile that is also a filter. */
function FilterTile({ label, value, tone, active, onClick }) {
  return (
    <button
      type="button"
      className={`stat stat--button${tone ? ` stat--${tone}` : ''}${
        active ? ' stat--active' : ''
      }`}
      onClick={onClick}
      aria-pressed={active}
    >
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
    </button>
  );
}

/**
 * One line of the branch breakdown, and a filter for that team.
 *
 * The bar is present-over-total, so a 9/12 executive turnout reads differently
 * from 7/9 members at a glance.
 */
function TeamRow({ row, active, onClick }) {
  const share = row.total > 0 ? Math.round((row.present / row.total) * 100) : 0;
  return (
    <button
      type="button"
      className={`team-row${active ? ' team-row--active' : ''}`}
      onClick={onClick}
      aria-pressed={active}
    >
      <div className="row row--between" style={{ marginBottom: 4 }}>
        <span style={{ fontWeight: 620, fontSize: 14 }}>{teamLabel(row.team)}</span>
        <span className="mono" style={{ fontSize: 13, fontWeight: 640 }}>
          <span style={{ color: 'var(--green-600)' }}>{row.present}</span>
          <span style={{ color: 'var(--text-muted)' }}> / {row.total} present</span>
        </span>
      </div>
      <div
        className="team-row__bar"
        role="img"
        aria-label={`${row.present} of ${row.total} ${teamLabel(row.team)} present`}
      >
        <div className="team-row__fill" style={{ width: `${share}%` }} />
      </div>
      <div className="tiny" style={{ marginTop: 3, textAlign: 'left' }}>
        {row.absent} absent · {row.checked_out} checked out
      </div>
    </button>
  );
}

function PersonRow({ entry, timezone }) {
  const active = entry.state === 'PRESENT';
  // Ticks locally from the server-issued punch-in time; no polling required.
  const seconds = useLiveTimer(entry.punch_in, active);
  const badge =
    entry.state === 'PRESENT'
      ? { variant: 'present', text: 'PRESENT' }
      : entry.state === 'CHECKED_OUT'
        ? { variant: 'checked-out', text: 'CHECKED OUT' }
        : { variant: 'absent', text: 'ABSENT' };

  let meta = `${teamShort(entry.team)} · ${entry.member_id}`;
  if (entry.state === 'PRESENT') {
    meta = `${teamShort(entry.team)} · IN ${formatTime(entry.punch_in, timezone)} · ${
      entry.member_id
    }${entry.is_late ? ' · late' : ''}`;
  } else if (entry.state === 'CHECKED_OUT') {
    meta = `${teamShort(entry.team)} · ${formatTime(entry.punch_in, timezone)} → ${formatTime(
      entry.last_punch_out,
      timezone,
    )}`;
  }

  return (
    <Link to={`/admin/users/${entry.user_id}`} className="list-row" style={{ color: 'inherit' }}>
      <div className={`avatar${entry.state === 'ABSENT' ? ' avatar--muted' : ''}`}>
        {initials(entry.name)}
      </div>
      <div className="list-row__main">
        <div className="list-row__name">{entry.name}</div>
        <div className="list-row__meta">{meta}</div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <Badge variant={badge.variant} dot>
          {badge.text}
        </Badge>
        {entry.state !== 'ABSENT' && (
          <div className="mono" style={{ fontSize: 13, marginTop: 4, fontWeight: 640 }}>
            {formatDuration(active ? seconds : entry.total_seconds)}
          </div>
        )}
      </div>
    </Link>
  );
}

export default function AdminDashboard() {
  const { timezone } = useAuth();
  const [status, setStatus] = useState('present');
  const [team, setTeam] = useState('');
  const { data, error, loading, reload } = useAsync(() => getDashboard(), []);

  // Presence changes on its own as people punch, so poll gently while visible.
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') reload({ quiet: true });
    }, 30000);
    return () => window.clearInterval(id);
  }, [reload]);

  // Every entry in one list, tagged with its status, so filtering is a single
  // pass rather than three parallel code paths.
  const everyone = useMemo(() => {
    if (!data) return [];
    return [...data.present, ...data.absent, ...data.checked_out];
  }, [data]);

  const visible = useMemo(() => {
    return everyone.filter((entry) => {
      if (team && entry.team !== team) return false;
      if (status === 'present') return entry.state === 'PRESENT';
      if (status === 'absent') return entry.state === 'ABSENT';
      if (status === 'checked_out') return entry.state === 'CHECKED_OUT';
      return true;
    });
  }, [everyone, status, team]);

  if (loading && !data) return <SkeletonCard lines={5} />;
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return null;

  const teamPresent = (value) =>
    data.breakdown.find((row) => row.team === value)?.present ?? 0;

  const filtered = status !== 'all' || team !== '';

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
        <FilterTile
          label="Total users"
          value={data.total_users}
          active={status === 'all' && !team}
          onClick={() => {
            setStatus('all');
            setTeam('');
          }}
        />
        <FilterTile
          label="Present"
          value={data.present_count}
          tone="present"
          active={status === 'present' && !team}
          onClick={() => {
            setStatus('present');
            setTeam('');
          }}
        />
        <FilterTile
          label="Absent"
          value={data.absent_count}
          tone="absent"
          active={status === 'absent' && !team}
          onClick={() => {
            setStatus('absent');
            setTeam('');
          }}
        />
        <FilterTile
          label="Checked out"
          value={data.checked_out_count}
          tone="checked"
          active={status === 'checked_out' && !team}
          onClick={() => {
            setStatus('checked_out');
            setTeam('');
          }}
        />
      </div>

      <Card>
        <CardTitle>Present by team</CardTitle>
        <div className="grid-4">
          {TEAMS.map((t) => (
            <FilterTile
              key={t.value}
              label={`${t.short} present`}
              value={teamPresent(t.value)}
              tone="present"
              active={status === 'present' && team === t.value}
              onClick={() => {
                setStatus('present');
                setTeam(t.value);
              }}
            />
          ))}
        </div>
      </Card>

      <Card>
        <CardTitle>By team</CardTitle>
        <div className="stack stack--tight">
          {data.breakdown.map((row) => (
            <TeamRow
              key={row.team}
              row={row}
              active={team === row.team}
              onClick={() => setTeam(team === row.team ? '' : row.team)}
            />
          ))}
        </div>
        <p className="tiny" style={{ marginTop: 'var(--sp-3)', marginBottom: 0 }}>
          Tap a team to filter the list below. Tap again to clear.
        </p>
      </Card>

      <div className="segmented">
        {STATUSES.map((s) => (
          <button
            key={s.value}
            type="button"
            className={`segmented__item${status === s.value ? ' segmented__item--active' : ''}`}
            onClick={() => setStatus(s.value)}
          >
            {s.label}
          </button>
        ))}
      </div>

      <Card flush>
        <div className="day-card__head">
          <div>
            <div className="day-card__date">
              {team ? teamLabel(team) : 'Everyone'} · {statusLabel(status)}
            </div>
            <div className="tiny">
              {visible.length} {visible.length === 1 ? 'person' : 'people'}
            </div>
          </div>
          {filtered && (
            <Button
              size="sm"
              variant="ghost"
              icon={X}
              onClick={() => {
                setStatus('all');
                setTeam('');
              }}
            >
              Clear
            </Button>
          )}
        </div>
        {visible.length === 0 ? (
          <EmptyState icon={Users} title="Nobody matches this filter">
            {data.total_users === 0
              ? 'No users have been created yet.'
              : 'Try a different team or status.'}
          </EmptyState>
        ) : (
          visible.map((entry) => (
            <PersonRow key={entry.user_id} entry={entry} timezone={timezone} />
          ))
        )}
      </Card>
    </>
  );
}
