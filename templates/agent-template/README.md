# my-agent

An agent for the agent platform. No tools to install: git and GitHub do everything.

## Layout
One agent: `agent.yaml` (+ `flow.json`) at the repo root, as in this template. Several agents in one repo:
`agents/<name>/agent.yaml` (+ `flow.json`, or a `Dockerfile` for a code agent) and no root `agent.yaml`.
Every agent of the repo is released together.

## Build
- **Langflow agent:** build it in the stage Langflow Builder. When it works, Export → save as `flow.json`
  here, and copy its `"id"` into `langflow.flow_id` in `agent.yaml`. Use model names from the gateway
  (`chat-default`, `embed-default`); keys and credentials never go into the flow.
- **Code agent (AG-UI: Pydantic AI, LangGraph, ...):** add your code and a `Dockerfile` next to `agent.yaml`, set
  `runtime: agui` with `agui: {host, path}` and remove `langflow:`. The workflow builds and pushes the image.
- **Try it on a local platform stack** (agent-platform checked out next to this repo):
  `uv run ../agent-platform/scripts/publish.py deploy .` (or `agents/*`). To take a flow you changed in the
  local Builder back into this repo: `uv run ../agent-platform/scripts/publish.py pull "<flow name>" <folder>`.

## Ship
| You do | Happens |
|---|---|
| Open a PR | `agent.yaml` and `flow.json` are validated |
| Merge to `main` | Released to **stage** |
| Publish a GitHub release (e.g. `v1.2.0`) | Released to **prod** after a team member approves the `prod` environment |
| Actions → agent → Run workflow on an older tag | Rollback |

Each release is a PR in `ORG/agent-catalog`; the workflow summary links it.

## Who can use it
`access.roles` in `agent.yaml`. People get roles through Entra groups (access request), not here.
