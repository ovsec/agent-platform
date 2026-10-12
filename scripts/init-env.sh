#!/usr/bin/env bash
# Create .env from .env.example with random secrets (no-op if .env exists).
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] && { echo ".env exists, leaving it alone"; exit 0; }
while IFS= read -r line; do
  if [[ $line =~ ^[A-Z_]+_URL=$ ]]; then echo "$line"           # empty = localhost default
  elif [[ $line =~ ^(BUILDER_LOGIN_COOKIE_SECRET)=$ ]]; then   # oauth2-proxy: exactly 32 bytes
    echo "${BASH_REMATCH[1]}=$(openssl rand -hex 16)"
  elif [[ $line =~ ^([A-Z_]+_SECRET_KEY)=$ ]]; then      # Langflow wants a Fernet key: 32 bytes, url-safe base64
    echo "${BASH_REMATCH[1]}=$(openssl rand -base64 32 | tr '+/' '-_')"
  elif [[ $line =~ ^([A-Z_]+_COOKIE_SECRET)=$ ]]; then   # agentgateway OIDC cookie key: 32 bytes, hex
    echo "${BASH_REMATCH[1]}=$(openssl rand -hex 32)"
  elif [[ $line =~ ^([A-Z_]+)=$ ]]; then echo "${BASH_REMATCH[1]}=$(openssl rand -hex 24)"
  else echo "$line"; fi
done < .env.example > .env
chmod 600 .env
echo "wrote .env"
