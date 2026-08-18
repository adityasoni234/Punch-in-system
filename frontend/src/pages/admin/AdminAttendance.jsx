import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarX2, Download } from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  SkeletonCard,
} from '../../components/common/index.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { useToast } from '../../context/ToastContext.jsx';
import { downloadAttendanceCsv, getAttendance } from '../../services/adminService.js';
import { formatDateLong, formatDuration, formatTime, shiftDays, todayIso } from '../../utils/time.js';
import { statusModifier } from '../../utils/format.js';

export default function AdminAttendance() {
  const { timezone } = useAuth();
  const toast = useToast();
  const today = useMemo(() => todayIso(timezone), [timezone]);
  const [fromDate, setFromDate] = useState(() => shiftDays(today, -6));
  const [toDate, setToDate] = useState(today);
  const [exporting, setExporting] = useState(false);

  const { data, error, loading, reload } = useAsync(
    () => getAttendance({ fromDate, toDate }),
    [fromDate, toDate],
  );

  const exportCsv = async () => {
    setExporting(true);
    try {
      await downloadAttendanceCsv({ fromDate, toDate });
      toast.success('Report downloaded.');
    } catch (caught) {
      toast.error(caught.message);
    } finally {
      setExporting(false);
    }
  };

  const total = (data || []).reduce((sum, row) => sum + row.total_seconds, 0);

  return (
    <>
      <div className="greeting" style={{ fontSize: 20 }}>
        Attendance
      </div>

      <Card>
        <div className="grid-2">
          <Field label="From" htmlFor="from">
            <Input
              id="from"
              type="date"
              value={fromDate}
              max={toDate}
              onChange={(event) => setFromDate(event.target.value)}
            />
          </Field>
          <Field label="To" htmlFor="to">
            <Input
              id="to"
              type="date"
              value={toDate}
              min={fromDate}
              onChange={(event) => setToDate(event.target.value)}
            />
          </Field>
        </div>
        <div style={{ marginTop: 'var(--sp-3)' }}>
          <Button
            block
            variant="outline"
            icon={Download}
            onClick={exportCsv}
            loading={exporting}
          >
            Export CSV
          </Button>
        </div>
      </Card>

      {loading && !data && <SkeletonCard lines={4} />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {data && (
        <>
          <Card>
            <div className="row row--between">
              <span className="muted">{data.length} day records</span>
              <span className="value-md">{formatDuration(total)}</span>
            </div>
          </Card>

          <Card flush>
            {data.length === 0 ? (
              <EmptyState icon={CalendarX2} title="No attendance in this range">
                Records appear here once people punch in.
              </EmptyState>
            ) : (
              data.map((row) => (
                <Link
                  key={`${row.user_id}-${row.date}`}
                  to={`/admin/users/${row.user_id}`}
                  className="list-row"
                  style={{ color: 'inherit' }}
                >
                  <div className="list-row__main">
                    <div className="list-row__name">{row.name}</div>
                    <div className="list-row__meta">
                      {formatDateLong(row.date, timezone)} ·{' '}
                      {row.first_punch_in ? formatTime(row.first_punch_in, timezone) : '--'} →{' '}
                      {row.last_punch_out ? formatTime(row.last_punch_out, timezone) : 'Active'}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <Badge variant={statusModifier(row.status)}>{row.status}</Badge>
                    <div className="mono" style={{ fontSize: 13, marginTop: 4, fontWeight: 640 }}>
                      {formatDuration(row.total_seconds)}
                    </div>
                  </div>
                </Link>
              ))
            )}
          </Card>
        </>
      )}
    </>
  );
}
