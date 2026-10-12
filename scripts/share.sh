#!/usr/bin/env bash
# Share the local stack by URL, over Tailscale. What people can *use*: the Keycloak roles of their login.
#
#   ./scripts/share.sh on public       anyone with the link (Tailscale Funnel, internet); hardened, see below
#   ./scripts/share.sh on tailnet      only devices in your tailnet / people you share the machine with
#   ./scripts/share.sh off             back to localhost only
#   ./scripts/share.sh status
#   ./scripts/share.sh user <username> <tester|developer|admin> [extra-role...]   create a login, one-off password
#
#   audience    roles                                    can use
#   tester      agent-user (+ extras, e.g. finance-support)  portal
#   developer   + agent-developer                        portal, Langflow Builder
#   admin       + agent-developer, agent-admin           portal, Builder, gateway admin UI
#
# Addresses (Funnel allows only ports 443, 8443, 10000):
#   https://<machine>.ts.net          portal, and Keycloak's sign-in pages (/realms, /resources) on the same host
#   https://<machine>.ts.net:8443     Langflow Builder (login)
#   https://<machine>.ts.net:10000    gateway admin UI (login)
# Never shared: the Keycloak admin console (http://localhost:8180/admin on this machine only), the Builder without
# login (:7870), the runtime, Postgres, the gateway's agent and services ports.
# Public mode also disables the test users whose password is their name and turns on brute-force protection.
set -euo pipefail
cd "$(dirname "$0")/.."

die() { echo "error: $*" >&2; exit 1; }
env_get() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true; }
env_set() {  # KEY VALUE: replace or append in .env
  if grep -qE "^$1=" .env; then
    local tmp; tmp=$(mktemp); awk -v k="$1" -v v="$2" -F= '$1==k{print k"="v; next}{print}' .env > "$tmp"
    cat "$tmp" > .env && rm "$tmp"
  else
    printf '%s=%s\n' "$1" "$2" >> .env
  fi
}

