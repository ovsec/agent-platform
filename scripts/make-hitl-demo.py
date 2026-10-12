# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27"]
# ///
"""Generate the "HITL demo" flow: Chat Input → Human Input (Approve / Reject) → "✅ Approved: …" / "❌ Rejected: …".

No model involved, so it is a deterministic test of human-in-the-loop through the platform.
Node templates come from the running Langflow's registry. Writes test-agents/hitl-demo/flow.json; deploy it with
  uv run scripts/publish.py deploy test-agents/hitl-demo
"""

import copy
import json

import langflow_lib as lf

ROOT = lf.ROOT

FLOW_ID = "7d1e2c3b-4a5f-4e6d-9c8b-0a1b2c3d4e5f"


def main() -> None:
    reg = lf.registry()
    nodes, edges = [], []

    def add(type_key: str, node_id: str, x: int, y: int, **values) -> dict:
        node = copy.deepcopy(reg[type_key])
        for field, value in values.items():
            node["template"][field]["value"] = value
        nodes.append({"id": node_id, "type": "genericNode", "position": {"x": x, "y": y},
                      "data": {"id": node_id, "type": type_key, "node": node}})
        return node

    def connect(*args):
        edges.append(lf.edge(*args))

    add("ChatInput", "ChatInput-hitl", 0, 200)
    add("HumanInput", "HumanInput-hitl", 400, 200, decisions=["Approve", "Reject"])
    # each branch says which decision was taken, then echoes the request
    add("CombineText", "CombineText-approved", 850, 50, text1="✅ Approved:", delimiter=" ")
    add("CombineText", "CombineText-rejected", 850, 350, text1="❌ Rejected:", delimiter=" ")
    add("ChatOutput", "ChatOutput-approved", 1250, 50)
    add("ChatOutput", "ChatOutput-rejected", 1250, 350)
    out_types = ["Data", "JSON", "DataFrame", "Table", "Message"]
    connect("ChatInput-hitl", "ChatInput", "message", ["Message"], "HumanInput-hitl", "prompt", ["Message"], "str")
    for branch in ("approve", "reject"):
        combine = {"approve": "CombineText-approved", "reject": "CombineText-rejected"}[branch]
        output = {"approve": "ChatOutput-approved", "reject": "ChatOutput-rejected"}[branch]
        connect("HumanInput-hitl", "HumanInput", f"branch_{branch}", ["Message"], combine, "text2", ["Message"], "str")
        connect(combine, "CombineText", "combined_text", ["Message"], output, "input_value", out_types, "other")

    flow = {"id": FLOW_ID, "name": "HITL Demo", "endpoint_name": "hitl-demo", "icon": "Hand",
            "description": "Test agent: pauses every request for a human Approve / Reject decision.",
            "tags": [], "is_component": False,
            "data": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.8}}}
    out = ROOT / "test-agents" / "hitl-demo" / "flow.json"
    out.write_text(json.dumps(flow, indent=2))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
