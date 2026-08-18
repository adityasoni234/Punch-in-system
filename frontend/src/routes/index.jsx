import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import AppLayout from '../layouts/AppLayout.jsx';
import AdminLayout from '../layouts/AdminLayout.jsx';
import Login from '../pages/Login.jsx';
import ChangePassword from '../pages/ChangePassword.jsx';
import Dashboard from '../pages/Dashboard.jsx';
import History from '../pages/History.jsx';
import Profile from '../pages/Profile.jsx';
import AdminDashboard from '../pages/admin/AdminDashboard.jsx';
import AdminUsers from '../pages/admin/AdminUsers.jsx';
import AdminUserDetail from '../pages/admin/AdminUserDetail.jsx';
import AdminAttendance from '../pages/admin/AdminAttendance.jsx';
import AdminSettings from '../pages/admin/AdminSettings.jsx';
import AdminAudit from '../pages/admin/AdminAudit.jsx';

/**
 * Route guards are a usability affordance only. Every endpoint independently
 * re-checks authentication and role on the server, so bypassing these in
 * devtools gains nothing.
 */
function RequireAuth({ children }) {
  const { isAuthenticated, mustChangePassword, booting } = useAuth();
  const location = useLocation();

  if (booting) return <BootScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />;
  if (mustChangePassword && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />;
  }
  return children;
}

function RequireAdmin({ children }) {
  const { isAdmin, booting } = useAuth();
  if (booting) return <BootScreen />;
  if (!isAdmin) return <Navigate to="/" replace />;
  return children;
}

function RedirectIfAuthenticated({ children }) {
  const { isAuthenticated, booting, mustChangePassword } = useAuth();
  if (booting) return <BootScreen />;
  if (isAuthenticated) return <Navigate to={mustChangePassword ? '/change-password' : '/'} replace />;
  return children;
}

function BootScreen() {
  return (
    <div className="boot-splash">
      <div className="boot-splash__mark" />
      <p>Loading…</p>
    </div>
  );
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthenticated>
            <Login />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePassword />
          </RequireAuth>
        }
      />

      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="/history" element={<History />} />
        <Route path="/profile" element={<Profile />} />
      </Route>

      <Route
        path="/admin"
        element={
          <RequireAuth>
            <RequireAdmin>
              <AdminLayout />
            </RequireAdmin>
          </RequireAuth>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="attendance" element={<AdminAttendance />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="users/:userId" element={<AdminUserDetail />} />
        <Route path="audit" element={<AdminAudit />} />
        <Route path="settings" element={<AdminSettings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
