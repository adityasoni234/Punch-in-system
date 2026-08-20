#!/usr/bin/env bash
#
# Switches backend/.env between the local-development and Firebase profiles.
#
# Copying the .example files by hand is a footgun: they ship with an empty
# SECRET_KEY, so a stray `cp` silently wipes the real key and the app then
# refuses to start. This script keeps the key in backend/.secret_key (git
# ignored, generated once) and stamps it into whichever profile you select, so
# the key survives every switch -- which matters, because changing it signs
# every user out.
#
#   ./scripts/use-env.sh dev        local development on http://localhost:5173
#   ./scripts/use-env.sh firebase   PWA on Firebase, API here behind a tunnel
set -euo pipefail

cd "$(dirname "$0")/../backend"

PROFILE="${1:-}"
KEY_FILE=".secret_key"

case "${PROFILE}" in
  dev | development) TEMPLATE=".env.example" ;;
  firebase | prod | production) TEMPLATE=".env.firebase.example" ;;
  *)
    echo "usage: $0 dev|firebase" >&2
    exit 1
    ;;
esac

if [ ! -f "${TEMPLATE}" ]; then
  echo "Missing ${TEMPLATE}" >&2
  exit 1
fi

# The signing key lives outside the profile files so it is never clobbered.
if [ ! -s "${KEY_FILE}" ]; then
  if [ -f .env ] && grep -q '^SECRET_KEY=..*' .env; then
    grep '^SECRET_KEY=' .env | head -1 | cut -d= -f2- > "${KEY_FILE}"
    echo "Recovered the existing SECRET_KEY from backend/.env"
  else
    ./.venv/bin/python -c "import secrets;print(secrets.token_urlsafe(64))" > "${KEY_FILE}"
    echo "Generated a new SECRET_KEY (backend/.secret_key)"
    echo "Note: any existing session is now invalid; sign in again."
  fi
  chmod 600 "${KEY_FILE}"
fi

SECRET_KEY="$(tr -d '\n' < "${KEY_FILE}")"
if [ -z "${SECRET_KEY}" ]; then
  echo "backend/.secret_key is empty -- delete it and re-run" >&2
  exit 1
fi

if [ -f .env ]; then
  cp .env ".env.previous"
fi

python3 - "${TEMPLATE}" "${SECRET_KEY}" <<'PY'
import pathlib, sys
template, key = sys.argv[1], sys.argv[2]
lines = pathlib.Path(template).read_text().splitlines(keepends=True)
out = []
seen = False
for line in lines:
    if line.startswith("SECRET_KEY="):
        out.append(f"SECRET_KEY={key}\n")
        seen = True
    else:
        out.append(line)
if not seen:
    out.append(f"\nSECRET_KEY={key}\n")
pathlib.Path(".env").write_text("".join(out))
PY

ENVIRONMENT="$(grep '^ENVIRONMENT=' .env | cut -d= -f2- || echo '?')"
CORS="$(grep '^CORS_ORIGINS=' .env | cut -d= -f2- || echo '')"

cat <<MSG

backend/.env is now the '${PROFILE}' profile.
  ENVIRONMENT   ${ENVIRONMENT}
  CORS_ORIGINS  ${CORS:-<same-origin, none needed>}
  SECRET_KEY    set (${#SECRET_KEY} chars, from backend/.secret_key)

The previous file was kept as backend/.env.previous.

Restart the API for this to take effect:
  cd backend && ./.venv/bin/uvicorn app.main:app --port 8000
MSG
