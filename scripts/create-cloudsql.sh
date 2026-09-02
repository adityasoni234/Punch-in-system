#!/usr/bin/env bash
#
# Creates the Cloud SQL PostgreSQL instance the API will use.
#
# Run once. It prints a generated database password -- keep it, the deploy
# script needs it as DB_PASSWORD.
#
# Cost note: unlike Cloud Run, a Cloud SQL instance does not scale to zero. The
# smallest tier bills continuously (roughly $8-10/month). That is the price of
# the tight integration and private socket access.
set -euo pipefail

PROJECT="${GCP_PROJECT:-punchin-7c498}"
REGION="${GCP_REGION:-asia-south1}"
INSTANCE="${CLOUDSQL_INSTANCE:-punchin-db}"
DB_NAME="${DB_NAME:-punchin}"
DB_USER="${DB_USER:-punchin}"
TIER="${CLOUDSQL_TIER:-db-f1-micro}"

command -v gcloud >/dev/null 2>&1 || {
  echo "gcloud is not installed:  brew install --cask google-cloud-sdk" >&2
  exit 1
}

gcloud config set project "${PROJECT}" >/dev/null
gcloud services enable sqladmin.googleapis.com >/dev/null

if gcloud sql instances describe "${INSTANCE}" >/dev/null 2>&1; then
  echo "Instance ${INSTANCE} already exists; leaving it alone."
else
  echo "Creating ${INSTANCE} (this takes several minutes) ..."
  gcloud sql instances create "${INSTANCE}" \
    --database-version=POSTGRES_16 \
    --tier="${TIER}" \
    --region="${REGION}" \
    --storage-size=10GB \
    --storage-auto-increase \
    --backup-start-time=19:00
fi

gcloud sql databases describe "${DB_NAME}" --instance="${INSTANCE}" >/dev/null 2>&1 \
  || gcloud sql databases create "${DB_NAME}" --instance="${INSTANCE}"

DB_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
if gcloud sql users list --instance="${INSTANCE}" --format='value(name)' | grep -qx "${DB_USER}"; then
  gcloud sql users set-password "${DB_USER}" --instance="${INSTANCE}" --password="${DB_PASSWORD}"
  echo "Reset the password for the existing user ${DB_USER}."
else
  gcloud sql users create "${DB_USER}" --instance="${INSTANCE}" --password="${DB_PASSWORD}"
fi

# The first migration creates the citext extension, which needs elevated rights.
gcloud sql users set-password postgres --instance="${INSTANCE}" \
  --password="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')" >/dev/null 2>&1 || true
gcloud sql instances patch "${INSTANCE}" --database-flags=cloudsql.iam_authentication=off >/dev/null 2>&1 || true

cat <<MSG

Cloud SQL is ready.

  instance     ${PROJECT}:${REGION}:${INSTANCE}
  database     ${DB_NAME}
  user         ${DB_USER}
  password     ${DB_PASSWORD}

Save that password somewhere safe, then:

  export DB_PASSWORD='${DB_PASSWORD}'
  ./scripts/deploy-cloudrun.sh

MSG
