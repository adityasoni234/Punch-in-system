import { useEffect, useState } from 'react';
import { MapPin, Save } from 'lucide-react';
import {
  Button,
  Card,
  CardTitle,
  ErrorState,
  Field,
  Input,
  Notice,
  Select,
  SkeletonCard,
} from '../../components/common/index.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useToast } from '../../context/ToastContext.jsx';
import { getWorkspace, updateWorkspace } from '../../services/adminService.js';

const TIMEZONES = [
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Singapore',
  'Europe/London',
  'Europe/Berlin',
  'America/New_York',
  'America/Los_Angeles',
  'Australia/Sydney',
  'UTC',
];

export default function AdminSettings() {
  const toast = useToast();
  const { data, error, loading, reload } = useAsync(() => getWorkspace(), []);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    if (data) {
      setForm({
        name: data.name,
        latitude: String(data.latitude),
        longitude: String(data.longitude),
        radius_meters: String(data.radius_meters),
        accuracy_threshold_meters: String(data.accuracy_threshold_meters),
        timezone: data.timezone,
        attendance_start_time: data.attendance_start_time.slice(0, 5),
        late_threshold_minutes: String(data.late_threshold_minutes),
        auto_close_after_hours: String(data.auto_close_after_hours),
        max_travel_speed_kmh: String(data.max_travel_speed_kmh),
        block_impossible_movement: data.block_impossible_movement,
      });
    }
  }, [data]);

  if (loading && !data) return <SkeletonCard lines={6} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!form) return null;

  const set = (key) => (event) =>
    setForm({
      ...form,
      [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
    });

  const submit = async (event) => {
    event.preventDefault();
    setSaveError(null);
    setBusy(true);
    try {
      await updateWorkspace({
        name: form.name,
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
        radius_meters: Number(form.radius_meters),
        accuracy_threshold_meters: Number(form.accuracy_threshold_meters),
        timezone: form.timezone,
        attendance_start_time: `${form.attendance_start_time}:00`,
        late_threshold_minutes: Number(form.late_threshold_minutes),
        auto_close_after_hours: Number(form.auto_close_after_hours),
        max_travel_speed_kmh: Number(form.max_travel_speed_kmh),
        block_impossible_movement: form.block_impossible_movement,
      });
      toast.success('Workspace updated. It applies to the next punch immediately.');
      reload({ quiet: true });
    } catch (caught) {
      setSaveError(caught.details?.fields
        ? Object.entries(caught.details.fields)
            .map(([field, message]) => `${field}: ${message}`)
            .join('; ')
        : caught.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="stack" onSubmit={submit}>
      <div className="greeting" style={{ fontSize: 20 }}>
        Workspace settings
      </div>

      {data.warnings?.map((warning) => (
        <Notice key={warning} variant="warn" title="Check this setting">
          {warning}
        </Notice>
      ))}
      {saveError && <Notice variant="error" title="Could not save">{saveError}</Notice>}

      <Card>
        <CardTitle>Geofence</CardTitle>
        <div className="stack">
          <Field label="Workspace name">
            <Input value={form.name} onChange={set('name')} required />
          </Field>
          <div className="grid-2">
            <Field label="Latitude">
              <Input
                type="number"
                step="0.0000001"
                inputMode="decimal"
                value={form.latitude}
                onChange={set('latitude')}
                required
              />
            </Field>
            <Field label="Longitude">
              <Input
                type="number"
                step="0.0000001"
                inputMode="decimal"
                value={form.longitude}
                onChange={set('longitude')}
                required
              />
            </Field>
          </div>
          <Field
            label="Geofence radius (metres)"
            hint="Distance from the centre within which punching is allowed. 10–5000."
          >
            <Input
              type="number"
              min="10"
              max="5000"
              inputMode="numeric"
              value={form.radius_meters}
              onChange={set('radius_meters')}
              required
            />
          </Field>
          <Field
            label="Maximum GPS accuracy (metres)"
            hint="Readings less accurate than this are refused. Indoors, 50–75 m is realistic."
          >
            <Input
              type="number"
              min="5"
              max="1000"
              inputMode="numeric"
              value={form.accuracy_threshold_meters}
              onChange={set('accuracy_threshold_meters')}
              required
            />
          </Field>
        </div>
      </Card>

      <Card>
        <CardTitle>Attendance policy</CardTitle>
        <div className="stack">
          <Field label="Timezone">
            <Select value={form.timezone} onChange={set('timezone')}>
              {TIMEZONES.map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </Select>
          </Field>
          <div className="grid-2">
            <Field label="Start time">
              <Input
                type="time"
                value={form.attendance_start_time}
                onChange={set('attendance_start_time')}
                required
              />
            </Field>
            <Field label="Late after (min)">
              <Input
                type="number"
                min="0"
                max="480"
                inputMode="numeric"
                value={form.late_threshold_minutes}
                onChange={set('late_threshold_minutes')}
                required
              />
            </Field>
          </div>
          <Field
            label="Auto-close sessions after (hours)"
            hint="A session left open longer than this is capped and flagged, never counted as a verified punch out."
          >
            <Input
              type="number"
              min="1"
              max="72"
              inputMode="numeric"
              value={form.auto_close_after_hours}
              onChange={set('auto_close_after_hours')}
              required
            />
          </Field>
        </div>
      </Card>

      <Card>
        <CardTitle>Anti-spoofing</CardTitle>
        <div className="stack">
          <Field
            label="Implausible travel speed (km/h)"
            hint="Movement faster than this between two punches is flagged in the audit log."
          >
            <Input
              type="number"
              min="10"
              max="5000"
              inputMode="numeric"
              value={form.max_travel_speed_kmh}
              onChange={set('max_travel_speed_kmh')}
              required
            />
          </Field>
          <label className="switch-row">
            <span className="field__label" style={{ marginBottom: 0 }}>
              Block implausible movement
            </span>
            <input
              type="checkbox"
              checked={form.block_impossible_movement}
              onChange={set('block_impossible_movement')}
              style={{ width: 22, height: 22 }}
            />
          </label>
          <Notice variant="info" icon={MapPin} title="What this can and cannot do">
            A browser cannot prove that a GPS reading is genuine. These controls make spoofing
            visible and awkward — they do not make it impossible. Treat the audit trail, not the
            geofence, as the evidence.
          </Notice>
        </div>
      </Card>

      <Button type="submit" variant="primary" block icon={Save} loading={busy}>
        Save settings
      </Button>
    </form>
  );
}
