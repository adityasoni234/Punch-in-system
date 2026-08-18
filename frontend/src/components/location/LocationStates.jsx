/**
 * Every location failure the browser can hand us, expressed in terms the user
 * can act on. No state silently fails.
 */
import { Crosshair, Lock, MapPin, ShieldAlert, WifiOff } from 'lucide-react';
import { Button, Notice } from '../common/index.jsx';
import { ErrorCode } from '../../utils/errorCodes.js';

const UA = typeof navigator === 'undefined' ? '' : navigator.userAgent;
const IOS = /iPad|iPhone|iPod/.test(UA);

function currentOrigin() {
  return typeof window === 'undefined' ? '' : window.location.host;
}

/**
 * Shown when the page is not on a secure origin.
 *
 * This is a browser rule, not an app rule and not a device setting: Location
 * Services can be fully switched on and the call will still be refused. Saying
 * so plainly is the difference between a user fixing it in a minute and them
 * hunting through iOS settings that were never the problem.
 */
export function InsecureContextHelp() {
  return (
    <Notice variant="error" icon={Lock} title="This page needs HTTPS for location">
      You are on <strong>http://{currentOrigin()}</strong>. Browsers only release location
      on a secure page, so this is refused before your device settings are ever consulted
      — turning Location Services on will not change it.
      <div style={{ marginTop: 8 }}>Open the app on an address that is either:</div>
      <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
        <li>
          an <strong>https://</strong> address (see <code>npm run dev:https</code> or an
          HTTPS tunnel), or
        </li>
        <li>
          <strong>http://localhost:5173</strong> on the machine running the server
        </li>
      </ul>
    </Notice>
  );
}

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
      title="Your browser refused the location request"
      actions={
        <Button size="sm" variant="outline" onClick={onRetry}>
          I have allowed it — try again
        </Button>
      }
    >
      {IOS ? (
        <>
          Your iPhone&apos;s Location Services being on is not enough — Safari keeps a
          separate <em>per-site</em> answer, and once you tap <strong>Don&apos;t Allow</strong>{' '}
          it stops asking. To be asked again:
          <ol style={{ margin: '8px 0 0', paddingLeft: 18 }}>
            <li>
              Tap <strong>aA</strong> in the address bar → <strong>Website Settings</strong> →
              set <strong>Location</strong> to <strong>Ask</strong> or{' '}
              <strong>Allow</strong>, then reload.
            </li>
            <li>
              If that option is missing: <strong>Settings → Apps → Safari → Location</strong>{' '}
              (older iOS: <strong>Settings → Safari → Location</strong>) → <strong>Ask</strong>.
            </li>
            <li>
              Check <strong>Settings → Privacy &amp; Security → Location Services → Safari
              Websites</strong> is <strong>While Using the App</strong> with{' '}
              <strong>Precise Location</strong> on.
            </li>
          </ol>
          <div style={{ marginTop: 8 }}>
            Then tap the button below — Safari will ask you, and you decide.
          </div>
        </>
      ) : (
        <>
          Tap the padlock or <strong>⋮</strong> icon in the address bar, open{' '}
          <strong>Permissions / Site settings</strong>, set <strong>Location</strong> to{' '}
          <strong>Allow</strong> (or clear the saved choice so you are asked again), then
          reload. On Android also check <strong>Settings → Location</strong> is switched on.
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
    case ErrorCode.LOCATION_INSECURE_CONTEXT:
      return <InsecureContextHelp />;
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
