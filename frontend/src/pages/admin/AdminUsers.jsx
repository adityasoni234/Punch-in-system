import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Copy, UserPlus, Users } from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Notice,
  SegmentedControl,
  Select,
  Sheet,
  SkeletonCard,
} from '../../components/common/index.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useToast } from '../../context/ToastContext.jsx';
import { createUser, listUsers } from '../../services/adminService.js';
import { initials, TEAMS, teamShort } from '../../utils/format.js';

const EMPTY_FORM = { name: '', email: '', member_id: '', role: 'USER', team: 'MEMBER' };

export default function AdminUsers() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [team, setTeam] = useState('');
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(null);

  const { data, error, loading, reload } = useAsync(
    () => listUsers({ search, team: team || undefined }),
    [search, team],
  );

  const submit = async (event) => {
    event.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      const result = await createUser({
        name: form.name.trim(),
        email: form.email.trim(),
        member_id: form.member_id.trim(),
        role: form.role,
        team: form.team,
      });
      setCreated(result);
      setCreating(false);
      setForm(EMPTY_FORM);
      reload({ quiet: true });
    } catch (caught) {
      setFormError(caught.message);
    } finally {
      setBusy(false);
    }
  };

  const copyPassword = async () => {
    try {
      await navigator.clipboard.writeText(created.temporary_password);
      toast.success('Temporary password copied.');
    } catch {
      toast.error('Could not copy. Select the password and copy it manually.');
    }
  };

  return (
    <>
      <div className="row row--between">
        <div className="greeting" style={{ fontSize: 20 }}>
          Users
        </div>
        <Button size="sm" variant="primary" icon={UserPlus} onClick={() => setCreating(true)}>
          New
        </Button>
      </div>

      <Input
        placeholder="Search by name, email or enrollment number"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        aria-label="Search users"
      />

      <SegmentedControl
        options={[{ value: '', label: 'All' }, ...TEAMS.map((t) => ({ value: t.value, label: t.short }))]}
        value={team}
        onChange={setTeam}
        ariaLabel="Filter by team"
      />

      {loading && !data && <SkeletonCard lines={4} />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {data && (
        <Card flush>
          {data.items.length === 0 ? (
            <EmptyState icon={Users} title="No users found">
              {search ? 'Try a different search.' : 'Create the first user to get started.'}
            </EmptyState>
          ) : (
            data.items.map((user) => (
              <Link
                key={user.id}
                to={`/admin/users/${user.id}`}
                className="list-row"
                style={{ color: 'inherit' }}
              >
                <div className={`avatar${user.status === 'DISABLED' ? ' avatar--muted' : ''}`}>
                  {initials(user.name)}
                </div>
                <div className="list-row__main">
                  <div className="list-row__name">{user.name}</div>
                  <div className="list-row__meta">
                    {teamShort(user.team)} · {user.member_id}
                  </div>
                </div>
                <div style={{ display: 'grid', gap: 4, justifyItems: 'end' }}>
                  {user.role === 'ADMIN' && <Badge variant="info">ADMIN</Badge>}
                  {user.status === 'DISABLED' && <Badge variant="absent">DISABLED</Badge>}
                </div>
              </Link>
            ))
          )}
        </Card>
      )}

      <Sheet open={creating} onClose={() => setCreating(false)} title="Create user">
        <form className="stack" onSubmit={submit}>
          {formError && <Notice variant="error">{formError}</Notice>}
          <Field label="Full name" htmlFor="name">
            <Input
              id="name"
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Field>
          <Field label="Email" htmlFor="new-email">
            <Input
              id="new-email"
              type="email"
              required
              autoCapitalize="none"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </Field>
          <Field label="Member ID" htmlFor="member">
            <Input
              id="member"
              required
              value={form.member_id}
              onChange={(event) => setForm({ ...form, member_id: event.target.value })}
            />
          </Field>
          <Field
            label="Team"
            htmlFor="team"
            hint="Where they sit in the branch. Drives the dashboard breakdown."
          >
            <Select
              id="team"
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
          <Field
            label="Role"
            htmlFor="role"
            hint="Admins oversee attendance and cannot punch in."
          >
            <Select
              id="role"
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value })}
            >
              <option value="USER">User</option>
              <option value="ADMIN">Admin</option>
            </Select>
          </Field>
          <Button type="submit" variant="primary" block loading={busy}>
            Create user
          </Button>
        </form>
      </Sheet>

      <Sheet open={Boolean(created)} onClose={() => setCreated(null)} title="User created">
        {created && (
          <div className="stack">
            <Notice variant="warn" title="Shown once only">
              Give this temporary password to {created.user.name}. It cannot be retrieved later —
              you would have to reset it.
            </Notice>
            <div
              className="mono"
              style={{
                fontSize: 20,
                fontWeight: 700,
                letterSpacing: '0.06em',
                textAlign: 'center',
                padding: 'var(--sp-4)',
                background: 'var(--slate-100)',
                borderRadius: 'var(--radius-sm)',
                userSelect: 'all',
              }}
            >
              {created.temporary_password}
            </div>
            <Button variant="outline" block icon={Copy} onClick={copyPassword}>
              Copy password
            </Button>
            <Button variant="primary" block onClick={() => setCreated(null)}>
              Done
            </Button>
          </div>
        )}
      </Sheet>
    </>
  );
}
