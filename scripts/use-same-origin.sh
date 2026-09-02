#!/usr/bin/env bash
#
# Switches the PWA from "API behind a tunnel" to "API on our own origin".
#
# Puts the /api/** -> Cloud Run rewrite back into firebase.json, drops the
# build-time API override, rebuilds and redeploys. After this there is no CORS
# and the refresh cookie is SameSite=Lax again.
set -euo pipefail

cd "$(dirname "$0")/.."

SERVICE="${GCP_SERVICE:-punchin-api}"
REGION="${GCP_REGION:-asia-south1}"

python3 - "${SERVICE}" "${REGION}" <<'PY'
import json, pathlib, sys

service, region = sys.argv[1], sys.argv[2]
path = pathlib.Path("firebase.json")
config = json.loads(path.read_text())
hosting = config["hosting"]

rewrite = {"source": "/api/**", "run": {"serviceId": service, "region": region}}
others = [r for r in hosting.get("rewrites", []) if r.get("source") != "/api/**"]

# The API rewrite must come before the SPA fallback, or ** swallows /api first.
hosting["rewrites"] = [rewrite] + others
path.write_text(json.dumps(config, indent=2) + "\n")
print("firebase.json rewrites:", [r["source"] for r in hosting["rewrites"]])
PY

# A build-time API base URL would keep pointing the app at the old tunnel.
rm -f frontend/.env.production
echo "Removed frontend/.env.production (same origin needs no override)"

npm --prefix frontend run build
npx firebase deploy --only hosting

cat <<'MSG'

Same origin is live. Verify:

  curl -s https://punchin-7c498.web.app/api/v1/health

That must return JSON, not HTML. Once it does, the tunnel and the laptop
backend are no longer part of the picture and can be shut down.
MSG
