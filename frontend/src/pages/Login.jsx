import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Fingerprint } from 'lucide-react';
import { Button, Field, Input, Notice } from '../components/common/index.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { ApiError } from '../services/apiClient.js';

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError('Enter both your email and password.');
      return;
    }
    setBusy(true);
    try {
      const session = await signIn(email.trim(), password);
      navigate(session.user.must_change_password ? '/change-password' : '/', { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const fields = caught.details?.fields;
        setError(
          fields
            ? Object.values(fields).join(' ')
            : caught.message,
        );
      } else {
        setError('Could not sign in. Please try again.');
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

      {error && <Notice variant="error" title="Sign in failed">{error}</Notice>}

      <form className="stack" onSubmit={onSubmit} noValidate>
        <Field label="Email" htmlFor="email">
          <Input
            id="email"
            type="email"
            autoComplete="username"
            inputMode="email"
            autoCapitalize="none"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@company.com"
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

      <p className="tiny" style={{ textAlign: 'center' }}>
        Accounts are created by your administrator.
      </p>
    </div>
  );
}