# https-port | mount path | local port | local path
ROUTES=("443|/|3100|" "443|/realms|8180|/realms" "443|/resources|8180|/resources" "8443|/|7871|" "10000|/|4101|")
PORTS=(443 8443 10000 4101 7871)   # everything this script ever published (incl. older layouts), for `off`
TEST_USERS=(alice bob dev admin)    # password = username: never reachable from the internet
URL_VARS=(PORTAL_URL IDP_URL GATEWAY_UI_URL BUILDER_URL)
LOCAL=(PORTAL_URL=http://localhost:3100 IDP_URL=http://localhost:8180 GATEWAY_UI_URL=http://localhost:4101
       BUILDER_URL=http://localhost:7871)
url() {  # current public URL of a service (.env), else its localhost URL
  local v; v=$(env_get "$1")
  if [[ -n $v ]]; then echo "$v"; else printf '%s\n' "${LOCAL[@]}" | grep "^$1=" | cut -d= -f2-; fi
}

unpublish() {
  for p in "${PORTS[@]}"; do
    tailscale funnel --https="$p" off >/dev/null 2>&1 || true
    tailscale serve --https="$p" off >/dev/null 2>&1 || true
  done
}

publish() {  # serve (tailnet) | funnel (internet)
  local how=$1 port path lport lpath
  for r in "${ROUTES[@]}"; do
    IFS='|' read -r port path lport lpath <<< "$r"
    if [[ $path == / ]]; then
      tailscale "$how" --bg --https="$port" "http://127.0.0.1:$lport$lpath" >/dev/null
    else
      tailscale "$how" --bg --https="$port" --set-path="$path" "http://127.0.0.1:$lport$lpath" >/dev/null
    fi
  done
}

kc() { docker compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/kcadm.config; }
kc_login() {
  kc config credentials --server http://localhost:8080 --realm master --user admin \
    --password "$(env_get KEYCLOAK_ADMIN_PASSWORD)" >/dev/null 2>&1 || die "Keycloak admin login failed"
}
client_id() { kc get clients -r agents -q "clientId=$1" --fields id | jq -r '.[0].id // empty'; }

# Bring the running realm in line with infra/keycloak/realm-agents.json additions and the current public URLs.
sync_realm() {
  kc_login
  kc get roles/agent-developer -r agents >/dev/null 2>&1 ||
    kc create roles -r agents -s name=agent-developer -s 'description=Builds agents: Langflow Builder access'
  if [[ -z $(client_id langflow-builder) ]]; then
    jq '.clients[] | select(.clientId == "langflow-builder")' infra/keycloak/realm-agents.json |
      kc create clients -r agents -f - >/dev/null
  fi
  local portal gwui builder
  portal=$(url PORTAL_URL) gwui=$(url GATEWAY_UI_URL) builder=$(url BUILDER_URL)
  set_redirects agent-portal "$portal/*" "$portal" "$portal/*" "http://localhost:3100"
  set_redirects agent-gateway-ui "$gwui/oauth/callback" "$gwui" "" "http://localhost:4101"
  set_redirects langflow-builder "$builder/oauth2/callback" "$builder" "" "http://localhost:7871"
}

set_redirects() {  # client redirect origin post-logout localhost-origin: allow the public and the localhost URLs
  local id; id=$(client_id "$1")
  [[ -n $id ]] || die "client $1 missing in realm agents"
  local local_redirect=${2/$3/$5}
  kc get "clients/$id" -r agents |
    jq --arg r "$2" --arg o "$3" --arg lr "$local_redirect" --arg lo "$5" --arg pl "$4" '
      .redirectUris = ([$r, $lr] | unique) | .webOrigins = ([$o, $lo] | unique)
      | if $pl != "" then .attributes["post.logout.redirect.uris"] = ([$pl, ($lr)] | unique | join("##")) else . end' |
    kc update "clients/$id" -r agents -f -
}

test_users() {  # enable | disable
  local id
  for u in "${TEST_USERS[@]}"; do
    id=$(kc get users -r agents -q "username=$u" -q exact=true --fields id | jq -r '.[0].id // empty')
    if [[ -n $id ]]; then kc update "users/$id" -r agents -s "enabled=$([[ $1 == enable ]] && echo true || echo false)"; fi
  done
  echo "test users ${TEST_USERS[*]}: ${1}d"
}

wait_keycloak() {
  for _ in $(seq 60); do
    curl -sf -o /dev/null http://localhost:8180/realms/agents && return
    sleep 2
  done
  die "Keycloak did not come up"
}

apply() {
  # services that read the public URLs at start; the gateway reads them from the generated config
  docker compose up -d keycloak portal builder-login >/dev/null
  wait_keycloak
  sync_realm
  uv run -q scripts/gen-gateway.py
  docker compose restart agentgateway >/dev/null
  echo "applied; everyone has to sign in again (tokens now carry the new issuer)"
}

case "${1:-}" in
  on)
    mode=${2:-}
    [[ $mode == public || $mode == tailnet ]] || die "usage: $0 on public|tailnet"
    command -v tailscale >/dev/null || die "tailscale not installed"
    host=$(tailscale status --json | jq -r '.Self.DNSName' | sed 's/\.$//')
    [[ -n $host && $host != null ]] || die "tailscale is not connected"
    unpublish
    if [[ $mode == public ]]; then publish funnel; else publish serve; fi
    env_set PORTAL_URL "https://$host"
    env_set IDP_URL "https://$host"
    env_set BUILDER_URL "https://$host:8443"
    env_set GATEWAY_UI_URL "https://$host:10000"
    env_set SHARE_MODE "$mode"
    apply
    kc update realms/agents -s bruteForceProtected=true
    if [[ $mode == public ]]; then test_users disable; else test_users enable; fi
    "$0" status
    ;;

  off)
    unpublish
    for v in "${URL_VARS[@]}"; do env_set "$v" ""; done
    env_set SHARE_MODE ""
    apply
    test_users enable
    echo "localhost only"
    ;;

  status)
    echo "  mode: $(env_get SHARE_MODE | grep . || echo 'off (localhost)')"
    for v in "${URL_VARS[@]}"; do printf '  %-15s %s\n' "$v" "$(url "$v")"; done
    tailscale funnel status 2>/dev/null | sed 's/^/  /' || true
    ;;

  user)
    [[ $# -ge 3 ]] || die "usage: $0 user <username> <tester|developer|admin> [extra-role...]"
    user=$2 audience=$3; shift 3
    case $audience in
      tester) roles=(agent-user) ;;
      developer) roles=(agent-user agent-developer) ;;
      admin) roles=(agent-user agent-developer agent-admin) ;;
      *) die "audience must be tester, developer or admin" ;;
    esac
    roles+=("$@")
    kc_login
    if [[ $(kc get users -r agents -q "username=$user" -q exact=true --fields id | jq length) == 0 ]]; then
      # complete profile (Keycloak 26 asks for missing first/last name or email at login otherwise)
      kc create users -r agents -s "username=$user" -s enabled=true -s emailVerified=true \
        -s "email=$user@example.local" -s "firstName=$user" -s "lastName=$audience" 2>&1 | grep -v -e '^Created' -e '^$' || true
      [[ $(kc get users -r agents -q "username=$user" -q exact=true --fields id | jq length) == 1 ]] ||
        die "could not create $user"
    fi
    password=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
    kc set-password -r agents --username "$user" --new-password "$password"
    # exactly the audience's platform roles (a downgrade removes the others), plus the extras
    for r in agent-developer agent-admin; do
      [[ " ${roles[*]} " == *" $r "* ]] || kc remove-roles -r agents --uusername "$user" --rolename "$r" 2>/dev/null || true
    done
    args=(); for r in "${roles[@]}"; do args+=(--rolename "$r"); done
    kc add-roles -r agents --uusername "$user" "${args[@]}"
    echo "login  $user / $password   (roles: ${roles[*]})"
    echo "portal $(url PORTAL_URL)"
    if [[ $audience != tester ]]; then echo "builder $(url BUILDER_URL)"; fi
    if [[ $audience == admin ]]; then echo "gateway $(url GATEWAY_UI_URL)/ui"; fi
    ;;

  *) sed -n '2,24p' "$0"; exit 1 ;;
esac
