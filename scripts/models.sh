#!/usr/bin/env bash
# Models of the Ollama the platform uses, as the containers see it (host.docker.internal:11434).
# `curl localhost:11434` on the Mac can reach a different Ollama (e.g. docker-lab's container).
# In the gateway UI, models are named ollama/<name> (e.g. ollama/qwen3:8b).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T langflow-runtime python -c '
import json, urllib.request
tags = json.load(urllib.request.urlopen("http://host.docker.internal:11434/api/tags", timeout=10))
for m in tags["models"]: print(m["name"])'
