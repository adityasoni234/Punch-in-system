# Deployment — Firebase Hosting

Firebase Hosting gives you HTTPS on a real domain, which is what the app needs:
`navigator.geolocation` only works on a secure context, so a hosted HTTPS build
fixes the phone problem permanently.

Hosting serves **static files only**. The FastAPI backend and PostgreSQL have
to live somewhere else.

---

## Option C — App on Firebase, API on your laptop (current setup)

```
   https://your-project.web.app          https://xxxx.trycloudflare.com
   Firebase Hosting (React PWA)  ──────▶ Cloudflare tunnel
                                                │
                                         127.0.0.1:8000  (uvicorn, your laptop)
                                                │
                                         PostgreSQL      (your laptop)
```

**The tunnel is not optional.** An HTTPS page cannot call an `http://` address —
browsers block it as mixed content — so `http://192.168.110.30:8000` is
unreachable from a Firebase-hosted app no matter what else is configured.

Trade-offs to be clear about:

- The app only works while your laptop is awake, uvicorn is running and the
  tunnel is up. Close the lid and everyone is locked out.
- The free quick-tunnel URL changes on every restart, so the frontend has to be
  rebuilt and redeployed each time (`VITE_API_BASE_URL` is baked into the
  bundle at build time). A named Cloudflare tunnel on a domain you own gives a
  stable URL and removes this.
- App and API are on different origins, so the refresh cookie drops to
  `SameSite=None` and CORS is required. Safari's tracking prevention is
  unfriendly to third-party cookies; if sign-in gets dropped on iOS, this is
  why, and the fix is a same-origin deployment (Option A) or putting both
  behind one hostname.
- While the tunnel runs, your API is on the public internet. It still requires
  authentication and is rate limited, but it is exposed.

### Steps

```bash
# 1. Backend settings for split origin
cp backend/.env.tunnel.example backend/.env      # keep a copy of your dev .env
python3 -c "import secrets;print(secrets.token_urlsafe(64))"   # -> SECRET_KEY
# edit CORS_ORIGINS to your real Firebase origins

# 2. Start the API
cd backend && ./.venv/bin/uvicorn app.main:app --port 8000

# 3. Expose it over HTTPS (new terminal) — prints the URL to use
./scripts/tunnel-api.sh

# 4. Point the frontend at that URL
cp frontend/.env.production.example frontend/.env.production
#    VITE_API_BASE_URL=https://<tunnel-url>/api/v1

# 5. Deploy the PWA
npx firebase login
cp .firebaserc.example .firebaserc               # add your project id
npm run deploy
```

Then open `https://your-project.web.app` on the phone, sign in, and punch. This
runs on the **free Spark plan** — no Cloud Run, no billing.

### Simpler alternative if Firebase is not the goal

If the only aim is HTTPS on your phone, one tunnel to the dev server does it
with no Firebase, no CORS and no cookie relaxation, because everything stays on
one origin:

```bash
cd frontend && npm run dev          # Vite proxies /api to :8000
cloudflared tunnel --url http://localhost:5173
```

Open the printed URL on the phone. This is strictly more secure than Option C
and needs no rebuild when the URL changes.

---

## Option A — Same origin, Cloud Run (most robust)


```
                    https://your-app.web.app
                              │
                    Firebase Hosting (CDN, HTTPS)
                    ├── /            → frontend/dist  (React PWA)
                    └── /api/**      → Cloud Run       (FastAPI)
                                             │
                                       Cloud SQL (PostgreSQL)
```

The app and the API share one origin, so the refresh token stays in a
`SameSite=Lax` cookie and there is no CORS at all. Worth moving to when the
laptop stops being a sensible host. To enable it, put this rewrite back into
`firebase.json` before the SPA fallback:

```json
{ "source": "/api/**", "run": { "serviceId": "punchin-api", "region": "asia-south1" } }
```

**Requires the Blaze (pay-as-you-go) plan** — Hosting rewrites to Cloud Run are
not available on the free Spark plan. Cloud Run scales to zero, so idle cost is
near nothing; Cloud SQL's smallest instance is the real line item (a few
dollars a month). A managed Postgres elsewhere (Neon, Supabase) works just as
well and has a free tier — Cloud Run reaches it over TCP with `sslmode=require`.

## Option B — Split origin on a hosted backend (Render / Railway / Fly)

```
https://your-app.web.app  ──CORS──▶  https://api.yourhost.com (Render/Railway/Fly)
                                              │
                                        PostgreSQL
```

Frontend on Firebase, backend anywhere that gives you HTTPS. Costs nothing on
Firebase's side, but the refresh cookie has to be relaxed to `SameSite=None`
and CORS has to be configured — a slightly weaker posture, and Safari's ITP is
less friendly to third-party cookies.

Switching to B is three settings, no code change:

| Where | Setting |
|---|---|
| `firebase.json` | delete the `/api/**` rewrite block |
| frontend build | `VITE_API_BASE_URL=https://api.yourhost.com/api/v1` |
| backend env | `COOKIE_SAMESITE=none`, `CORS_ORIGINS=https://your-app.web.app` |

---

## Prerequisites

