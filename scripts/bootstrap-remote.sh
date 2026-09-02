#!/usr/bin/env bash
#
# Seeds the workspace and the first administrator on the Cloud SQL database.
#
# Runs the same container as the API as a one-off Cloud Run job, so the
# database is reached over the private Cloud SQL socket. Nothing has to be
# exposed to the internet and no proxy has to be installed locally.
#
#   ./scripts/bootstrap-remote.sh                      # workspace only
#   ./scripts/bootstrap-remote.sh --admin "Your Name" you@example.com ADM001
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT="${GCP_PROJECT:-punchin-7c498}"
REGION="${GCP_REGION:-asia-south1}"
INSTANCE="${CLOUDSQL_INSTANCE:-punchin-db}"
JOB="${GCP_JOB:-punchin-bootstrap}"

WS_NAME="${WORKSPACE_NAME:-Main Workspace}"
WS_LAT="${WORKSPACE_LAT:-23.0900259}"
WS_LNG="${WORKSPACE_LNG:-72.5343615}"
WS_RADIUS="${WORKSPACE_RADIUS:-100}"
WS_ACCURACY="${WORKSPACE_ACCURACY:-50}"
WS_TZ="${WORKSPACE_TZ:-Asia/Kolkata}"

command -v gcloud >/dev/null 2>&1 || {
  echo "gcloud is not installed:  brew install --cask google-cloud-sdk" >&2
  exit 1
}

gcloud config set project "${PROJECT}" >/dev/null

# Only mount the Cloud SQL socket when Cloud SQL is actually in use; with an
# external free-tier database the job reaches it over TLS like any other host.
SQL_FLAGS=()
if [ -z "${DATABASE_URL:-}" ]; then
  SQL_FLAGS=(--set-cloudsql-instances "${PROJECT}:${REGION}:${INSTANCE}")
fi

run_job() {
  local description="$1"
  shift
  echo
  echo "--- ${description} ---"
  if gcloud run jobs describe "${JOB}" --region "${REGION}" >/dev/null 2>&1; then
    gcloud run jobs update "${JOB}" --region "${REGION}" \
      --args "$1" >/dev/null
  else
    gcloud run jobs create "${JOB}" \
      --region "${REGION}" \
      --source backend \
      "${SQL_FLAGS[@]}" \
      --set-secrets "SECRET_KEY=punchin-secret-key:latest,DATABASE_URL=punchin-database-url:latest" \
      --set-env-vars "ENVIRONMENT=production,DEBUG=false,COOKIE_SECURE=true" \
      --command python \
      --args "$1" \
      --max-retries 0 \
      --task-timeout 10m >/dev/null
  fi
  gcloud run jobs execute "${JOB}" --region "${REGION}" --wait
  echo "Output:"
  gcloud logging read \
    "resource.type=cloud_run_job AND resource.labels.job_name=${JOB}" \
    --limit 30 --format 'value(textPayload)' --freshness 5m | tac
}

WS_ARGS="-m,scripts.seed_workspace,--name,${WS_NAME},--lat,${WS_LAT},--lng,${WS_LNG}"
WS_ARGS="${WS_ARGS},--radius,${WS_RADIUS},--accuracy,${WS_ACCURACY},--timezone,${WS_TZ}"
run_job "Seeding the workspace" "${WS_ARGS}"

if [ "${1:-}" = "--admin" ]; then
  ADMIN_NAME="${2:?admin name required}"
  ADMIN_EMAIL="${3:?admin email required}"
  ADMIN_MEMBER="${4:?admin member id required}"
  run_job "Creating the administrator" \
    "-m,scripts.create_admin,--name,${ADMIN_NAME},--email,${ADMIN_EMAIL},--member-id,${ADMIN_MEMBER},--generate-password"
  echo
  echo "The temporary password is in the output above. It is shown once."
fi
