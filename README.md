# Punch In — Geofenced Workspace Attendance

A mobile-first PWA for workspace attendance. Users punch in and out only when a
**real browser GPS reading** is independently verified by the backend against a
configurable geofence. Admins see live presence, manage users, configure the
workspace and export reports.

```
React 18 + Vite PWA  ──HTTPS/REST──▶  FastAPI  ──▶  Services  ──▶  SQLAlchemy  ──▶  PostgreSQL 16
```

The client is untrusted. Distance, geofence validity, attendance state,
durations, role and identity are all derived on the server.

---

## 1. What is implemented

**User**
- Email + password sign in, forced password change on a temporary credential
- Real `navigator.geolocation` capture, one shot per punch — no tracking
- Punch IN / Punch OUT with server-side geofence + accuracy validation
- Live workspace timer (server timestamp + measured clock skew, never GPS)
- Today's sessions, multiple sessions per day, daily totals
- History: today / week / month / custom range
- Analytics: days present & absent, totals, averages, longest session, late
  arrivals, average arrival & departure
- Installable PWA; offline opens the shell but refuses to punch

**Admin**
- Live presence dashboard: total / present / absent / checked out with each
  present person's running duration
- Attendance browsing across users and dates, per-user drill-down
- Punch verification records including rejections, distance, accuracy and the
  radius that was in force at the time
- User management: create, edit, enable/disable, change role, reset password
- Workspace settings: coordinates, radius, accuracy threshold, timezone, start
  time, late threshold, auto-close, anti-spoofing thresholds
- CSV attendance export
- Audit log viewer

**Security**
- argon2id password hashing, JWT access token in memory only, rotating
  HttpOnly refresh cookie with reuse detection
- Server-side RBAC on every admin endpoint
- Database-backed rate limiting on login and punch endpoints
- Idempotency keys and a partial unique index that make duplicate or racing
  punches impossible
- Full audit trail, security headers, CSP, secrets from the environment only

---

## 2. Project structure

```
backend/
  app/
    api/v1/          routers: auth, attendance, admin_*, health
    core/            config, security, deps (RBAC), errors, time, logging
    db/              engine/session, Alembic migrations
    models/          SQLAlchemy models + enums
    schemas/         Pydantic request/response models
    repositories/    all data access
    services/        auth, geofence, attendance, analytics, report, audit,
                     user, workspace, rate limiting
    middleware/      request context, security headers
    jobs/            maintenance (auto-close, retention purge)
    utils/geo.py     haversine + coordinate validation
    main.py          app factory, error handlers
  scripts/           seed_workspace.py, create_admin.py
  tests/             unit/ + integration/  (93 tests)
frontend/
  src/
    components/      common, layout, attendance, location
    pages/           Login, ChangePassword, Dashboard, History, Profile,
                     admin/*
    layouts/         AppLayout, AdminLayout
    hooks/           useGeolocation, usePunch, useLiveTimer, useAsync,
                     useOnlineStatus
    services/        apiClient, authService, attendanceService, adminService
    context/         AuthContext, ToastContext
    routes/          route table + guards
    styles/          tokens, base, components
  public/            manifest.webmanifest, sw.js, icons/
docker-compose.yml   PostgreSQL for local development
```

---

## 3. Environment variables

Backend (`backend/.env`, copy from `backend/.env.example`):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/punchin` |
| `SECRET_KEY` | JWT signing key. **Required** in production. `python -c "import secrets;print(secrets.token_urlsafe(64))"` |
| `ENVIRONMENT` | `development` \| `production` \| `test` |
| `DEBUG` | `false` in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | default 15 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | default 30 |
| `COOKIE_SECURE` | **must be `true`** in production |
| `COOKIE_SAMESITE` | `lax` for a same-origin deploy |
| `CORS_ORIGINS` | comma separated; empty for same-origin |
| `RATE_LIMIT_LOGIN_MAX` / `_WINDOW_SECONDS` | login limit, default 5 / 900s |
| `RATE_LIMIT_PUNCH_MAX` / `_WINDOW_SECONDS` | punch limit, default 10 / 60s |
| `LOCATION_RETENTION_DAYS` | coordinates older than this are purged, default 180 |
| `TRUST_PROXY_HEADERS` | `true` only behind a trusted reverse proxy |

The app refuses to start in `production` with a default `SECRET_KEY`,
`COOKIE_SECURE=false` or `DEBUG=true`.

Geofence radius, accuracy threshold, coordinates, timezone and attendance
policy are **not** environment variables — they live in the `workspaces` table
and are edited from the admin app at runtime.

---

## 4. Database setup

Either use Docker:

```bash
docker compose up -d db
```

…or a local PostgreSQL 16:

```bash
createuser punchin --pwprompt --createdb
createdb -O punchin punchin
```

Then run the migrations:

```bash
cd backend && ./.venv/bin/alembic upgrade head
```

The initial migration creates the `citext` extension, every table, all foreign
keys, check constraints and indexes — including
`uq_one_open_session_per_user`, the partial unique index that guarantees a user
can never hold two open sessions.

---

## 5. Running the backend

```bash
cd backend
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env          # then edit DATABASE_URL and SECRET_KEY
./.venv/bin/alembic upgrade head
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

