import { NavLink } from 'react-router-dom';
import { WifiOff } from 'lucide-react';
import { useOnlineStatus } from '../../hooks/useOnlineStatus.js';

export function AppHeader({ title, subtitle, action }) {
  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div style={{ minWidth: 0 }}>
          <div className="app-header__title">{title}</div>
          {subtitle && <div className="app-header__sub">{subtitle}</div>}
        </div>
        {action}
      </div>
    </header>
  );
}

export function BottomNav({ items }) {
  return (
    <nav className="bottom-nav" aria-label="Primary">
      <div className="bottom-nav__inner">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `bottom-nav__item${isActive ? ' bottom-nav__item--active' : ''}`
            }
          >
            <Icon size={21} strokeWidth={2.1} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export function OfflineBanner() {
  const online = useOnlineStatus();
  if (online) return null;
  return (
    <div className="offline-banner" role="status">
      <WifiOff size={14} style={{ verticalAlign: '-2px', marginRight: 6 }} />
      Offline — punching is unavailable until you reconnect
    </div>
  );
}

export function MobileShell({ header, nav, children }) {
  return (
    <div className="shell">
      <OfflineBanner />
      {header}
      <main className="shell__body">{children}</main>
      {nav}
    </div>
  );
}
