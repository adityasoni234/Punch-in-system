import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { KeyRound, MapPin, ShieldOff, ShieldCheck } from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  CardTitle,
  EmptyState,
  ErrorState,
  Field,
  Input,
  KeyValue,
  Notice,
  SegmentedControl,
  Select,
  Sheet,
  SkeletonCard,
} from '../../components/common/index.jsx';
import { SessionList } from '../../components/attendance/PunchControls.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import {
  getPunchEvents,
  getUser,
  getUserAttendance,
  resetPassword,
  setUserStatus,
  updateUser,
} from '../../services/adminService.js';
import { formatDateLong, formatDuration, formatTime } from '../../utils/time.js';
import { initials, metres, TEAMS, teamLabel } from '../../utils/format.js';

const PERIODS = [
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
];

export default function AdminUserDetail() {
  const { userId } = useParams();
  const { timezone } = useAuth();
  const toast = useToast();
  const [period, setPeriod] = useState('week');
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [temporaryPassword, setTemporaryPassword] = useState(null);
  const [showEvents, setShowEvents] = useState(false);

  const user = useAsync(() => getUser(userId), [userId]);
  const attendance = useAsync(
    () => getUserAttendance(userId, { period }),
    [userId, period],
  );
  const events = useAsync(() => getPunchEvents({ userId }), [userId], { immediate: false });

  if (user.loading && !user.data) return <SkeletonCard lines={4} />;
  if (user.error) return <ErrorState error={user.error} onRetry={user.reload} />;
  const person = user.data;
  if (!person) return null;

  const toggleStatus = async () => {
    setBusy(true);
    try {
      await setUserStatus(person.id, person.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE');
      toast.success(person.status === 'ACTIVE' ? 'User disabled.' : 'User enabled.');
      user.reload({ quiet: true });
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(false);
    }
  };

  const doReset = async () => {
    setBusy(true);
    try {
      const result = await resetPassword(person.id);
      setTemporaryPassword(result.temporary_password);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(false);
    }
  };

  const saveEdits = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await updateUser(person.id, form);
      toast.success('User updated.');
      setEditing(false);
      user.reload({ quiet: true });
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Card>
        <div className="row">
          <div className={`avatar${person.status === 'DISABLED' ? ' avatar--muted' : ''}`}
               style={{ width: 52, height: 52, fontSize: 18 }}>
            {initials(person.name)}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 680, fontSize: 17 }}>{person.name}</div>
            <div className="tiny">{person.email}</div>
          </div>
          <div style={{ display: 'grid', gap: 4, justifyItems: 'end' }}>
            <Badge variant={person.role === 'ADMIN' ? 'info' : 'default'}>{person.role}</Badge>
            <Badge>{teamLabel(person.team)}</Badge>
            <Badge variant={person.status === 'ACTIVE' ? 'present' : 'absent'}>
              {person.status}
            </Badge>
          </div>
        </div>
        <div style={{ marginTop: 'var(--sp-3)' }}>
          <KeyValue label="Enrollment number">{person.member_id}</KeyValue>
          <KeyValue label="Team">{teamLabel(person.team)}</KeyValue>
          <KeyValue label="Last sign in">
            {person.last_login_at ? formatTime(person.last_login_at, timezone) : 'Never'}
          </KeyValue>
          <KeyValue label="Must change password">
            {person.must_change_password ? 'Yes' : 'No'}
          </KeyValue>
        </div>
        <div className="grid-2" style={{ marginTop: 'var(--sp-4)' }}>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setForm({
                name: person.name,
                email: person.email,
                member_id: person.member_id,
                role: person.role,
                team: person.team,
              });
              setEditing(true);
            }}
          >
            Edit
          </Button>
          <Button size="sm" variant="outline" icon={KeyRound} onClick={doReset} loading={busy}>
            Reset password
          </Button>
        </div>
        <div style={{ marginTop: 'var(--sp-3)' }}>
          <Button
            size="sm"
            block
            variant={person.status === 'ACTIVE' ? 'danger' : 'outline'}
            icon={person.status === 'ACTIVE' ? ShieldOff : ShieldCheck}
            onClick={toggleStatus}
            loading={busy}
          >
            {person.status === 'ACTIVE' ? 'Disable user' : 'Enable user'}
          </Button>
        </div>
      </Card>

      <SegmentedControl
        options={PERIODS}
        value={period}
        onChange={setPeriod}
        ariaLabel="Attendance period"
      />

      {attendance.loading && !attendance.data && <SkeletonCard lines={3} />}
      {attendance.error && (
        <ErrorState error={attendance.error} onRetry={attendance.reload} />
      )}
      {attendance.data && (
        <>
          <Card>
            <CardTitle>Total in range</CardTitle>
            <div className="value-lg mono">{formatDuration(attendance.data.total_seconds)}</div>
          </Card>
          {attendance.data.days.length === 0 ? (
            <Card>
              <EmptyState title="No attendance in this range" />
            </Card>
          ) : (
            attendance.data.days.map((day) => (
              <Card key={day.date} flush>
                <div className="day-card__head">
                  <div>
                    <div className="day-card__date">{formatDateLong(day.date, timezone)}</div>
                    <div className="tiny">
                      {day.status}
                      {day.is_late ? ' · late' : ''}
                    </div>
                  </div>
                  <div className="day-card__total">{formatDuration(day.total_seconds)}</div>
                </div>
                <SessionList sessions={day.sessions} timezone={timezone} />
              </Card>
            ))
          )}
        </>
      )}

      <Button
        variant="outline"
        block
        icon={MapPin}
        onClick={() => {
          setShowEvents(true);
          events.reload();
        }}
      >
        View punch verification records
      </Button>

      <Sheet open={editing} onClose={() => setEditing(false)} title="Edit user">
        {form && (
          <form className="stack" onSubmit={saveEdits}>
            <Field label="Name">
              <Input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <Field label="Email">
              <Input
                type="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
              />
            </Field>
            <Field label="Member ID">
              <Input
                value={form.member_id}
                onChange={(event) => setForm({ ...form, member_id: event.target.value })}
              />
            </Field>
            <Field label="Team">
              <Select
                value={form.team}
                onChange={(event) => setForm({ ...form, team: event.target.value })}
              >
                {TEAMS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Role">
              <Select
                value={form.role}
                onChange={(event) => setForm({ ...form, role: event.target.value })}
              >
                <option value="USER">User</option>
                <option value="ADMIN">Admin</option>
              </Select>
            </Field>
            <Button type="submit" variant="primary" block loading={busy}>
              Save changes
            </Button>
          </form>
        )}
      </Sheet>

      <Sheet
        open={Boolean(temporaryPassword)}
        onClose={() => setTemporaryPassword(null)}
        title="Temporary password"
      >
        <div className="stack">
          <Notice variant="warn" title="Shown once only">
            Every existing session for this user has been signed out and they must set a new
            password at next sign-in.
          </Notice>
          <div
            className="mono"
            style={{
              fontSize: 20,
              fontWeight: 700,
              textAlign: 'center',
              padding: 'var(--sp-4)',
              background: 'var(--slate-100)',
              borderRadius: 'var(--radius-sm)',
              userSelect: 'all',
            }}
          >
            {temporaryPassword}
          </div>
          <Button variant="primary" block onClick={() => setTemporaryPassword(null)}>
            Done
          </Button>
        </div>
      </Sheet>

      <Sheet open={showEvents} onClose={() => setShowEvents(false)} title="Punch verification">
        {events.loading && <SkeletonCard lines={3} />}
        {events.error && <ErrorState error={events.error} onRetry={events.reload} />}
        {events.data &&
          (events.data.items.length === 0 ? (
            <EmptyState title="No punch attempts recorded" />
          ) : (
            <div className="stack stack--tight">
              {events.data.items.map((event) => (
                <div
                  key={event.id}
                  style={{
                    padding: 'var(--sp-3)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  <div className="row row--between">
                    <strong style={{ fontSize: 14 }}>
                      {event.type === 'IN' ? 'Punch in' : 'Punch out'}
                    </strong>
                    <Badge variant={event.validation_status === 'ACCEPTED' ? 'present' : 'absent'}>
                      {event.validation_status}
                    </Badge>
                  </div>
                  <div className="tiny" style={{ marginTop: 4 }}>
                    {formatTime(event.server_timestamp, timezone)} ·{' '}
                    {formatDateLong(new Date(event.server_timestamp), timezone)}
                  </div>
                  <div className="tiny">
                    Distance {metres(event.distance_meters)} / allowed{' '}
                    {metres(event.radius_snapshot)} · accuracy {metres(event.accuracy_meters)} /
                    limit {metres(event.accuracy_threshold_snapshot)}
                  </div>
                  {event.rejection_reason && (
                    <div className="tiny" style={{ color: 'var(--red-600)' }}>
                      Reason: {event.rejection_reason}
                    </div>
                  )}
                  {event.location_purged && (
                    <div className="tiny">Coordinates purged by the retention policy.</div>
                  )}
                </div>
              ))}
            </div>
          ))}
      </Sheet>
    </>
  );
}
