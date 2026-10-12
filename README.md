# Agent platform

A portal and agent catalog (Next.js + assistant-ui, AG-UI) in front of **agentgateway**, with pluggable agent
runtimes behind it. Langflow is the first runtime (visual builder for developers). Pydantic AI, LangGraph and
CrewAI come later.

![components](docs/components.svg)

More diagrams (architecture, data flow; SVG, tldraw and Mermaid): [docs/README.md](docs/README.md).

**Contract:** every agent is `POST /agents/{slug}/run` on the gateway. It takes a standard AG-UI `RunAgentInput`
and returns AG-UI SSE events, whatever runtime runs it. The portal uses one plain `HttpAgent` for all agents.

- **Langflow** goes through the **Langflow AG-UI adapter** (`services/langflow-adapter`), which turns standard
  AG-UI into Langflow Workflow API calls: stream mode for normal flows (token streaming), background jobs for flows
  that can pause for a human, with Langflow's pause/resume mapped to standard AG-UI interrupts (see
  "Human in the loop").
- **Native AG-UI runtimes** (Pydantic AI, LangGraph, CrewAI) are forwarded as is (`runtime: agui`).

**Auth** is generic OAuth2/OIDC. The gateway validates access tokens from any IdP that issues:

| Claim | Value |
|---|---|
| `iss` | the configured issuer (`gateway/base.yaml`) |
| `aud` | `agent-platform` |
| `sub` | user id, forwarded to the runtime as `x-end-user-id` |
| `roles` | array, matched against `access.roles` in the agent's `agent.yaml`; `agent-admin` can use every agent |

Locally that IdP is Keycloak. For another environment, change `issuer`/`jwks` and map that IdP's roles into
`roles` (for example Entra ID app roles, which already use that claim name).

## Layout

```
catalog/<slug>/           agents deployed to the local stack (gitignored; agent-catalog/<env>/ elsewhere)
test-agents/hitl-demo/    the platform's own test agent (deterministic human-in-the-loop, no model)
gateway/base.yaml         hand-edited gateway base (listener, OIDC JWT, CORS)
gateway/config.yaml       GENERATED: uv run scripts/gen-gateway.py
apps/portal/              Next.js 15 portal: OIDC login, agent list, assistant-ui chat (see below)
infra/keycloak/           local OIDC realm "agents" (users alice, bob)
infra/postgres/init.sql   databases: keycloak, langflow_builder, langflow_runtime, portal
scripts/                  init-env, bootstrap-runtime-key, publish, gen-gateway, validate-agents, e2e, dev-token,
                          smoke, models, github-setup
docs/                     diagrams: components, architecture, data flow (.svg, .tldr, .mmd)
```

platform.yaml             platform-wide settings (admin roles), read by gen-gateway.py and the portal
components/agentgateway/  the agentgateway Model component that routes every Agent's model calls via the gateway
services/langflow-adapter standard AG-UI (incl. HITL interrupts) in front of the Langflow runtime
schemas/agent.schema.json agent manifest contract v1 (validate: uv run scripts/validate-agents.py)
.github/workflows/        ci.yml (this repo) · agent.yml (reusable: validate + release, called by agent repos @v1)
templates/                agent-catalog and agent-template repos, created by scripts/github-setup.sh

`gateway/config.yaml` is generated (on every `docker compose up` by the `gateway-config` container, and by
`publish.py`), never committed.

**Agents are not in this repo.** Each team keeps its agents in its own repo (agent folders: `agent.yaml` +
`flow.json`, from `templates/agent-template`); for example `../my-agents`. Agent repos release
through `.github/workflows/agent.yml` into `agent-catalog`; locally, `publish.py deploy` puts agent folders into
`catalog/`. An agent repo can add local wiring (Builder components, env vars, volumes) with a compose file in
`COMPOSE_FILE` (`.env`), e.g. `../my-agents/compose.platform.yaml`.

## Local stack

| Service | URL | Notes |
|---|---|---|
| agentgateway | http://localhost:4100 | `/agents/{slug}/run` |
| agentgateway admin UI | http://localhost:4101/ui | "Sign in with SSO" → Keycloak user `admin`/`admin` (role `agent-admin`) |
| agentgateway services | http://localhost:4102 | LLM (`/v1/chat/completions`, `/v1/models`) and MCP (`/mcp`) added in the UI; runtimes use `agentgateway:4102` |
| Langflow Builder | http://localhost:7870 | visual editor (auto login locally) |
| Langflow Runtime | http://localhost:7880 | headless; clients go through the gateway |
| Keycloak | http://localhost:8180 | admin user `admin`, password `KEYCLOAK_ADMIN_PASSWORD` in `.env` |
| Postgres | localhost:5440 | user `platform` |
| Portal | http://localhost:3100 | container `portal` (built from `apps/portal/Dockerfile`); brand from `BRAND` in `.env` |

