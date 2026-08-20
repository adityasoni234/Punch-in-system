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

URL_FILE=".tunnel-url"
rm -f "${URL_FILE}"

echo "Opening a public HTTPS tunnel to http://127.0.0.1:${PORT} ..."
echo "Ctrl-C closes it and takes the API offline."
echo

# cloudflared prints the URL in a banner. Watch for it, record it, and print
# the exact command to run next -- copying a placeholder out of documentation
# is how this goes wrong.
cloudflared tunnel --url "http://127.0.0.1:${PORT}" 2>&1 | while IFS= read -r line; do
  printf '%s\n' "${line}"
  case "${line}" in
    *trycloudflare.com*)
      url="$(printf '%s' "${line}" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)"
      if [ -n "${url}" ] && [ ! -f "${URL_FILE}" ]; then
        printf '%s' "${url}" > "${URL_FILE}"
        cat <<BANNER

  ============================================================
   Tunnel is live:  ${url}

   Now run this in another terminal, exactly as written:

       npm run deploy:api

   (it reads the URL above from .tunnel-url -- nothing to paste)
  ============================================================

BANNER
      fi
      ;;
  esac
done
