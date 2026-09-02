import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Fingerprint } from 'lucide-react';
import {
  Button,
  Field,
  Input,
  Notice,
  SegmentedControl,
} from '../components/common/index.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { ApiError } from '../services/apiClient.js';

/**
 * One form, two modes.
 *
 * Members are issued an enrollment number and sign in with that;
 * administrators use their email. Both post the same `identifier` field, so
 * there is a single credential check, audit entry and rate limit behind it.
 */
const MODES = [
  { value: 'member', label: 'Member' },
  { value: 'admin', label: 'Admin' },
];

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState('member');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const isAdmin = mode === 'admin';

  const onSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    if (!identifier.trim() || !password) {
      setError(
        isAdmin
          ? 'Enter your email and password.'
          : 'Enter your enrollment number and password.',
      );
      return;
    }
    setBusy(true);
    try {
      const session = await signIn(identifier.trim(), password);
      navigate(session.user.must_change_password ? '/change-password' : '/', {
        replace: true,
      });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const fields = caught.details?.fields;
        setError(fields ? Object.values(fields).join(' ') : caught.message);
      } else {
        setError(caught?.message || 'Could not sign in. Please try again.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <div className="stack--tight stack">
        <div className="auth__mark">
          <Fingerprint size={28} />
        </div>
        <h1 className="auth__title">Sign in</h1>
        <p className="muted">Workspace attendance and time tracking.</p>
      </div>

      <SegmentedControl
        options={MODES}
        value={mode}
        onChange={(next) => {
          setMode(next);
          setIdentifier('');
          setError(null);
        }}
        ariaLabel="Sign in as"
      />

      {error && (
        <Notice variant="error" title="Sign in failed">
          {error}
        </Notice>
      )}

      <form className="stack" onSubmit={onSubmit} noValidate>
        <Field
          label={isAdmin ? 'Email' : 'Enrollment number'}
          htmlFor="identifier"
          hint={isAdmin ? undefined : 'The enrollment number you signed up with.'}
        >
          <Input
            id="identifier"
            key={mode}
            type={isAdmin ? 'email' : 'text'}
            inputMode={isAdmin ? 'email' : 'text'}
            autoComplete={isAdmin ? 'username' : 'off'}
            autoCapitalize={isAdmin ? 'none' : 'characters'}
            autoCorrect="off"
            spellCheck="false"
            required
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            placeholder={isAdmin ? 'you@company.com' : 'ENR2026001'}
          />
        </Field>
        <Field label="Password" htmlFor="password">
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
          />
        </Field>
        <Button type="submit" variant="primary" block loading={busy}>
          Sign in
        </Button>
      </form>

      {isAdmin ? (
        <p className="tiny" style={{ textAlign: 'center' }}>
          Administrator accounts are created by another administrator.
        </p>
      ) : (
        <p className="tiny" style={{ textAlign: 'center' }}>
          No account yet? <Link to="/register">Create one</Link>
        </p>
      )}
    </div>
  );
}
