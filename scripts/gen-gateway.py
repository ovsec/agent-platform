# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Generate gateway/config.yaml from gateway/base.yaml + the deployed agents (<catalog>/<slug>/agent.yaml).

Every agent becomes `POST /agents/{slug}/run`, speaking standard AG-UI to the caller:
  runtime: langflow  → the Langflow AG-UI adapter (standard AG-UI incl. human-in-the-loop interrupts)
  runtime: agui      → native AG-UI endpoint (Pydantic AI, LangGraph, CrewAI), forwarded as is

Usage: uv run scripts/gen-gateway.py [--check]

CATALOG_DIR: folder of deployed agents (default catalog/, filled by scripts/publish.py deploy; agent-catalog/<env>
elsewhere).
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = Path(os.getenv("CATALOG_DIR", ROOT / "catalog"))
LANGFLOW_ADAPTER = "langflow-adapter:8080"
LANGFLOW_KEY_FILE = "/secrets/langflow-runtime.key"

# Platform admins can use every agent (platform.yaml, also read by the portal)
ADMIN_ROLES = yaml.safe_load((ROOT / "platform.yaml").read_text())["admin_roles"]


def authorization(agent: dict) -> dict:
    roles = agent["access"]["roles"] + ADMIN_ROLES
    return {"rules": [{"allow": f"jwt.roles.exists(r, r in {json.dumps(roles)})"}]}


def route(agent: dict) -> dict:
    slug = agent["slug"]
    policies = {
        "authorization": authorization(agent),
        # gap allowed between SSE frames (local models can be slow to first token)
        "timeout": {"responseIdleTimeout": "300s"},
    }
    runtime = agent["runtime"]
    if runtime == "langflow":
        # The Langflow AG-UI adapter speaks standard AG-UI (incl. interrupts/resume) and runs the flow as a
        # background job on the runtime; the gateway tells it which flow, and passes key and end user through.
        policies |= {
            "urlRewrite": {"path": {"full": "/run"}},
            "backendAuth": {"key": {"value": {"file": LANGFLOW_KEY_FILE}, "location": {"header": {"name": "x-api-key"}}}},
            "transformations": {"request": {
                "set": {
                    # end-user identity for Langflow memory scoping and model-call attribution
                    "x-end-user-id": "default(jwt.preferred_username, jwt.sub)",
                    "x-langflow-flow-id": json.dumps(agent["langflow"]["flow_id"]),  # CEL string literal
                },
                # the runtime authenticates the gateway by x-api-key; never forward the user's bearer token
                "remove": ["authorization"],
            }},
        }
        backend = LANGFLOW_ADAPTER
    elif runtime == "agui":
        policies |= {
            "urlRewrite": {"path": {"full": agent["agui"]["path"]}},
            "transformations": {"request": {"set": {"x-end-user-id": "jwt.sub"}}},
        }
        backend = agent["agui"]["host"]
    else:
        sys.exit(f"{slug}: unknown runtime {runtime!r}")
    return {
        "name": f"agent-{slug}",
        "matches": [{"path": {"exact": f"/agents/{slug}/run"}, "method": "POST"}],
        "policies": policies,
        "backends": [{"host": backend}],
    }


class LiteralDumper(yaml.SafeDumper):
    pass


LiteralDumper.add_representer(
    str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None)
)


# Runtimes and agents calling LLM/MCP on the services gateway authenticate with keys named <CLIENT>_GATEWAY_KEY
# (env or .env; never in the generated file: only their SHA-256 hashes are written). The client name becomes the
# `client` metadata in logs and analytics: LANGFLOW_RUNTIME_GATEWAY_KEY → langflow-runtime. Issuing a key to a new
# agent = adding one line to .env (openssl rand -hex 24) and regenerating.
KEY_SUFFIX = "_GATEWAY_KEY"


def client_name(var: str) -> str:
    return var.removesuffix(KEY_SUFFIX).lower().replace("_", "-")


def read_env() -> dict[str, str]:
    env = {}
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env | {k: v for k, v in os.environ.items() if k.endswith(KEY_SUFFIX) or k.endswith("_URL")}


def service_api_keys() -> dict:
    env = read_env()
    keys = [
        {"keyHash": "sha256:" + hashlib.sha256(value.encode()).hexdigest(), "metadata": {"client": client_name(var)}}
        for var, value in sorted(env.items())
        if var.endswith(KEY_SUFFIX) and value
    ]
    if not keys:
        sys.exit("no *_GATEWAY_KEY set (run scripts/init-env.sh): refusing to leave the services gateway open")
    return {"mode": "strict", "keys": keys}


# Public URLs (what browsers use and what tokens carry as `iss`); scripts/share.sh changes them in .env.
PUBLIC_URLS = {"PORTAL_URL": "http://localhost:3100", "IDP_URL": "http://localhost:8180",
               "GATEWAY_UI_URL": "http://localhost:4101"}


def main() -> None:
    env = read_env()
    base_text = (ROOT / "gateway/base.yaml").read_text()
    for var, default in PUBLIC_URLS.items():
        base_text = base_text.replace("${" + var + "}", env.get(var) or default)
    marker = "  services:\n    port: 4102\n"
    if marker not in base_text:
        sys.exit("gateway/base.yaml: services gateway not found")
    api_key = yaml.dump({"apiKey": service_api_keys()}, Dumper=LiteralDumper, sort_keys=False, width=200)
    base_text = base_text.replace(marker, marker + "".join(f"    {l}\n" for l in api_key.splitlines()))
    agents = [yaml.safe_load(p.read_text()) for p in sorted(CATALOG_DIR.glob("*/agent.yaml"))]
    routes = yaml.dump({"routes": [route(a) for a in agents]}, Dumper=LiteralDumper, sort_keys=False, width=200)
    out = (
        "# yaml-language-server: $schema=https://agentgateway.dev/schema/config\n"
        "# GENERATED by scripts/gen-gateway.py from gateway/base.yaml + catalog/*/agent.yaml. Do not edit.\n\n"
        + base_text + "\n" + routes
    )
    target = ROOT / "gateway/config.yaml"
    if "--check" in sys.argv:
        sys.exit(0 if target.exists() and target.read_text() == out else "gateway/config.yaml is stale")
    target.write_text(out)
    print(f"wrote {target.relative_to(ROOT)} ({len(agents)} agents)")


if __name__ == "__main__":
    main()
