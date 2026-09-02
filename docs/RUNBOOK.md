# Runbook — what to type, in order

Everything here is copy-paste. Run each command from the project folder unless
it says otherwise:

```bash
cd "/Users/adityasoni/Desktop/Punch in system "
```

---

## A. Run it today (laptop + tunnel)

One command brings up the API, opens an HTTPS tunnel and deploys the app:

```bash
npm run start
```

Wait for it to print **Deploy complete**. It can pause a couple of minutes on
*"waiting for the hostname to resolve"* — that is normal for a new tunnel.

Then open **https://punchin-7c498.web.app**

To shut it down:

```bash
npm run stop
```

### If it finishes without deploying

```bash
npm run deploy:api
```

Still says unreachable? Check the address resolves, then override:

```bash
dig +short $(cat .tunnel-url | sed 's|https://||')
FORCE=1 ./scripts/deploy-firebase.sh
```

### Limits of this mode

- Works only while the laptop is awake and `npm run start` is running
- Every restart mints a new tunnel URL, so the app must be redeployed
- The API is publicly reachable while the tunnel is open

Part B removes all three.

---

## B. Make it permanent (Cloud Run + Cloud SQL)

Do this once and the tunnel is never needed again.

### Step 1 — Sign in to Google (only you can)

```bash
gcloud auth login
```

### Step 2 — Turn on billing (only you can)

Open <https://console.firebase.google.com/project/punchin-7c498/usage/details>
and upgrade to the **Blaze** plan. Firebase cannot forward `/api/**` to a
backend on the free Spark plan.

### Step 3 — Create the database (~10 minutes)

```bash
./scripts/create-cloudsql.sh
```

It prints a password at the end. Copy it.

### Step 4 — Deploy the API

```bash
export DB_PASSWORD='paste-the-password-from-step-3'
./scripts/deploy-cloudrun.sh
```

### Step 5 — Create the workspace and your admin account

```bash
./scripts/bootstrap-remote.sh --admin "Aditya Soni" adityaksoni234@gmail.com ADM001
```

It prints a temporary password. Copy it — it is shown once.

### Step 6 — Point the app at the new API

```bash
./scripts/use-same-origin.sh
```

### Step 7 — Check it worked

```bash
curl -s https://punchin-7c498.web.app/api/v1/health
```

**JSON** = done. **HTML** = something above did not finish.

Then stop the laptop backend for good:

```bash
npm run stop
```

---

## C. Using the app

| Who | Where | Signs in with |
|---|---|---|
| Member | https://punchin-7c498.web.app | Enrollment number + password |
| Admin | same site, **Admin** tab on sign in | Email + password |

- New members tap **Create one** on the sign-in screen and register with name,
  email and enrollment number.
- Admin screens: Presence, Attendance, Users, Audit, Settings.
- Change your password: **Profile → Change password**.

---

## D. Everyday commands

| Task | Command |
|---|---|
| Start everything (tunnel mode) | `npm run start` |
| Stop everything | `npm run stop` |
| Redeploy the app only | `npm run deploy:api` |
| Backend log | `tail -f .run/api.log` |
| Tunnel log | `tail -f .run/tunnel.log` |
| Run the tests | `cd backend && ./.venv/bin/python -m pytest -q` |
| Switch to local dev settings | `./scripts/use-env.sh dev` |
| Switch to Firebase settings | `./scripts/use-env.sh firebase` |

---

## E. When something breaks

| Symptom | Cause | Fix |
|---|---|---|
| "Could not sign in" | App built against a dead API address | `npm run deploy:api` |
| "No API responded at ..." | Backend or tunnel is down | `npm run start` |
| "Refusing to start with an insecure configuration" | `SECRET_KEY` empty, usually after copying an `.env.example` by hand | `./scripts/use-env.sh firebase` |
| "No backend answering on 127.0.0.1:8000" | API not running (a `Ctrl-C` kills it) | `npm run start` |
| Punch rejected, `OUTSIDE_GEOFENCE` | Genuinely outside the 100 m radius | Punch at the workspace, or widen the radius in Admin → Settings |
| Punch rejected, `ACCURACY_TOO_LOW` | Indoor GPS is worse than 50 m | Enable Precise Location, or raise the limit in Admin → Settings |
| Location blocked on iPhone | Safari's per-site setting, separate from Location Services | `aA` in the address bar → Website Settings → Location → Ask |

Never edit `backend/.env` by copying an `.example` file over it — use
`./scripts/use-env.sh`. The examples ship with an empty `SECRET_KEY`, and
overwriting the real one signs everybody out.