API docs (development only): http://localhost:8000/docs

---

## 6. Running the frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
```

Production build:

```bash
npm run build      # emits frontend/dist/
```

Serve `frontend/dist` and proxy `/api` to uvicorn from the **same origin** — the
refresh cookie is `SameSite=Lax` and scoped to `/api/v1/auth`.

### Testing on a real phone (important)

**Geolocation only works on a secure context**: HTTPS, or `http://localhost`.
A phone on the same Wi-Fi reaches this machine on a LAN address such as
`http://192.168.1.23:5173`, which is **not** a secure context — the browser
refuses to release a position no matter how the phone's Location Services are
configured. iOS Safari makes this especially confusing: it reports the
permission as grantable and then denies the actual call, which looks exactly
like the user having blocked the site.

Two ways to get HTTPS:

**A. Self-signed certificate (no internet, LAN only)**

```bash
cd frontend
npm run cert        # issues a cert for localhost + this machine's LAN IP
npm run dev:https   # serves https://<LAN-IP>:5173
```

Safari will warn the certificate is untrusted. Either tap through the warning,
or install it properly: AirDrop/email `frontend/certs/dev-cert.pem` to the
phone, then **Settings → General → VPN & Device Management** (install the
profile) and **Settings → General → About → Certificate Trust Settings**
(switch it on). Re-run `npm run cert` if your LAN IP changes.

`frontend/certs/` is gitignored — the private key never leaves the machine.

**B. HTTPS tunnel (publicly reachable URL, trusted certificate)**

```bash
cloudflared tunnel --url http://localhost:5173     # or: ngrok http 5173
```

Note this exposes your dev server on the public internet for the life of the
tunnel.

### If location still fails on the phone

The app now tells you which of these it is, but for reference:

| Symptom | Cause | Fix |
|---|---|---|
| "This page needs HTTPS for location" | Non-secure origin | Use HTTPS as above |
| "Your browser refused the location request" on iOS | Safari's **per-site** answer is "Don't Allow" — separate from Location Services | `aA` in the address bar → Website Settings → Location → Ask/Allow. Or Settings → Apps → Safari → Location → Ask |
| Prompt never appears | Site permission already answered | Same as above; iOS remembers a denial |
| "Location accuracy too low" | Indoor GPS | Enable Precise Location, move near a window, or raise the threshold in Admin → Settings |

The app never decides on your behalf that location is blocked: apart from the
non-secure-origin case (where the browser can never succeed), tapping **Punch
in** always calls the real browser API so the phone shows its own permission
prompt and you answer it.

---

## 7. Creating the first admin

```bash
cd backend
./.venv/bin/python -m scripts.create_admin \
  --name "Your Name" --email you@example.com --member-id ADM001
```

It prompts for a password (hidden, minimum 10 characters). Add
`--generate-password` to have a random one generated and printed once instead;
the account is then forced to change it at first sign-in. No credential is ever
hardcoded or defaulted.

---

## 8. Configuring the workspace

Seed the initial geofence:

```bash
cd backend
./.venv/bin/python -m scripts.seed_workspace \
  --name "Main Workspace" \
  --lat 23.0900259 --lng 72.5343615 \
  --radius 100 --accuracy 50 --timezone Asia/Kolkata
```

After that, everything is editable in **Admin → Settings** with no code change
and no redeploy: coordinates, radius, GPS accuracy threshold, timezone,
attendance start time, late threshold, auto-close window and the anti-spoofing
speed threshold. Changes apply to the very next punch.

Each punch snapshots the radius and threshold that applied to it, so changing
the configuration never rewrites the meaning of historical records.

**Calibration.** 100 m / 50 m is a sensible start, but the right numbers depend
on the building. Indoors, consumer GPS is routinely accurate to only 30–100 m.
Watch Admin → Audit for `PUNCH_IN_REJECTED` with reason `ACCURACY_TOO_LOW` in
the first week and widen the threshold (or radius) if genuine staff are being
turned away. The settings screen warns when the accuracy threshold exceeds half
the radius.

---

## 9. How geofence validation works

Every punch posts only raw sensor output:

```json
{ "latitude": 23.090012, "longitude": 72.534401, "accuracy": 14.5,
  "captured_at": "2026-08-18T09:42:11.482Z" }
```

`captured_at` is the device clock; it is stored for forensics and used in **no**
calculation. The server then runs, in order (first failure wins):

1. **Structure** — latitude/longitude in range, not the `(0, 0)` "no fix"
   sentinel, accuracy positive → else `INVALID_COORDINATES`
2. **Accuracy** — `accuracy <= workspace.accuracy_threshold_meters` → else
   `ACCURACY_TOO_LOW`
3. **Distance** — haversine great-circle distance from the workspace centre,
   `distance <= workspace.radius_meters` → else `OUTSIDE_GEOFENCE`
