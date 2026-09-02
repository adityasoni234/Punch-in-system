import { Outlet, useNavigate } from 'react-router-dom';
import { CalendarRange, LayoutDashboard, LogOut, Settings, ShieldCheck, Users } from 'lucide-react';
import { AppHeader, BottomNav, MobileShell } from '../components/layout/MobileShell.jsx';
import { useAuth } from '../context/AuthContext.jsx';

const NAV = [
  { to: '/admin', label: 'Presence', icon: LayoutDashboard, end: true },
  { to: '/admin/attendance', label: 'Attendance', icon: CalendarRange },
  { to: '/admin/users', label: 'Users', icon: Users },
  { to: '/admin/audit', label: 'Audit', icon: ShieldCheck },
  { to: '/admin/settings', label: 'Settings', icon: Settings },
];

export default function AdminLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate('/login', { replace: true });
  };

  return (
    <MobileShell
      header={
        <AppHeader
          title="Admin"
          subtitle={user?.name}
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
