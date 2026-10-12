# Diagrams

Three views of the agent platform, each in three formats:

| View | What it shows | SVG (polished) | tldraw (editable) | Mermaid (text, renders on GitHub) |
|---|---|---|---|---|
| Components | high-level parts and what each one is for | [components.svg](components.svg) | [components.tldr](components.tldr) | [components.mmd](components.mmd) |
| Architecture | services, ports, listeners, stores, publish path | [architecture.svg](architecture.svg) | [architecture.tldr](architecture.tldr) | [architecture.mmd](architecture.mmd) |
| Data flow | sign-in, agent run, human in the loop, control plane, step by step | [data-flow.svg](data-flow.svg) | [data-flow.tldr](data-flow.tldr) | [data-flow.mmd](data-flow.mmd) |

Open a `.tldr` file at tldraw.com (menu → Open file) or in the tldraw desktop / VS Code extension. The tldraw versions
use automatic elbow arrows; drag an arrow to tidy a route, the SVGs are the hand-checked layout.

## Regenerate

```bash
python3 docs/make-components.py docs/components.svg docs/diagram-specs/components.json
python3 docs/make-data-flow.py  docs/data-flow.svg  docs/diagram-specs/data-flow.json
# architecture.svg is hand-written; its tldraw layout is docs/diagram-specs/architecture.json

# .tldr from the layout specs (validated against tldraw's schema)
npm i --prefix /tmp/tldr @tldraw/tlschema@5.5.2 @tldraw/store@5.5.2 @tldraw/utils@5.5.2
for d in components architecture data-flow; do
  NODE_PATH=/tmp/tldr/node_modules node docs/make-tldr.mjs docs/diagram-specs/$d.json docs/$d.tldr
done
```

The Mermaid files are written by hand; keep them in step when the platform changes.

## Components and their purpose

```mermaid
%% Agent platform · components and their purpose (picture: components.svg)
flowchart LR
  subgraph people["People"]
    users["<b>End users</b><br/>find the right agent, ask questions,<br/>approve or reject proposed actions"]
    admins["<b>Agent admins</b><br/>govern models, tools and access;<br/>see who used what"]
    devs["<b>Agent developers</b><br/>build and test agents,<br/>publish them to the catalog"]
  end

  subgraph exp["Experience & identity"]
    portal["<b>Portal</b><br/>one place for every agent: sign in, search,<br/>chat with streaming answers, tool results<br/>and approval cards, whatever the runtime"]
    idp["<b>Identity provider (OIDC)</b><br/>who you are and your roles;<br/>one login for portal and gateway UI"]
  end

  subgraph door["Front door"]
    gw["<b>agentgateway</b><br/>checks identity and roles for every call ·<br/>routes each agent to its runtime ·<br/>governs model and tool use (keys, guardrails) ·<br/>records who called which agent and model"]
  end

  subgraph runtimes["Agent runtimes"]
    adapter["<b>Langflow adapter</b><br/>Langflow speaks standard AG-UI,<br/>incl. pausing for a human"]
    runtime["<b>Langflow runtime</b><br/>runs published visual agents with<br/>per-user memory and human-in-the-loop"]
    code["<b>Code runtimes</b> (planned)<br/>code-first agents behind the same door"]
  end

  subgraph uses["What agents use"]
    llm["<b>LLM providers</b><br/>the models, reached only via the gateway"]
    ent["<b>Enterprise systems</b><br/>data and actions agents work on (e.g. an ERP)"]
    mcp["<b>Shared tools (MCP)</b> (planned)<br/>tools every runtime can use"]
  end

  subgraph build["Build & publish"]
    builder["<b>Langflow Builder</b><br/>design and test agents visually"]
    publish["<b>Publish</b><br/>a tested flow becomes a live catalog<br/>agent in one step, no restarts"]
    git[("<b>Git repository</b><br/>source of truth, reviewed by PR")]
  end

  subgraph insight["State & insight"]
    state[("<b>Databases & volumes</b><br/>identities, flows, jobs and memory,<br/>gateway settings and request logs")]
    obs["<b>Observability</b> (planned)<br/>logs, metrics, traces, audit dashboards"]
  end

  users --> portal
  idp --> portal
  idp -- tokens --> gw
  portal -- AG-UI --> gw
  admins --> gw
  gw -- "/run" --> adapter
  gw -.-> code
  adapter --> runtime
  runtime -- "via gateway" --> llm
  runtime --> ent
  code -.-> mcp
  devs --> builder
  builder --> publish
  publish --> git
  publish -- publish --> runtime
  runtime -.-> state
  gw -.-> obs

  classDef ui fill:#ffffff,stroke:#005d92,stroke-width:2px
  classDef idp fill:#f5f3ff,stroke:#7c3aed
  classDef gw fill:#eff6ff,stroke:#2563eb,stroke-width:2px
  classDef rt fill:#f0fdfa,stroke:#0d9488
  classDef dev fill:#ecfdf5,stroke:#059669
  classDef ext fill:#fff7ed,stroke:#d97706
  classDef store fill:#f8fafc,stroke:#475569
  classDef plan fill:#ffffff,stroke:#94a3b8,stroke-dasharray:5 5,color:#475569
  class portal ui
  class idp,admins idp
  class gw gw
  class adapter,runtime rt
  class devs,builder,publish dev
  class llm,ent ext
  class git,state store
  class code,mcp,obs plan
```

