/**
 * Every location failure the browser can hand us, expressed in terms the user
 * can act on. No state silently fails.
 */
import { Crosshair, MapPin, ShieldAlert, WifiOff } from 'lucide-react';
import { Button, Notice } from '../common/index.jsx';
import { ErrorCode } from '../../utils/errorCodes.js';

const IOS = /iPad|iPhone|iPod/.test(typeof navigator === 'undefined' ? '' : navigator.userAgent);

export function LocationPermissionPrompt({ onEnable, busy }) {
  return (
    <Notice
      variant="info"
      icon={MapPin}
      title="Location required"
      actions={
        <Button size="sm" variant="primary" onClick={onEnable} loading={busy}>
          Enable location
        </Button>
      }
    >
      Location access is required to verify that you are inside the workspace before punching in or
      out. Your location is read only at the moment you punch — never in the background.
    </Notice>
  );
}

export function LocationBlockedHelp({ onRetry }) {
  return (
    <Notice
      variant="error"
      icon={ShieldAlert}
      title="Location is blocked"
      actions={
        <Button size="sm" variant="outline" onClick={onRetry}>
          I have enabled it — try again
        </Button>
      }
    >
      {IOS ? (
        <>
          On iPhone: open <strong>Settings → Privacy &amp; Security → Location Services</strong>,
          make sure it is on, then find your browser and choose{' '}
          <strong>While Using the App</strong>. Also enable <strong>Precise Location</strong>. Then
          reload this page.
        </>
      ) : (
        <>
          Tap the padlock or <strong>⋮</strong> icon in the address bar, open{' '}
          <strong>Permissions / Site settings</strong>, set <strong>Location</strong> to{' '}
          <strong>Allow</strong>, then reload this page. On Android also check{' '}
          <strong>Settings → Location</strong> is switched on.
        </>
      )}
    </Notice>
  );
}

export function AccuracyTooLowHelp({ message, accuracy, onRetry }) {
  return (
    <Notice
      variant="warn"
      icon={Crosshair}
      title="Location accuracy too low"
      actions={
        <Button size="sm" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      }
    >
      {message}
      <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
        <li>Turn on Precise Location for this browser</li>
        <li>Move near a window or step outside</li>
        <li>Switch off any VPN or location-mocking app</li>
      </ul>
      {accuracy != null && (
        <div style={{ marginTop: 8, fontSize: 12.5 }}>
          Last reading was accurate to about {Math.round(accuracy)} m.
        </div>
      )}
    </Notice>
  );
}

export function OutsideWorkspaceHelp({ message, onRetry }) {
  return (
    <Notice
      variant="error"
      icon={MapPin}
      title="Outside workspace"
      actions={
        <Button size="sm" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      }
    >
      {message}
    </Notice>
  );
}

export function OfflineHelp() {
  return (
    <Notice variant="warn" icon={WifiOff} title="No internet connection">
      Punching requires an active internet connection — the server has to verify your location as it
      happens. Nothing is queued for later.
    </Notice>
  );
}

/** Maps a punch failure to the right explanation panel. */
export function PunchFailure({ failure, onRetry }) {
  if (!failure) return null;
  switch (failure.code) {
    case ErrorCode.OFFLINE:
      return <OfflineHelp />;
    case ErrorCode.LOCATION_PERMISSION_DENIED:
      return <LocationBlockedHelp onRetry={onRetry} />;
    case ErrorCode.ACCURACY_TOO_LOW:
      return (
        <AccuracyTooLowHelp
          message={failure.message}
          accuracy={failure.accuracy}
          onRetry={onRetry}
        />
      );
    case ErrorCode.OUTSIDE_GEOFENCE:
      return <OutsideWorkspaceHelp message={failure.message} onRetry={onRetry} />;
    case ErrorCode.LOCATION_TIMEOUT:
    case ErrorCode.LOCATION_UNAVAILABLE:
    case ErrorCode.LOCATION_UNSUPPORTED:
      return (
        <Notice
          variant="warn"
          icon={Crosshair}
          title="Location unavailable"
          actions={
            <Button size="sm" variant="outline" onClick={onRetry}>
              Try again
            </Button>
          }
        >
          {failure.message}
        </Notice>
      );
    case ErrorCode.RATE_LIMITED:
      return (
        <Notice variant="warn" title="Too many attempts">
          {failure.message}
        </Notice>
      );
    default:
      return (
        <Notice
          variant="error"
          title="Punch not recorded"
          actions={
            <Button size="sm" variant="outline" onClick={onRetry}>
              Try again
            </Button>
          }
        >
          {failure.message}
        </Notice>
      );
  }
}
