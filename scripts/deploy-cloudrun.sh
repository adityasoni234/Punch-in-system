#!/usr/bin/env bash
#
# Deploys the API to Cloud Run in the same Google project as Firebase Hosting.
#
# Why this one: Hosting can rewrite /api/** to a Cloud Run service, which puts
# the app and the API on ONE origin. That removes CORS entirely and lets the
# refresh cookie go back to SameSite=Lax, which is a stronger position than any
# split-origin deployment.
#
#   ./scripts/deploy-cloudrun.sh
#
# Prerequisites: gcloud CLI, the Blaze plan on the Firebase project, and a
# DATABASE_URL for a reachable PostgreSQL (Neon/Supabase free tier is fine).
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT="${GCP_PROJECT:-punchin-7c498}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE="${GCP_SERVICE:-punchin-api}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is not installed:  brew install --cask google-cloud-sdk" >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "Set DATABASE_URL to your managed PostgreSQL connection string:" >&2
  echo "  export DATABASE_URL='postgresql://user:pass@host/db?sslmode=require'" >&2
  exit 1
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

echo "Storing secrets in Secret Manager ..."
for pair in "punchin-secret-key=${SECRET_KEY}" "punchin-database-url=${DATABASE_URL}"; do
  name="${pair%%=*}"
  value="${pair#*=}"
  if gcloud secrets describe "${name}" >/dev/null 2>&1; then
    printf '%s' "${value}" | gcloud secrets versions add "${name}" --data-file=- >/dev/null
  else
    printf '%s' "${value}" | gcloud secrets create "${name}" --data-file=- >/dev/null
  fi
done

echo "Deploying ${SERVICE} to ${REGION} ..."
gcloud run deploy "${SERVICE}" \
  --source backend \
  --region "${REGION}" \
  --allow-unauthenticated \
  --set-secrets "SECRET_KEY=punchin-secret-key:latest,DATABASE_URL=punchin-database-url:latest" \
  --set-env-vars "ENVIRONMENT=production,DEBUG=false,COOKIE_SECURE=true,COOKIE_SAMESITE=lax,TRUST_PROXY_HEADERS=true,RUN_MIGRATIONS_ON_START=true,CORS_ORIGINS=,DB_POOL_SIZE=5,DB_MAX_OVERFLOW=5" \
  --min-instances 0 --max-instances 4 --cpu 1 --memory 512Mi --port 8080

cat <<MSG

Cloud Run is up. Now put the rewrite back into firebase.json, BEFORE the SPA
fallback, so the API is served from the app's own origin:

  { "source": "/api/**", "run": { "serviceId": "${SERVICE}", "region": "${REGION}" } }

Then clear the split-origin build and redeploy the PWA:

  rm -f frontend/.env.production
  npm run deploy

Same origin means no CORS and a SameSite=Lax cookie, so you can also drop
COOKIE_SAMESITE=none from the service afterwards.
MSG