4. **Plausibility** — implied speed since the previous accepted punch against
   `max_travel_speed_kmh`; flagged in the audit log, and blocked as
   `IMPOSSIBLE_MOVEMENT` if the admin has enabled blocking
5. **State** — user active, and the transition legal for the current state

Haversine uses the IUGG mean Earth radius (6 371 008.8 m). Against a true
WGS-84 geodesic the error is under 0.5 %, i.e. well under a metre on a 100 m
fence — far below GPS noise.

**Boundary policy** is a strict `distance <= radius` against the centre, with no
padding by the accuracy figure. Padding would silently widen the fence by up to
the accuracy threshold; if a site needs more tolerance, the radius is the one
visible knob to turn.

Punch mutations run in a single transaction that starts with
`SELECT … FOR UPDATE` on the user row, so a user's punches are serialised, and
the partial unique index makes two open sessions impossible even under a race.
Every attempt — accepted or rejected — writes a `punch_events` row and an audit
entry.

---

## 10. Maintenance job

```bash
cd backend && ./.venv/bin/python -m app.jobs.maintenance
```

Run it from cron every 15 minutes. It:

- closes sessions left open past `auto_close_after_hours`, capping the duration
  and marking them `AUTO_CLOSED` (never presented as a verified punch out)
- deletes stored coordinates older than `LOCATION_RETENTION_DAYS` while keeping
  the attendance record and the accept/reject verdict
- sweeps expired refresh tokens and rate-limit windows

---

## 11. Testing

```bash
cd backend
createdb -O punchin punchin_test          # once
./.venv/bin/python -m pytest -q
```

**93 tests, all passing.** Coverage of the critical logic:

- *Geofence* — centre, inside, outside, exact boundary (computed by bisection,
  not an approximation), 1 cm outside, accuracy at/over threshold, accuracy
  checked before distance, null island, out-of-range coordinates, configurable
  radius and threshold changing the verdict, implausible movement flagged and
  blocked
- *Attendance* — valid punch in/out, duplicate punch in, punch out with no
  active session, rejected punch creates no session but is recorded, multiple
  sessions per day, day totals, active-session elapsed from server time,
  database refusal of two open sessions, forged client timestamp ignored,
  refresh-safe state, auto-close
- *Security* — unauthenticated access, user hitting admin endpoints, forged
  ADMIN role in a token, disabled user locked out immediately, login and punch
  rate limiting, invalid payloads, extra client-asserted fields ignored,
  security headers, self-disable prevention
- *Auth* — login, wrong password, unknown email, disabled account, token
  invalidation on password change, refresh rotation and reuse detection
- *Admin* — presence counts, user CRUD, temporary passwords, workspace edits
  changing punch outcomes, CSV export contents, audit contents, radius snapshot
  survival

Frontend build: `npm run build` (clean).

Verified end to end in a mobile viewport: sign-in, forced password change,
dashboard states, the blocked-location path (no punch is sent), punch in →
live timer → punch out with the verification sheet, and the admin screens.

---

## 12. Known browser / PWA limitations

1. **GPS spoofing cannot be prevented in a browser.** Mock-location apps,
   rooted devices and desktop devtools sensor overrides produce readings that
   are indistinguishable from genuine ones at the API level. This system makes
   spoofing *auditable and inconvenient* — server-side validation, accuracy
   gates, movement plausibility, a full forensic trail — it does not make it
   impossible. Real anti-spoofing needs a native app with Play Integrity /
   DeviceCheck attestation, or an on-site factor (BLE beacon, rotating QR, NFC).
   The admin settings screen says so explicitly rather than implying otherwise.
2. **Indoor accuracy.** 30–100 m indoors is normal; a strict threshold will
   block legitimate staff. Both the radius and the threshold are admin-tunable
   for exactly this reason.
3. **HTTPS is mandatory.** `getCurrentPosition` is unavailable on non-localhost
   HTTP, so phone testing needs `npm run dev:https` or a tunnel — see
   "Testing on a real phone". The app detects a non-secure origin and says so
   explicitly instead of blaming the device's location settings.
4. **iOS PWA.** Location needs a user gesture and per-origin permission. Safari
   stores a *per-site* location answer independently of Location Services, and
   once "Don't Allow" is tapped it stops prompting until that site setting is
   reset — the in-app help walks through it. The access token is memory-only
   and is re-derived from the refresh cookie on every cold start, so an
   install/relaunch is a refresh, not a re-login.
5. **Offline punching is refused by design.** The service worker never caches
   or queues `/api`; a queued punch could not be checked against the geofence
   at the time it was finally delivered.
6. **Device clock manipulation is irrelevant** — every stored timestamp is the
   server's, and the client's is kept only for forensics.
7. **Day boundaries.** A session is attributed to the workspace-local day it
   *started*, so an overnight session counts against that day.
8. **`days_absent`** counts Mon–Fri days in range that have already passed and
   have no attendance; the system has no holiday or shift calendar yet.
9. **Rate limiting** is fixed-window in PostgreSQL. It is shared correctly
   across workers, but a burst straddling a window edge can briefly exceed the
   nominal rate.