Ollama is the host one on `:11434`.

```bash
./scripts/init-env.sh                 # .env with random secrets (once)
docker compose up -d
./scripts/bootstrap-runtime-key.sh    # Langflow runtime API key → .secrets/ (one-time; restarts the gateway once)
uv run scripts/publish.py deploy test-agents/hitl-demo --builder        # the platform's test agent
uv run scripts/publish.py deploy ../my-agents/agents/* --builder      # agents from agent repos
uv run scripts/e2e.py                 # end-to-end check (auth, HITL, services key, audit)
uv run scripts/e2e.py --model-agent invoice-monitor --prompt "How many invoices failed to post in the last 24h?"   # + model, tools
./scripts/models.sh                   # models of the Ollama the platform uses (host.docker.internal:11434)
```

Test users: `alice`/`alice` (roles agent-user, finance-support), `bob`/`bob` (agent-user), `dev`/`dev` (agent-user,
agent-developer; fresh stacks) and `admin`/`admin` (agent-user, agent-admin).

The Builder is also behind a login on http://localhost:7871 (`builder-login`, oauth2-proxy): roles agent-developer or
agent-admin. :7870 stays loopback-only without login.

### Sharing the local stack: `scripts/share.sh`

By URL over Tailscale: `on public` (anyone with the link, Tailscale Funnel) or `on tailnet` (your tailnet only).
Keycloak roles decide what each person can use.

```bash
./scripts/share.sh on public                           # or: on tailnet
./scripts/share.sh user jane tester finance-support    # portal (+ finance agents); prints a one-off password
./scripts/share.sh user raj developer                  # portal + Langflow Builder
./scripts/share.sh user mia admin                      # + gateway admin UI
./scripts/share.sh off                                 # back to localhost
```

| Shared URL | Service |
|---|---|
| `https://<machine>.ts.net` | Portal, plus Keycloak's sign-in pages (`/realms`, `/resources`) |
| `https://<machine>.ts.net:8443` | Langflow Builder (login: agent-developer, agent-admin) |
| `https://<machine>.ts.net:10000/ui` | Gateway admin UI (login: agent-admin) |

Funnel allows only ports 443, 8443 and 10000, hence Keycloak on the portal's host. Never shared: the Keycloak admin
console (`http://localhost:8180/admin`, this machine only), the Builder without login, the runtime, Postgres and the
gateway's agent/services ports. `on public` disables the test users whose password is their name (`alice`, `bob`,
`dev`, `admin`; `off` and `on tailnet` enable them again) and turns on brute-force protection. While shared, everyone,
including you, uses the shared URLs: the IdP has one public address and tokens carry it. The portal redirects
localhost there. Funnel must be allowed for the machine in the tailnet policy (`funnel` node attribute).

### Local deploys: `scripts/publish.py`

No restarts. Builder → agent folder (in the agent repo) → local stack:

```bash
uv run scripts/publish.py pull "<flow id | endpoint name | name in the Builder>" ../my-agents/agents/my-agent
uv run scripts/publish.py pull --file some-flow.json ../my-agents/agents/my-agent    # import a flow file
uv run scripts/publish.py deploy ../my-agents/agents/my-agent [--set field=value] [--builder]
uv run scripts/publish.py deploy --all          # redeploy catalog/ (e.g. after resetting the Langflow databases)
uv run scripts/publish.py remove my-agent
```

`pull` routes model calls through the gateway and writes `flow.json` and `agent.yaml` (created if missing; slug =
folder name) into the agent folder, to commit in the agent repo. `deploy` validates the folders
(`schemas/agent.schema.json`), upserts the flows into the runtime, copies them to `catalog/<slug>/` and regenerates the
gateway routes. `--set field=value` sets a component field on every node that has it (environment-specific
paths/URLs; applied at deploy, never stored in the agent repo).

## Human in the loop

Generic across runtimes: the portal handles **standard AG-UI interrupts** (RUN_FINISHED
`outcome: {type: "interrupt", interrupts: [...]}`, resumed by a new run with `resume: [{interruptId, status, payload}]`).
`apps/portal/src/components/interrupts.tsx` renders one card for any interrupt: decision buttons when the
`responseSchema` is a single enum (labels from `x-labels`), a small form for other object schemas, a tool box for
`reason: tool_call`, and Cancel. Runtimes that emit standard interrupts (code agents) need nothing else.

