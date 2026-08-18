import { useMemo, useState } from 'react';
import { CalendarX2 } from 'lucide-react';
import {
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  SegmentedControl,
  SkeletonCard,
  StatTile,
} from '../components/common/index.jsx';
import { SessionList } from '../components/attendance/PunchControls.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { useAsync } from '../hooks/useAsync.js';
import { getHistory } from '../services/attendanceService.js';
import { formatDateLong, formatDuration, formatWeekday, shiftDays, todayIso } from '../utils/time.js';
import { pluralise } from '../utils/format.js';

const PERIODS = [
  { value: 'today', label: 'Today' },
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
  { value: 'custom', label: 'Custom' },
];

export default function History() {
  const { timezone } = useAuth();
  const [period, setPeriod] = useState('week');
  const today = useMemo(() => todayIso(timezone), [timezone]);
  const [fromDate, setFromDate] = useState(() => shiftDays(today, -13));
  const [toDate, setToDate] = useState(today);

  const { data, error, loading, reload } = useAsync(
    () =>
      getHistory(
        period === 'custom' ? { period, fromDate, toDate } : { period },
      ),
    [period, period === 'custom' ? fromDate : null, period === 'custom' ? toDate : null],
  );

  return (
    <>
      <SegmentedControl
        options={PERIODS}
        value={period}
        onChange={setPeriod}
        ariaLabel="History period"
      />

      {period === 'custom' && (
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
        </Card>
      )}

      {loading && !data && <SkeletonCard lines={4} />}
      {error && <ErrorState error={error} onRetry={reload} />}

      {data && (
        <>
          <div className="grid-2">
            <StatTile label="Days present" value={data.days.length} />
            <StatTile label="Total time" value={formatDuration(data.total_seconds)} />
          </div>

          {data.days.length === 0 ? (
            <Card>
              <EmptyState icon={CalendarX2} title="No attendance in this range">
                Days appear here once you punch in.
              </EmptyState>
            </Card>
          ) : (
            data.days.map((day) => (
              <Card key={day.date} flush>
                <div className="day-card__head">
                  <div>
                    <div className="day-card__date">{formatDateLong(day.date, timezone)}</div>
                    <div className="tiny">
                      {formatWeekday(day.date, timezone)} ·{' '}
                      {pluralise(day.session_count, 'session')}
                      {day.is_late ? ' · late arrival' : ''}
                    </div>
                  </div>
                  <div className="day-card__total">{formatDuration(day.total_seconds)}</div>
                </div>
                <SessionList sessions={day.sessions} timezone={timezone} />
              </Card>
            ))
          )}
        </>
      )}
    </>
  );
}
