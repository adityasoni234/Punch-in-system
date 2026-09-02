#!/usr/bin/env bash
#
# Brings the whole thing up with one command: API, HTTPS tunnel, and a deploy
# of the PWA built against that tunnel.
#
# The three pieces are long-running, and running them in one terminal means
# Ctrl-C (or just starting the next command) kills the previous one. This
# starts the first two detached, waits for each to be genuinely ready, then
# deploys.
#
#   ./scripts/start-all.sh        bring everything up
#   ./scripts/stop-all.sh         take it back down
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-${API_PORT:-8000}}"

# Read only API_PORT out of .env. Sourcing the whole file would be unsafe: it
# holds a database URL containing "&", which a shell would treat as a job
# control operator.
if [ -f .env ]; then
  ENV_PORT="$(grep -E '^API_PORT=' .env | tail -1 | cut -d= -f2 | tr -d ' "')"
  [ -n "${ENV_PORT}" ] && PORT="${PORT:-${ENV_PORT}}"
fi

LOG_DIR=".run"
mkdir -p "${LOG_DIR}"
API_LOG="${LOG_DIR}/api.log"
TUNNEL_LOG="${LOG_DIR}/tunnel.log"

# ---------------------------------------------------------------- the API ---
if curl -sf --max-time 3 "http://127.0.0.1:${PORT}/api/v1/health" 2>/dev/null | grep -q punch-in-system; then
  # Either the container (npm run docker:up) or a local uvicorn. Either way
  # something healthy is already answering, so leave it alone.
  echo "API already running on :${PORT}"
else
  echo "Starting the API on :${PORT} ..."
  # uvicorn must run from backend/ so it resolves app.main and reads .env there.
  # nohup + disown so it survives this shell closing or a Ctrl-C.
  (
    cd backend
    nohup .venv/bin/uvicorn app.main:app --port "${PORT}" > "../${API_LOG}" 2>&1 &
    echo $! > "../${LOG_DIR}/api.pid"
    disown $! 2>/dev/null || true
  )

  for _ in $(seq 1 30); do
    if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/api/v1/health" 2>/dev/null | grep -q punch-in-system; then
      break
    fi
    sleep 1
  done

  if ! curl -sf --max-time 3 "http://127.0.0.1:${PORT}/api/v1/health" 2>/dev/null | grep -q punch-in-system; then
    echo "The API did not come up. Last lines of ${API_LOG}:" >&2
    tail -20 "${API_LOG}" >&2
    exit 1
  fi
fi
echo "  API healthy"

# ------------------------------------------------------------- the tunnel ---
rm -f .tunnel-url

# Each run mints a new hostname, so an earlier tunnel is now pointing at an
# address nothing is built against. Close it rather than leaving orphans that
# hold the API open to the internet.
if pgrep -f "cloudflared tunnel --url" >/dev/null 2>&1; then
  echo "Closing the previous tunnel ..."
  pkill -f "cloudflared tunnel --url" || true
  sleep 1
fi

echo "Opening the HTTPS tunnel ..."
nohup cloudflared tunnel --url "http://127.0.0.1:${PORT}" > "${TUNNEL_LOG}" 2>&1 &
TUNNEL_PID=$!
disown "${TUNNEL_PID}" 2>/dev/null || true
echo "${TUNNEL_PID}" > "${LOG_DIR}/tunnel.pid"

URL=""
for _ in $(seq 1 40); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "${TUNNEL_LOG}" 2>/dev/null | head -1 || true)"
  [ -n "${URL}" ] && break
  sleep 1
done

if [ -z "${URL}" ]; then
  echo "The tunnel did not report a URL. Last lines of ${TUNNEL_LOG}:" >&2
  tail -20 "${TUNNEL_LOG}" >&2
  exit 1
fi
printf '%s' "${URL}" > .tunnel-url
echo "  Tunnel live: ${URL}"

# A brand new quick-tunnel hostname often takes a minute or two to resolve.
echo "  waiting for the hostname to resolve ..."
for _ in $(seq 1 45); do
  curl -sf --max-time 5 "${URL}/api/v1/health" 2>/dev/null | grep -q punch-in-system && break
  sleep 4
done

# ------------------------------------------------------------- the deploy ---
echo
./scripts/deploy-firebase.sh "${URL}"

cat <<MSG

Everything is up:

  API      http://127.0.0.1:${PORT}      (log: ${API_LOG})
  Tunnel   ${URL}   (log: ${TUNNEL_LOG})
  App      https://punchin-7c498.web.app

Both run in the background, so this terminal is free and Ctrl-C will not kill
them. Stop them with:

  ./scripts/stop-all.sh

MSG