Langflow pauses differently, so the adapter translates (stateless; the interrupt id carries the Langflow job id,
request id and the SSE event id to continue after):

| Step | Client (standard AG-UI) | Adapter → Langflow |
|---|---|---|
| run | `POST /agents/<slug>/run` | flow has Human Input or a tool with `approval_actions` → `mode: background` job + `GET /{job}/events`; otherwise `mode: stream` |
| pause | `RUN_FINISHED` with an interrupt (`input_required` / `tool_call`, options, `expiresAt`) | `CUSTOM langflow.human_input_required` |
| resume | new run with `resume[0].payload = {action_id}` | `POST /{job}/resume {request_id, decision}` + events after the pause (`Last-Event-ID`) |
| cancel | `resume[0].status = cancelled` | `POST /stop {job_id}` |

Langflow's end-user check applies: another user cannot resume someone else's pause ("job not found").

Test agents:
- `hitl-demo` (`scripts/make-hitl-demo.py`): Chat Input → Human Input → "✅ Approved: …" / "❌ Rejected: …".
- `invoice-monitor-approval` (`../my-agents`, `scripts/make-approval-demo.py` there): an invoice monitor agent; its `make_api_request` tool
  needs Approve / Reject (Actions table → `approval_actions`). Approve runs the tool and answers; Reject makes the
  agent say it cannot answer without it.

In the Builder: add a **Human Input** node, or in a tool component's **Actions** table select approval decisions,
then publish as usual. The adapter picks up the change within 30 s. Langflow's `edit` / `respond` decisions need
extra fields the card does not offer yet; use approve / reject.

## Adding an agent (no restarts)

Nothing needs a restart to add, change or remove an agent (all three verified locally):

| Piece | How it picks up a change |
|---|---|
| Langflow runtime | Publish the flow through its API: `POST /api/v1/flows/` (create, keeps the flow `id`), `PATCH /api/v1/flows/{id}` (update), `DELETE` (remove). Callable immediately. |
| agentgateway | Watches `config.yaml` and hot-reloads routes within seconds (`loaded config from File` in the log). Only the `config:` section (storage, database, admin address) is startup-only. |
| Portal | Reads `catalog/*/agent.yaml` on every request (P2: from the catalog database). |

Steps today:
1. In the agent's repo (from `templates/agent-template`): build the flow in the Builder and `publish.py pull` it
   into an agent folder, or write a code agent (`runtime: agui` with `agui: {host, path}` and a `Dockerfile`).
2. Locally: `publish.py deploy <folder>`. The route is live a few seconds later.
3. Stage and prod: merge (stage) or publish a GitHub release (prod) in the agent repo; the reusable workflow
   opens an auto-merging release PR in `agent-catalog`. Deploying from `agent-catalog` comes with the stage runtime.

Langflow does not load flows at startup: `publish.py deploy` is the only way flows get into the runtime (and, with
`--builder`, the Builder). Redeploying keeps each flow's model; `pull --model` changes it.

## Gotchas

- `LANGFLOW_SECRET_KEY` must be a Fernet key (32 bytes, url-safe base64). `init-env.sh` generates it that way.
- agentgateway fetches JWKS at startup, so it waits for Keycloak's healthcheck and restarts if the fetch fails.
- Recreating a container (e.g. `docker compose up -d langflow-runtime` after an env change) can give it a new IP;
  the gateway keeps the old address until it is restarted. That once sent runtime traffic to the Builder
  ("Invalid API key"). Restart the gateway after recreating Langflow containers. (Kubernetes Services have stable
  IPs, so this is local-only.)
- The bootstrap script restarts the gateway once, because the key file starts empty. That is one-time setup;
  normal config changes are hot-reloaded.
- The Keycloak realm is imported only into an empty database. To apply realm changes: stop Keycloak,
  drop/create the `keycloak` database, start Keycloak again.
- The realm defines its own client scope (`agent-platform`), so Keycloak's built-in scopes aren't created.
  `sub`, `aud` and `roles` come from that scope's mappers.
- The Langflow Workflow API is Beta. Its request shape lives only in the adapter (`services/langflow-adapter`).
- Langflow sends `TOOL_CALL_RESULT` with the assistant message's id (the spec expects a separate tool message)
  and only just before the final answer, so tool cards show "running…" until then. assistant-ui handles it.
- After re-importing the realm, sign out and in again: the old session's tokens were signed with keys that no
  longer exist.

## License

[Apache-2.0](LICENSE)
