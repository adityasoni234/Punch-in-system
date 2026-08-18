import { Outlet, useNavigate } from 'react-router-dom';
import { CalendarDays, Home, LogOut, User } from 'lucide-react';
import { AppHeader, BottomNav, MobileShell } from '../components/layout/MobileShell.jsx';
import { useAuth } from '../context/AuthContext.jsx';

const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/history', label: 'History', icon: CalendarDays },
  { to: '/profile', label: 'Profile', icon: User },
];

export default function AppLayout() {
  const { user, workspace, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <MobileShell
      header={
        <AppHeader
          title={workspace?.name || 'Punch In'}
          subtitle={user ? `${user.name} · ${user.member_id}` : undefined}
          action={
            <button className="icon-button" onClick={handleSignOut} aria-label="Sign out">
              <LogOut size={19} />
            </button>
          }
        />
      }
      nav={<BottomNav items={NAV} />}
    >
      <Outlet />
    </MobileShell>
  );
}
