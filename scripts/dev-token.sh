#!/usr/bin/env bash
# Print an access token for a local Keycloak test user (alice = finance-support, bob = agent-user only).
# Dev only: uses the password grant of the local agent-portal client.
set -euo pipefail
user=${1:-alice}
curl -sf -X POST http://localhost:8180/realms/agents/protocol/openid-connect/token \
  -d grant_type=password -d client_id=agent-portal -d client_secret=dev-only-agent-portal-secret \
  -d "username=$user" -d "password=$user" -d scope=openid \
  | python3 -I -c 'import json,sys;print(json.load(sys.stdin)["access_token"])'
