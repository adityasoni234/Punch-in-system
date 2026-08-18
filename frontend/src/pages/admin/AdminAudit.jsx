import { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Select,
  SkeletonCard,
} from '../../components/common/index.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { getAuditLogs } from '../../services/adminService.js';
import { formatDateLong, formatTime } from '../../utils/time.js';

const ACTIONS = [
  '',
  'LOGIN_SUCCESS',
  'LOGIN_FAILED',
  'PUNCH_IN_SUCCESS',
  'PUNCH_IN_REJECTED',
  'PUNCH_OUT_SUCCESS',
  'PUNCH_OUT_REJECTED',
  'SUSPICIOUS_MOVEMENT',
  'SESSION_AUTO_CLOSED',
  'USER_CREATED',
  'USER_DISABLED',
  'USER_ENABLED',
  'USER_ROLE_CHANGED',
  'USER_PASSWORD_RESET',
  'WORKSPACE_UPDATED',
  'REPORT_EXPORTED',
  'TOKEN_REFRESH_REUSE',
];

function metaLine(entry) {
  const meta = entry.metadata || {};
  const bits = [];
  if (meta.distance_m !== undefined) bits.push(`${Math.round(meta.distance_m)} m away`);
  if (meta.accuracy_m !== undefined) bits.push(`±${Math.round(meta.accuracy_m)} m`);
  if (meta.reason) bits.push(meta.reason);
  if (meta.duration_seconds !== undefined) {
    bits.push(`${Math.round(meta.duration_seconds / 60)} min session`);
  }
  if (meta.implied_speed_kmh) bits.push(`${meta.implied_speed_kmh} km/h implied`);
  return bits.join(' · ');
}

export default function AdminAudit() {
  const { timezone } = useAuth();
  const [action, setAction] = useState('');
  const { data, error, loading, reload } = useAsync(
    () => getAuditLogs(action ? { action } : {}),
    [action],
  );

  return (
    <>
      <div className="greeting" style={{ fontSize: 20 }}>
        Audit log
      </div>

      <Card>
        <Field label="Filter by action">
          <Select value={action} onChange={(event) => setAction(event.target.value)}>
            {ACTIONS.map((value) => (
              <option key={value || 'all'} value={value}>
                {value || 'All actions'}
              </option>
            ))}
          </Select>
        </Field>
      </Card>

      {loading && !data && <SkeletonCard lines={5} />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {data && (
        <Card flush>
          {data.items.length === 0 ? (
            <EmptyState icon={ShieldCheck} title="No audit entries">
              Security and attendance events appear here as they happen.
            </EmptyState>
          ) : (
            data.items.map((entry) => (
              <div key={entry.id} className="list-row">
                <div className="list-row__main">
                  <div className="list-row__name" style={{ fontSize: 14 }}>
                    {entry.action}
                  </div>
                  <div className="list-row__meta">
                    {entry.actor_name || 'System'}
                    {entry.target_name && entry.target_name !== entry.actor_name
                      ? ` → ${entry.target_name}`
                      : ''}
                    {entry.ip_address ? ` · ${entry.ip_address}` : ''}
                  </div>
                  {metaLine(entry) && <div className="tiny">{metaLine(entry)}</div>}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <Badge variant={entry.result === 'SUCCESS' ? 'present' : 'absent'}>
                    {entry.result}
                  </Badge>
                  <div className="tiny" style={{ marginTop: 4 }}>
                    {formatTime(entry.timestamp, timezone)}
                  </div>
                  <div className="tiny">
                    {formatDateLong(new Date(entry.timestamp), timezone)}
                  </div>
                </div>
              </div>
            ))
          )}
        </Card>
      )}
    </>
  );
}
