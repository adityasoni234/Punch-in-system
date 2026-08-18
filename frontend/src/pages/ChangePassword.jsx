import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound } from 'lucide-react';
import { Button, Field, Input, Notice } from '../components/common/index.jsx';
import { changePassword } from '../services/authService.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';

const MIN_LENGTH = 10;

export default function ChangePassword() {
  const { signIn, user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    if (next.length < MIN_LENGTH) {
      setError(`Your new password must be at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (next !== confirm) {
      setError('The two new passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      await changePassword(current, next);
      // Changing the password revokes every session, so sign in again silently.
      await signIn(user.email, next);
      toast.success('Password updated.');
      navigate('/', { replace: true });
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <div className="stack stack--tight">
        <div className="auth__mark">
          <KeyRound size={26} />
        </div>
        <h1 className="auth__title">Set a new password</h1>
        <p className="muted">
          Your account is using a temporary password. Choose your own before continuing.
        </p>
      </div>

      {error && <Notice variant="error" title="Could not update">{error}</Notice>}

      <form className="stack" onSubmit={onSubmit} noValidate>
        <Field label="Current password" htmlFor="current">
          <Input
            id="current"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </Field>
        <Field label="New password" hint={`At least ${MIN_LENGTH} characters.`} htmlFor="next">
          <Input
            id="next"
            type="password"
            autoComplete="new-password"
            required
            value={next}
            onChange={(event) => setNext(event.target.value)}
          />
        </Field>
        <Field label="Confirm new password" htmlFor="confirm">
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </Field>
        <Button type="submit" variant="primary" block loading={busy}>
          Update password
        </Button>
      </form>
    </div>
  );
}