## System architecture

```mermaid
%% Agent platform · system architecture (detailed picture: architecture.svg)
flowchart TB
  subgraph people["People"]
    direction LR
    users["End users<br/>browser · catalog, chat, approvals"]
    admins["Agent admins<br/>role agent-admin · models, MCP, audit"]
    devs["Agent developers<br/>Langflow flows · code agents (planned)"]
  end

  subgraph exp["Experience & identity"]
    direction LR
    idp["OIDC IdP<br/>Keycloak :8180 · Entra ID / Okta<br/>token: sub · aud · roles[]"]
    portal["Portal · Next.js :3100<br/>assistant-ui + AG-UI HttpAgent<br/>Auth.js OIDC · catalog · chat · HITL card"]
    catalog[("agents/*.yaml + platform.yaml<br/>catalog, roles, routes source")]
  end

  subgraph gw["agentgateway v1.6 · one container, three listeners"]
    direction LR
    gwdef["default :4100 · agent API<br/>JWT strict · per-agent roles (CEL)<br/>audit: user, agent, thread"]
    gwadm["admin-ui :4101 · gateway UI<br/>OIDC login · agent-admin only<br/>models, MCP, logs, analytics"]
    gwsvc["services :4102 · LLM & MCP<br/>API key per runtime<br/>user / agent attribution"]
    gwcfg[("config.yaml (generated, hot reload)<br/>agw_data: UI overlay + request logs")]
  end

  subgraph rt["Agent runtimes"]
    direction LR
    adapter["Langflow AG-UI adapter :8080<br/>stream · background + events<br/>interrupts ↔ resume (stateless)"]
    runtime["Langflow Runtime :7880<br/>memory per user and thread<br/>Human Input · tool approval"]
    code["Code runtimes (planned)<br/>Pydantic AI · LangGraph · CrewAI"]
  end

  subgraph build["Build & publish · no restarts"]
    direction LR
    builder["Langflow Builder :7870<br/>visual editor · playground"]
    publish["scripts/publish.py<br/>gateway model · flows/ + agents/<br/>runtime API · routes"]
    git[("Git repo<br/>flows/ agents/ components/ gateway/")]
  end

  subgraph data["Data & backing services"]
    direction LR
    pg[("Postgres :5440<br/>keycloak · langflow_runtime · langflow_builder")]
    vol[("Volumes<br/>agw_data · pg_data")]
    ollama["Ollama :11434<br/>qwen3:8b · nomic-embed-text"]
    biz["Business system :8000<br/>REST / OData APIs, docs"]
    mcp["MCP servers (planned)"]
    obs["Observability (planned)<br/>Loki · Prometheus · Tempo · Grafana"]
  end

  users --> portal
  portal -- OIDC --> idp
  portal -. reads .-> catalog
  portal -- "AG-UI + Bearer JWT" --> gwdef
  idp -- JWKS --> gwdef
  admins -- "browser login" --> gwadm
  gwdef -- "/run · flow id, user, key" --> adapter
  gwdef -. "runtime: agui" .-> code
  adapter -- "Workflow API v2" --> runtime
  runtime -- "LLM + user / agent / thread" --> gwsvc
  code -.-> gwsvc
  gwsvc --> ollama
  gwsvc -.-> mcp
  runtime -- tools --> biz
  runtime -.-> pg
  gwcfg -- "hot reload" --> gwdef
  catalog --> gwcfg
  devs --> builder
  builder -- export --> publish
  publish --> git
  publish -- "upsert flow (API)" --> runtime
  publish -- routes --> gwcfg

  classDef ui fill:#ffffff,stroke:#005d92,stroke-width:2px
  classDef idp fill:#f5f3ff,stroke:#7c3aed
  classDef gw fill:#eff6ff,stroke:#2563eb
  classDef rt fill:#f0fdfa,stroke:#0d9488
  classDef dev fill:#ecfdf5,stroke:#059669
  classDef ext fill:#fff7ed,stroke:#d97706
  classDef store fill:#f8fafc,stroke:#475569
  classDef plan fill:#ffffff,stroke:#94a3b8,stroke-dasharray:5 5,color:#475569
  class portal ui
  class idp,admins idp
  class gwdef,gwadm,gwsvc gw
  class adapter,runtime rt
  class devs,builder,publish dev
  class ollama,biz ext
  class catalog,gwcfg,git,pg,vol store
  class code,mcp,obs plan
```

