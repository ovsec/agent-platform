#!/usr/bin/env bash
# Create a Langflow runtime API key for the gateway and store it in .secrets/langflow-runtime.key.
set -euo pipefail
cd "$(dirname "$0")/.."
source .env
RT=http://localhost:7880
until curl -sf "$RT/health" >/dev/null; do echo "waiting for langflow-runtime..."; sleep 3; done
token=$(curl -sf -X POST "$RT/api/v1/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode username=runtime-admin --data-urlencode "password=$LANGFLOW_RUNTIME_ADMIN_PASSWORD" \
  | python3 -I -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')
curl -sf -X POST "$RT/api/v1/api_key/" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  -d '{"name":"agentgateway"}' | python3 -I -c 'import json,sys;print(json.load(sys.stdin)["api_key"],end="")' \
  > .secrets/langflow-runtime.key
chmod 600 .secrets/langflow-runtime.key
echo "wrote .secrets/langflow-runtime.key"
# One-time setup: the gateway started with an empty key file; restart once so it uses the new key
docker compose restart agentgateway >/dev/null && echo "restarted agentgateway"
