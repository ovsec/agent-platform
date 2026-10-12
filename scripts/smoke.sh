#!/usr/bin/env bash
# P0 check: a standard AG-UI RunAgentInput through the gateway returns an AG-UI event stream.
#   ./scripts/smoke.sh [agent-slug] [user]
set -euo pipefail
cd "$(dirname "$0")"
slug=${1:-hitl-demo}; user=${2:-bob}
token=$(./dev-token.sh "$user")
thread="smoke-$(date +%s)"
curl -sN -X POST "http://localhost:4100/agents/$slug/run" \
  -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -H 'Accept: text/event-stream' \
  -H "x-agui-thread-id: $thread" \
  -d "{\"threadId\":\"$thread\",\"runId\":\"r1\",\"messages\":[{\"id\":\"m1\",\"role\":\"user\",\"content\":\"Reply with the single word PONG\"}],\"tools\":[],\"context\":[],\"state\":{},\"forwardedProps\":{}}" \
  -w '\nHTTP %{http_code}\n'
