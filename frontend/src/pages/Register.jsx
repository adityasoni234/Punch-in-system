import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { UserPlus } from 'lucide-react';
import { Button, Field, Input, Notice } from '../components/common/index.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { ApiError } from '../services/apiClient.js';

const MIN_PASSWORD_LENGTH = 10;

export default function Register() {
  const { signUp } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '',
    email: '',
    memberId: '',
    password: '',
    confirm: '',
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  const onSubmit = async (event) => {
    event.preventDefault();
    setError(null);

    if (!form.name.trim() || !form.email.trim() || !form.memberId.trim()) {
      setError('Fill in your name, email and enrollment number.');
      return;
    }
    if (form.password.length < MIN_PASSWORD_LENGTH) {
      setError(`Your password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (form.password !== form.confirm) {
      setError('The two passwords do not match.');
      return;
    }

    setBusy(true);
    try {
      await signUp({
        name: form.name.trim(),
        email: form.email.trim(),
        memberId: form.memberId.trim(),
        password: form.password,
      });
      navigate('/', { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const fields = caught.details?.fields;
        setError(fields ? Object.values(fields).join(' ') : caught.message);
      } else {
        setError(caught?.message || 'Could not create your account.');
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <div className="stack stack--tight">
        <div className="auth__mark">
          <UserPlus size={26} />
        </div>
        <h1 className="auth__title">Create account</h1>
        <p className="muted">
          You will sign in with your enrollment number from now on.
        </p>
      </div>

      {error && (
        <Notice variant="error" title="Could not sign up">
          {error}
        </Notice>
      )}

      <form className="stack" onSubmit={onSubmit} noValidate>
        <Field label="Full name" htmlFor="name">
          <Input
            id="name"
            autoComplete="name"
            required
            value={form.name}
            onChange={set('name')}
            placeholder="Aditya Soni"
          />
        </Field>
        <Field label="Email" htmlFor="email">
          <Input
            id="email"
            type="email"
            inputMode="email"
            autoCapitalize="none"
            autoComplete="email"
            required
            value={form.email}
            onChange={set('email')}
            placeholder="you@example.com"
          />
        </Field>
        <Field
          label="Enrollment number"
          htmlFor="memberId"
          hint="This is what you will sign in with."
        >
          <Input
            id="memberId"
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck="false"
            required
            value={form.memberId}
            onChange={set('memberId')}
            placeholder="ENR2026001"
          />
        </Field>
        <Field
          label="Password"
          htmlFor="new-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        >
          <Input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            value={form.password}
            onChange={set('password')}
          />
        </Field>
        <Field label="Confirm password" htmlFor="confirm">
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            required
            value={form.confirm}
            onChange={set('confirm')}
          />
        </Field>
        <Button type="submit" variant="primary" block loading={busy}>
          Create account
        </Button>
      </form>

      <p className="tiny" style={{ textAlign: 'center' }}>
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </div>
  );
}
