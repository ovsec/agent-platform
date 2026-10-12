"""Shared Langflow helpers for the platform scripts (publish.py, make-*-demo.py).

- registry(): component templates from a running Langflow (/api/v1/all), so generated nodes always match
  the installed components
- handle(): Langflow's edge-handle encoding
- add_gateway_model(): route an Agent's model calls through agentgateway by connecting an
  "agentgateway Model" node (components/agentgateway) to its model input
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
GATEWAY_MODEL = "ext:agentgateway:AgentGatewayModelComponent@extra"
DEFAULT_MODEL = "ollama/qwen3:8b"


def handle(d: dict) -> str:
    return json.dumps(d, separators=(",", ":")).replace('"', "œ")


def registry() -> dict:
    url = os.getenv("LANGFLOW_RUNTIME_URL", "http://localhost:7880")
    key = os.getenv("LANGFLOW_RUNTIME_API_KEY") or (ROOT / ".secrets/langflow-runtime.key").read_text().strip()
    resp = httpx.get(f"{url}/api/v1/all", headers={"x-api-key": key}, timeout=60)
    resp.raise_for_status()
    return {k: v for cat in resp.json().values() for k, v in cat.items()}


def edge(src: str, src_type: str, out: str, out_types: list, dst: str, field: str, in_types: list, ftype: str) -> dict:
    sh = {"dataType": src_type, "id": src, "name": out, "output_types": out_types}
    th = {"fieldName": field, "id": dst, "inputTypes": in_types, "type": ftype}
    return {"id": f"xy-edge__{src}{handle(sh)}-{dst}{handle(th)}", "source": src, "target": dst,
            "sourceHandle": handle(sh), "targetHandle": handle(th),
            "data": {"sourceHandle": sh, "targetHandle": th},
            "className": "", "selected": False, "animated": False}


def add_gateway_model(flow: dict, template: dict, slug: str, model: str | None = None) -> int:
    """Connect an agentgateway Model node to every Agent; returns the number of Agents.

    Idempotent: an existing gateway model node is replaced, keeping its model name unless `model` is given.
    """
    nodes, edges = flow["data"]["nodes"], flow["data"]["edges"]
    agents = [n for n in nodes if n["data"]["type"] == "Agent"]
    for agent in agents:
        aid = agent["id"]
        mid = f"AgentGatewayModel-{aid.split('-')[-1]}"
        old = next((n for n in nodes if n["id"] == mid), None)
        current = old["data"]["node"]["template"]["model_name"]["value"] if old else None
        nodes[:] = [n for n in nodes if n["id"] != mid]
        edges[:] = [e for e in edges if not (e["target"] == aid and e["data"]["targetHandle"]["fieldName"] == "model")]

        node = copy.deepcopy(template)
        node["template"]["model_name"]["value"] = model or current or DEFAULT_MODEL
        node["template"]["agent_slug"]["value"] = slug
        x, y = agent["position"]["x"] - 450, agent["position"]["y"] - 250
        nodes.append({"id": mid, "type": "genericNode", "position": {"x": x, "y": y},
                      "data": {"id": mid, "type": GATEWAY_MODEL, "node": node, "selected_output": "model_output"}})
        edges.append(edge(mid, GATEWAY_MODEL, "model_output", ["LanguageModel"], aid, "model", ["LanguageModel"], "model"))
        agent["data"]["node"]["template"]["model"]["value"] = []  # the connected model is used
    return len(agents)
