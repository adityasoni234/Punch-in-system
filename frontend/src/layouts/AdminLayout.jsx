import { Outlet, useNavigate } from 'react-router-dom';
import { CalendarRange, LayoutDashboard, Settings, ShieldCheck, Users } from 'lucide-react';
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
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <MobileShell
      header={
        <AppHeader
          title="Admin"
          subtitle={user?.name}
          action={
            <button
              className="icon-button"
              onClick={() => navigate('/')}
              aria-label="Switch to my attendance"
            >
              <LayoutDashboard size={19} />
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
