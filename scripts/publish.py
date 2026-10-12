# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "pyyaml>=6", "jsonschema[format]>=4.23"]
# ///
"""Langflow agents on the local stack: Builder flow → agent folder → deployed agent. No restarts.

An agent folder is what agent repos contain: <dir>/agent.yaml, plus flow.json for Langflow agents
(e.g. ../my-agents/agents/invoice-monitor, test-agents/hitl-demo).

  pull     a Builder flow (or a flow file) → <dir>/flow.json with its model calls routed through agentgateway;
           creates <dir>/agent.yaml (slug = folder name) or updates its flow_id. Commit the folder in the agent repo.
  deploy   agent folder(s) → validated → flow upserted into the Langflow runtime → copied to catalog/<slug>/ →
           gateway routes regenerated (hot reload); the portal lists it on the next request.
  deploy --all   redeploy everything in catalog/ (e.g. after resetting the Langflow databases)
  remove   <slug>: out of catalog/, the gateway and the runtime

Usage:
  uv run scripts/publish.py pull "<flow id | endpoint name | name in the Builder>" ../my-agents/agents/invoice-monitor
  uv run scripts/publish.py pull --file some-flow.json ../my-agents/agents/my-agent
  uv run scripts/publish.py deploy test-agents/hitl-demo ../my-agents/agents/*
  uv run scripts/publish.py deploy --all --builder
  uv run scripts/publish.py remove invoice-monitor

Options:
  pull:    --model ollama/qwen3:8b   gateway model name (default: keep the flow's, else ollama/qwen3:8b)
           --roles finance-support,...   access roles for a new agent.yaml (default agent-user)
  deploy:  --set field=value         set a component field on every node that has it (repeatable). Environment
                                     specific, so applied at deploy time and never stored in the agent repo.
           --builder                 also upsert the flows into the Builder (seed a fresh Builder)

Env: LANGFLOW_BUILDER_URL (http://localhost:7870), LANGFLOW_BUILDER_API_KEY (else auto-login, local only),
     LANGFLOW_RUNTIME_URL (http://localhost:7880), LANGFLOW_RUNTIME_API_KEY (else .secrets/langflow-runtime.key),
     CATALOG_DIR (catalog/)
"""

import argparse
import functools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import langflow_lib
import yaml

ROOT = langflow_lib.ROOT
CATALOG_DIR = Path(os.getenv("CATALOG_DIR", ROOT / "catalog"))
FLOW_FIELDS = ("name", "description", "data", "endpoint_name", "icon", "tags", "is_component")


def builder_client() -> httpx.Client:
    url = os.getenv("LANGFLOW_BUILDER_URL", "http://localhost:7870")
    key = os.getenv("LANGFLOW_BUILDER_API_KEY")
    if key:
        return httpx.Client(base_url=url, headers={"x-api-key": key}, timeout=60)
    token = httpx.get(f"{url}/api/v1/auto_login", timeout=30).json()["access_token"]  # local Builder only
    return httpx.Client(base_url=url, headers={"Authorization": f"Bearer {token}"}, timeout=60)


def runtime_client() -> httpx.Client:
    url = os.getenv("LANGFLOW_RUNTIME_URL", "http://localhost:7880")
    key = os.getenv("LANGFLOW_RUNTIME_API_KEY") or (ROOT / ".secrets/langflow-runtime.key").read_text().strip()
    return httpx.Client(base_url=url, headers={"x-api-key": key}, timeout=60)


def find_flow(client: httpx.Client, ref: str) -> dict:
    resp = client.get(f"/api/v1/flows/{ref}")
    if resp.status_code == 200:
        return resp.json()
    flows = client.get("/api/v1/flows/", params={"get_all": True, "header_flows": False}).json()
    matches = [f for f in flows if ref in (f.get("endpoint_name"), f.get("name"))]
    if len(matches) != 1:
        sys.exit(f"flow {ref!r}: {len(matches)} matches in the Builder (use the flow id)")
    return client.get(f"/api/v1/flows/{matches[0]['id']}").json()


def upsert(client: httpx.Client, flow: dict, where: str) -> None:
    body = {k: flow[k] for k in FLOW_FIELDS if k in flow}
    if client.get(f"/api/v1/flows/{flow['id']}").status_code == 200:
        resp = client.patch(f"/api/v1/flows/{flow['id']}", json=body)
    else:
        resp = client.post("/api/v1/flows/", json={"id": flow["id"], **body})
    if resp.status_code >= 300:
        sys.exit(f"{where}: {resp.status_code} {resp.text[:300]}")
    print(f"  {where}: {'updated' if resp.request.method == 'PATCH' else 'created'} flow {flow['id']}")


def apply_sets(flow: dict, sets: list[str]) -> None:
    for item in sets:
        field, _, value = item.partition("=")
        hits = 0
        for node in flow["data"]["nodes"]:
            template = node["data"]["node"].get("template", {})
            if isinstance(template.get(field), dict):
                template[field]["value"] = value
                hits += 1
        if not hits:
            sys.exit(f"--set {field}: no node has that field")
        print(f"  set {field} on {hits} node(s)")


@functools.cache
def gateway_model_template() -> dict:
    return langflow_lib.registry()[langflow_lib.GATEWAY_MODEL]


def route_models(flow: dict, slug: str, model: str | None) -> None:
    """One name everywhere (catalog slug = Langflow endpoint) and every Agent's model calls via agentgateway."""
    flow["endpoint_name"] = slug
    if langflow_lib.add_gateway_model(flow, gateway_model_template(), slug, model):
        print("  model calls → agentgateway")
    else:
        print("  no Agent node: no model calls to route")


