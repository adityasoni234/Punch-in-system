#!/usr/bin/env bash
#
# Exposes the backend running on this laptop over HTTPS, so a Firebase-hosted
# frontend can reach it.
#
# WHY THIS IS NEEDED: the Firebase app is served over HTTPS. A page on HTTPS
# cannot call an http:// address -- browsers block it as mixed content -- so
# the laptop API has to be reachable over HTTPS too. This is also what makes
# geolocation work, since that needs a secure context.
#
# WHAT IT DOES: opens a public HTTPS URL that forwards to 127.0.0.1:8000 on
# this machine. While it runs, ANYONE WHO LEARNS THE URL CAN REACH YOUR API
# over the internet. The API still requires authentication and is rate
# limited, but it is exposed. Stop the tunnel (Ctrl-C) when you are done.
#
# The free quick-tunnel URL changes every restart. For a stable address, use a
# named tunnel on a domain you control:
#   cloudflared tunnel login && cloudflared tunnel create punchin-api
set -euo pipefail

PORT="${1:-8000}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed:  brew install cloudflared" >&2
  exit 1
fi

if ! curl -sf "http://127.0.0.1:${PORT}/api/v1/health" >/dev/null; then
  echo "No backend answering on http://127.0.0.1:${PORT}" >&2
  echo "Start it first:" >&2
  echo "  cd backend && ./.venv/bin/uvicorn app.main:app --port ${PORT}" >&2
  exit 1
fi

cat <<'MSG'
Opening a public HTTPS tunnel to your local API.

When the URL appears (https://something.trycloudflare.com):

  1. backend/.env      CORS_ORIGINS=https://YOUR_PROJECT.web.app
                       COOKIE_SECURE=true
                       COOKIE_SAMESITE=none
                       TRUST_PROXY_HEADERS=true
                       ...then restart uvicorn

  2. frontend/.env.production
                       VITE_API_BASE_URL=https://<that-url>/api/v1

  3. npm run deploy    (rebuilds and redeploys the Firebase frontend)

The URL changes every time this script restarts, so step 2 and 3 have to be
repeated each time. Ctrl-C closes the tunnel and takes the API offline.

MSG

exec cloudflared tunnel --url "http://127.0.0.1:${PORT}"