- A Firebase project (console.firebase.google.com)
- For Option A: Blaze plan, and the `gcloud` CLI
  (`brew install --cask google-cloud-sdk`)
- The Firebase CLI is already installed **in this repo** — use `npx firebase`
  or `npm run firebase`, no global install needed

```bash
npx firebase login
cp .firebaserc.example .firebaserc     # then put your real project id in it
```

---

## Step 1 — Database

**Cloud SQL**

```bash
gcloud sql instances create punchin-db \
  --database-version=POSTGRES_16 --cpu=1 --memory=4GB --region=asia-south1
gcloud sql databases create punchin --instance=punchin-db
gcloud sql users create punchin --instance=punchin-db --password='<strong-password>'
```

Connection string for Cloud Run (Unix socket):

```
postgresql+psycopg://punchin:<password>@/punchin?host=/cloudsql/<PROJECT>:asia-south1:punchin-db
```

**Or a managed Postgres elsewhere** — Neon, Supabase, RDS. Use:

```
postgresql+psycopg://user:password@host:5432/punchin?sslmode=require
```

Whichever you pick, the `citext` extension is created by the first migration,
so the database user needs rights to create an extension (or create it once by
hand: `CREATE EXTENSION IF NOT EXISTS citext;`).

## Step 2 — Secrets

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(64))"
```

Store it in Secret Manager rather than a plain env var:

```bash
printf '%s' '<generated-key>' | gcloud secrets create punchin-secret-key --data-file=-
printf '%s' '<database-url>'  | gcloud secrets create punchin-database-url --data-file=-
```

The app refuses to start in `production` with a default `SECRET_KEY`,
`COOKIE_SECURE=false` or `DEBUG=true` — that check is deliberate, don't work
around it.

## Step 3 — Deploy the backend to Cloud Run

```bash
cd backend
gcloud run deploy punchin-api \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --add-cloudsql-instances <PROJECT>:asia-south1:punchin-db \
  --set-secrets 'SECRET_KEY=punchin-secret-key:latest,DATABASE_URL=punchin-database-url:latest' \
  --set-env-vars 'ENVIRONMENT=production,DEBUG=false,COOKIE_SECURE=true,COOKIE_SAMESITE=lax,TRUST_PROXY_HEADERS=true,CORS_ORIGINS=' \
  --min-instances 0 --max-instances 4 --cpu 1 --memory 512Mi
```

`--allow-unauthenticated` is correct here: the service is the public API and
does its own authentication. `TRUST_PROXY_HEADERS=true` matters — without it
every request looks like it comes from the proxy and the login rate limiter
would throttle all users as one.

The service name and region must match the `run` block in `firebase.json`.

## Step 4 — Migrate and seed

Run once, from a machine that can reach the database (Cloud SQL Auth Proxy
locally, or `gcloud run jobs`):

```bash
cd backend
DATABASE_URL='<production-url>' ./.venv/bin/alembic upgrade head

DATABASE_URL='<production-url>' ./.venv/bin/python -m scripts.seed_workspace \
  --name "Main Workspace" --lat 23.0900259 --lng 72.5343615 \
  --radius 100 --accuracy 50 --timezone Asia/Kolkata

DATABASE_URL='<production-url>' ./.venv/bin/python -m scripts.create_admin \
  --name "Your Name" --email you@example.com --member-id ADM001
```

## Step 5 — Deploy the frontend

```bash
npm run deploy          # builds frontend/dist and deploys hosting
```

Test on a preview channel first if you like:

```bash
npm run deploy:preview  # temporary HTTPS URL, same build
```

## Step 6 — Verify on the phone

Open `https://<project>.web.app`. Check in order:

1. `/api/v1/health` returns `{"status":"ok"}` — the rewrite is working
2. Sign in
3. Tap **Punch in** — Safari asks for location, because the page is finally on
   a secure origin
4. Admin → Audit shows the punch with its distance and accuracy

Then **Add to Home Screen** to install the PWA.

---

## Scheduled maintenance

The auto-close and retention job should run every 15 minutes:

```bash
gcloud run jobs create punchin-maintenance \
  --source backend --region asia-south1 \
  --set-secrets 'SECRET_KEY=punchin-secret-key:latest,DATABASE_URL=punchin-database-url:latest' \
  --set-env-vars 'ENVIRONMENT=production,COOKIE_SECURE=true' \
  --command python --args '-m,app.jobs.maintenance'

gcloud scheduler jobs create http punchin-maintenance-schedule \
  --schedule '*/15 * * * *' --time-zone 'Asia/Kolkata' \
  --uri "https://asia-south1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/<PROJECT>/jobs/punchin-maintenance:run" \
  --http-method POST --oauth-service-account-email <SERVICE_ACCOUNT>
```

## Rollback

```bash
npx firebase hosting:rollback                       # frontend
gcloud run services update-traffic punchin-api \
  --to-revisions <previous-revision>=100            # backend
```

## What is NOT deployed to Firebase

No Firebase Authentication, Firestore, Storage or Functions are used. The app
has its own JWT auth and PostgreSQL; Hosting is a static CDN with a rewrite in
front of Cloud Run. Nothing in the codebase imports the Firebase SDK, and
nothing needs to.