def write_json(path: Path, flow: dict) -> None:
    path.write_text(json.dumps({k: flow[k] for k in ("id", *FLOW_FIELDS) if k in flow}, indent=2) + "\n")


def pull(args: argparse.Namespace) -> None:
    folder: Path = args.dir
    slug = folder.resolve().name
    print(f"pull {slug} → {folder}")
    if args.file:
        flow = json.loads(args.file.read_text())
    else:
        with builder_client() as builder:
            flow = find_flow(builder, args.flow)
    route_models(flow, slug, args.model)
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "flow.json", flow)
    print(f"  wrote {folder / 'flow.json'}")

    manifest = folder / "agent.yaml"
    if manifest.exists():
        agent = yaml.safe_load(manifest.read_text())
        if agent.get("langflow", {}).get("flow_id") != flow["id"]:
            agent.setdefault("langflow", {})["flow_id"] = flow["id"]
            manifest.write_text(yaml.safe_dump(agent, sort_keys=False, allow_unicode=True))
            print(f"  {manifest}: flow_id updated")
        return
    agent = {
        "slug": slug,
        "name": flow["name"],
        "description": (flow.get("description") or "").split(" LLM via agentgateway")[0] or flow["name"],
        "owner_team": "TODO",
        "tags": [],
        "runtime": "langflow",
        "langflow": {"flow_id": flow["id"]},
        "access": {"roles": [r.strip() for r in args.roles.split(",") if r.strip()]},
        "starter_prompts": [],
    }
    manifest.write_text(yaml.safe_dump(agent, sort_keys=False, allow_unicode=True))
    print(f"  {manifest}: created (fill in owner_team, tags, starter_prompts)")


def deploy_one(folder: Path, sets: list[str], builder: bool) -> None:
    agent = yaml.safe_load((folder / "agent.yaml").read_text())
    slug = agent["slug"]
    target = CATALOG_DIR / slug
    print(f"deploy {slug} ({folder})")
    flow = None
    if agent["runtime"] == "langflow":
        flow = json.loads((folder / "flow.json").read_text())
        route_models(flow, slug, None)
        apply_sets(flow, sets)
        with runtime_client() as runtime:
            upsert(runtime, flow, "runtime")
        if builder:
            with builder_client() as b:
                upsert(b, flow, "builder")
    # catalog/<slug>/ = what runs: the manifest and the flow as deployed (sets applied)
    if target.resolve() != folder.resolve():
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        shutil.copy(folder / "agent.yaml", target / "agent.yaml")
    if flow is not None:
        write_json(target / "flow.json", flow)
    print(f"  catalog/{slug}/ updated")


def deploy(args: argparse.Namespace) -> None:
    folders = sorted(p for p in CATALOG_DIR.iterdir() if (p / "agent.yaml").exists()) if args.all else args.dirs
    if not folders:
        sys.exit("nothing to deploy: give agent folders, or --all for everything in catalog/")
    validate = [sys.executable, str(ROOT / "scripts/validate-agents.py"), *(str(f / "agent.yaml") for f in folders)]
    sys.stdout.flush()
    if subprocess.run(validate, check=False).returncode:
        sys.exit("not deployed: fix the agents above")
    slugs = [yaml.safe_load((f / "agent.yaml").read_text())["slug"] for f in folders]
    if len(set(slugs)) != len(slugs):
        sys.exit(f"duplicate slugs: {slugs}")
    for folder in folders:
        deploy_one(folder, args.sets, args.builder)
    regenerate_gateway()


def remove(args: argparse.Namespace) -> None:
    target = CATALOG_DIR / args.slug
    if not (target / "agent.yaml").exists():
        sys.exit(f"{args.slug} is not deployed")
    flow_id = (yaml.safe_load((target / "agent.yaml").read_text()).get("langflow") or {}).get("flow_id")
    if flow_id:
        with runtime_client() as runtime:
            print(f"  runtime: delete flow {flow_id} → {runtime.delete(f'/api/v1/flows/{flow_id}').status_code}")
    shutil.rmtree(target)
    print(f"removed catalog/{args.slug}/")
    regenerate_gateway()


def regenerate_gateway() -> None:
    sys.stdout.flush()
    subprocess.run(["uv", "run", "-q", str(ROOT / "scripts/gen-gateway.py")], check=True)
    print("gateway routes regenerated; live in a few seconds")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("pull", help="Builder flow → agent folder")
    pp.add_argument("flow", nargs="?", help="Builder flow id, endpoint name or name")
    pp.add_argument("dir", type=Path, help="agent folder (its name is the slug)")
    pp.add_argument("--file", type=Path, help="take the flow from a JSON file instead of the Builder")
    pp.add_argument("--model")
    pp.add_argument("--roles", default="agent-user")

    dp = sub.add_parser("deploy", help="agent folder(s) → local stack")
    dp.add_argument("dirs", nargs="*", type=Path)
    dp.add_argument("--all", action="store_true", help="redeploy everything in catalog/")
    dp.add_argument("--set", action="append", default=[], dest="sets")
    dp.add_argument("--builder", action="store_true")

    rp = sub.add_parser("remove", help="take an agent off the local stack")
    rp.add_argument("slug")

    args = p.parse_args()
    if args.command == "pull":
        if bool(args.file) == bool(args.flow):
            p.error("give a Builder flow reference or --file")
        pull(args)
    elif args.command == "deploy":
        if bool(args.all) == bool(args.dirs):
            p.error("give agent folders or --all")
        deploy(args)
    else:
        remove(args)


if __name__ == "__main__":
    main()