## Data flow

```mermaid
%% Agent platform · data flow (picture: data-flow.svg)
sequenceDiagram
  autonumber
  participant BR as Browser
  participant PO as Portal :3100
  participant IDP as OIDC IdP
  participant GW as agentgateway :4100
  participant AD as Langflow adapter
  participant RT as Langflow runtime
  participant SV as agentgateway :4102
  participant EX as Ollama · business APIs

  rect rgba(124, 58, 237, 0.06)
    Note over BR,IDP: A · Sign-in (generic OAuth2 / OIDC code flow with PKCE)
    BR->>PO: Sign in
    BR->>IDP: login page (public issuer, e.g. localhost:8180)
    IDP-->>PO: code → token exchange (server side, OIDC_INTERNAL_ISSUER)
    Note over PO: access + refresh token in encrypted cookie
  end

  rect rgba(37, 99, 235, 0.05)
    Note over BR,EX: B · Agent run (standard AG-UI end to end)
    BR->>PO: POST /api/agents/{slug}/run · RunAgentInput {threadId, messages}
    PO->>GW: + Bearer access token, x-agui-thread-id
    Note over GW: validate JWT (JWKS from IdP) · CEL roles · audit log (user, agent, thread)
    GW->>AD: POST /run · x-langflow-flow-id, x-end-user-id, x-api-key (no user token)
    Note over AD: flow can pause? no → stream mode · yes → background job + events
    AD->>RT: POST /api/v2/workflows · session_id = threadId
    Note over RT: memory scoped user::thread · Agent plans
    RT->>SV: POST /v1/chat/completions · runtime key + x-end-user-id, x-agent-slug, x-agui-thread-id
    SV->>EX: ollama/qwen3:8b (Logs/Analytics: user, agent, tokens)
    RT->>EX: tool call (e.g. make_api_request → business API)
    RT-->>AD: AG-UI SSE: TEXT_MESSAGE_*, TOOL_CALL_*, RUN_FINISHED
    AD-->>BR: same events (client ids, langflow.* dropped) via gateway and portal
  end

  rect rgba(219, 39, 119, 0.05)
    Note over BR,RT: C · Human in the loop (Langflow pause/resume ↔ standard AG-UI interrupts)
    Note over RT: Human Input node, or a tool with approval_actions → pause
    RT-->>AD: CUSTOM langflow.human_input_required (request_id, options, prompt)
    AD-->>BR: RUN_FINISHED {outcome: interrupt} · id = job + request + event id
    BR->>AD: new run with resume [{interruptId, status, payload {action_id}}] (via portal + gateway)
    AD->>RT: POST /{job}/resume + GET /{job}/events (Last-Event-ID)
    RT-->>BR: remaining events → portal (cancelled → /stop · other user → job not found)
  end

  rect rgba(5, 150, 105, 0.05)
    Note over BR,EX: D · Control plane (no restarts)
    Note over AD,RT: publish.py: export flow → add agentgateway Model → flows/ + agents/ → upsert runtime by API
    Note over GW: gen-gateway.py → config.yaml → hot reload (route live in seconds)
    Note over SV: admin UI (:4101) → models / MCP in the gateway DB → served on :4102
  end
```
