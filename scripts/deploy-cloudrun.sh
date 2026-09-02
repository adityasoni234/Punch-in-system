#!/usr/bin/env bash
#
# Deploys the API to Cloud Run, backed by Cloud SQL, in the same Google project
# as Firebase Hosting.
#
# Why this shape: Hosting can rewrite /api/** to a Cloud Run service, which
# puts the app and the API on ONE origin. That removes CORS entirely and lets
# the refresh cookie go back to SameSite=Lax -- a stronger position than any
# split-origin deployment, and no laptop or tunnel in the path.
#
#   ./scripts/deploy-cloudrun.sh
#
# Prerequisites:
#   * gcloud CLI, authenticated:      gcloud auth login
#   * Blaze (pay-as-you-go) billing on the project
#   * a Cloud SQL instance:           ./scripts/create-cloudsql.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT="${GCP_PROJECT:-punchin-7c498}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE="${GCP_SERVICE:-punchin-api}"
INSTANCE="${CLOUDSQL_INSTANCE:-punchin-db}"
DB_NAME="${DB_NAME:-punchin}"
DB_USER="${DB_USER:-punchin}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is not installed:  brew install --cask google-cloud-sdk" >&2
  exit 1
fi

# Two ways to reach a database, and the choice is purely about cost:
#
#   DATABASE_URL set  -> an external managed Postgres (Neon, Supabase). Free
#                        tiers exist, reached over TLS. Nothing to provision
#                        here, and no Cloud SQL bill.
#   DATABASE_URL unset-> Cloud SQL over the socket Cloud Run mounts. Tighter
#                        integration, but the instance bills continuously.
SQL_FLAGS=()
if [ -n "${DATABASE_URL:-}" ]; then
  echo "Using the external database from DATABASE_URL"
else
  if [ -z "${DB_PASSWORD:-}" ]; then
    echo "Set one of these first:" >&2
    echo "  export DATABASE_URL='postgresql://user:pass@host/db?sslmode=require'   # free tier" >&2
    echo "  export DB_PASSWORD='...'   # the password ./scripts/create-cloudsql.sh printed" >&2
    exit 1
  fi
  CONNECTION_NAME="${PROJECT}:${REGION}:${INSTANCE}"
  # Cloud Run mounts the Cloud SQL socket at /cloudsql/<connection name>, so
  # the host is a directory path rather than a hostname.
  DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"
  SQL_FLAGS=(--add-cloudsql-instances "${CONNECTION_NAME}")
fi

# Reuse the existing signing key so live sessions survive the move.
if [ -s backend/.secret_key ]; then
  SECRET_KEY="$(tr -d '\n' < backend/.secret_key)"
else
  SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(64))')"
  printf '%s' "${SECRET_KEY}" > backend/.secret_key
  chmod 600 backend/.secret_key
  echo "Generated a new SECRET_KEY (backend/.secret_key); existing sessions end."
fi

gcloud config set project "${PROJECT}" >/dev/null

# Enabling any API fails with a wall of JSON if billing is off, and the real
# message is buried in it. Check first and say it plainly.
if ! gcloud services list --available --filter="name:run.googleapis.com" \
     --format='value(name)' >/dev/null 2>&1; then
  :
fi
BILLING="$(gcloud beta billing projects describe "${PROJECT}" \
  --format='value(billingEnabled)' 2>/dev/null || echo "")"
if [ "${BILLING}" = "False" ]; then
  cat >&2 <<MSG

Billing is not enabled on ${PROJECT}, so Cloud Run cannot be used yet.

Open this and upgrade to the Blaze (pay-as-you-go) plan:

  https://console.firebase.google.com/project/${PROJECT}/usage/details

Blaze needs a card on file, but this deployment stays inside the always-free
tiers: Cloud Run gives 2 million requests a month and the database is Neon's
free plan. Set a budget alert of a dollar or two while you are in there.

Then run this script again.

MSG
  exit 1
fi

echo "Enabling the APIs this needs ..."
gcloud services enable run.googleapis.com secretmanager.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com >/dev/null

echo "Storing secrets in Secret Manager ..."
store_secret() {
  local name="$1" value="$2"
  if gcloud secrets describe "${name}" >/dev/null 2>&1; then
    printf '%s' "${value}" | gcloud secrets versions add "${name}" --data-file=- >/dev/null
  else
    printf '%s' "${value}" | gcloud secrets create "${name}" --data-file=- >/dev/null
  fi
}
store_secret punchin-secret-key "${SECRET_KEY}"
store_secret punchin-database-url "${DATABASE_URL}"

echo "Deploying ${SERVICE} to ${REGION} ..."
# CORS_ORIGINS is empty and the cookie is Lax because Hosting serves the API
# from the app's own origin. --allow-unauthenticated is correct: this is the
# public API and it does its own authentication.
gcloud run deploy "${SERVICE}" \
  --source backend \
  --region "${REGION}" \
  --allow-unauthenticated \
  "${SQL_FLAGS[@]}" \
  --set-secrets "SECRET_KEY=punchin-secret-key:latest,DATABASE_URL=punchin-database-url:latest" \
  --set-env-vars "ENVIRONMENT=production,DEBUG=false,COOKIE_SECURE=true,COOKIE_SAMESITE=lax,TRUST_PROXY_HEADERS=true,RUN_MIGRATIONS_ON_START=true,CORS_ORIGINS=,DB_POOL_SIZE=5,DB_MAX_OVERFLOW=5" \
  --min-instances 0 --max-instances 4 --cpu 1 --memory 512Mi --port 8080

URL="$(gcloud run services describe "${SERVICE}" --region "${REGION}" --format 'value(status.url)')"
echo
echo "Service URL: ${URL}"
curl -sf --max-time 30 "${URL}/api/v1/health" && echo || echo "(health check did not answer yet; check the logs)"

cat <<MSG

The schema was applied at boot (RUN_MIGRATIONS_ON_START). Next:

  1. Create the workspace and your admin account on the new database:
       ./scripts/bootstrap-remote.sh

  2. Point Hosting at Cloud Run and go same-origin:
       ./scripts/use-same-origin.sh

MSG
