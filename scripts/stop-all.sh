#!/usr/bin/env bash
# Stops the API and the tunnel started by start-all.sh.
set -uo pipefail
cd "$(dirname "$0")/.."

for name in api tunnel; do
  pid_file=".run/${name}.pid"
  if [ -f "${pid_file}" ]; then
    pid="$(cat "${pid_file}")"
    if kill "${pid}" 2>/dev/null; then
      echo "Stopped ${name} (pid ${pid})"
    else
      echo "${name} was not running"
    fi
    rm -f "${pid_file}"
  fi
done

# Anything started by hand outside the scripts.
pkill -f "cloudflared tunnel --url" 2>/dev/null && echo "Stopped stray cloudflared" || true
rm -f .tunnel-url
echo "The public tunnel is closed; the API is no longer reachable from the internet."
