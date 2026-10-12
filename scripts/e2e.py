# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "pyyaml>=6"]
# ///
"""End-to-end check of the running local stack. Exit code 0 = all passed.

  uv run scripts/e2e.py                                   # platform checks (test-agents/hitl-demo deployed)
  uv run scripts/e2e.py --fast                            # same; kept for compatibility
  uv run scripts/e2e.py --model-agent invoice-monitor --prompt "How many invoices failed to post in the last 24h?"
                                                          # also run a deployed agent: model streaming + tool call

Covers: gateway auth (401/403), optionally an agent run with token streaming and a tool call, human-in-the-loop
(interrupt → approve / reject / cancel, other users cannot resume), the services gateway's API key, and the
audit log line with the user.
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = Path(os.getenv("CATALOG_DIR", ROOT / "catalog"))
GATEWAY = "http://localhost:4100"
SERVICES = "http://localhost:4102"
KEYCLOAK_TOKEN = "http://localhost:8180/realms/agents/protocol/openid-connect/token"

results: list[tuple[str, bool, str]] = []


def skip(name: str, why: str) -> None:
    print(f"SKIP  {name}  ({why})")


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))


def token(user: str) -> str:
    resp = httpx.post(KEYCLOAK_TOKEN, data={"grant_type": "password", "client_id": "agent-portal",
                                            "client_secret": "dev-only-agent-portal-secret",
                                            "username": user, "password": user, "scope": "openid"})
    resp.raise_for_status()
    return resp.json()["access_token"]


def run(slug: str, user_token: str | None, body: dict, timeout: float = 600) -> tuple[int, list[dict]]:
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream",
               "x-agui-thread-id": body.get("threadId", "")}
    if user_token:
        headers["Authorization"] = f"Bearer {user_token}"
    with httpx.stream("POST", f"{GATEWAY}/agents/{slug}/run", headers=headers, json=body, timeout=timeout) as r:
        events = [json.loads(line[5:]) for line in r.iter_lines() if line.startswith("data:")]
        return r.status_code, events


def ask(text: str, thread: str | None = None) -> dict:
    return {"threadId": thread or f"e2e-{uuid.uuid4().hex[:8]}", "runId": uuid.uuid4().hex,
            "messages": [{"id": "1", "role": "user", "content": text}], "tools": [], "context": [], "state": {},
            "forwardedProps": {}}


def resume(thread: str, interrupt_id: str, status: str, payload: dict | None = None) -> dict:
    entry = {"interruptId": interrupt_id, "status": status, **({"payload": payload} if payload else {})}
    return {"threadId": thread, "runId": uuid.uuid4().hex, "messages": [], "resume": [entry]}


def text(events: list[dict]) -> str:
    return "".join(e.get("delta", "") for e in events if e.get("type") == "TEXT_MESSAGE_CONTENT")


def interrupt_of(events: list[dict]) -> dict | None:
    for e in events:
        if e.get("type") == "RUN_FINISHED" and (e.get("outcome") or {}).get("type") == "interrupt":
            return e["outcome"]["interrupts"][0]
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fast", action="store_true", help="no effect: model checks only run with --model-agent")
    p.add_argument("--model-agent", help="deployed agent that calls a model and a tool")
    p.add_argument("--prompt", default="What can you do? Use a tool if you have one. One sentence.")
    args = p.parse_args()
    alice, bob, admin = token("alice"), token("bob"), token("admin")
    deployed = [yaml.safe_load(m.read_text()) for m in sorted(CATALOG_DIR.glob("*/agent.yaml"))]
    if "hitl-demo" not in {a["slug"] for a in deployed}:
        sys.exit("hitl-demo is not deployed: uv run scripts/publish.py deploy test-agents/hitl-demo")

    # gateway auth
    status, _ = run("hitl-demo", None, ask("hi"))
    check("no token → 401", status == 401, f"got {status}")
    # bob has only agent-user: any deployed agent without that role must be refused
    restricted = next((a["slug"] for a in deployed if "agent-user" not in a["access"]["roles"]), None)
    if restricted:
        status, _ = run(restricted, bob, ask("hi"))
        check(f"bob on {restricted} (role not granted) → 403", status == 403, f"got {status}")
    else:
        skip("role not granted → 403", "every deployed agent allows agent-user")

    # agent run with streaming and a tool call (admin may use every agent)
    if args.model_agent:
        thread = f"e2e-{uuid.uuid4().hex[:8]}"
        status, ev = run(args.model_agent, admin, ask(args.prompt, thread))
        deltas = sum(1 for e in ev if e.get("type") == "TEXT_MESSAGE_CONTENT")
        tools = [e.get("toolCallName") for e in ev if e.get("type") == "TOOL_CALL_START"]
        check(f"admin {args.model_agent} → 200, RUN_FINISHED", status == 200 and ev and ev[-1]["type"] == "RUN_FINISHED",
              f"{status} {ev[-1] if ev else 'no events'}")
        check("token streaming (> 5 text deltas)", deltas > 5, f"{deltas} deltas")
        check("tool call streamed", bool(tools), "no TOOL_CALL_START")
        check("thread id is the client's", {e.get("threadId") for e in ev if "threadId" in e} == {thread})
    else:
        skip("model streaming and tool call", "no --model-agent")

    # human in the loop
    for decision, expect in (("approve", "Approved"), ("reject", "Rejected")):
        thread = f"e2e-hitl-{uuid.uuid4().hex[:8]}"
        _, ev = run("hitl-demo", bob, ask(f"e2e {decision}", thread), timeout=120)
        intr = interrupt_of(ev)
        check(f"hitl-demo pauses with an interrupt ({decision})", intr is not None and intr["reason"] == "input_required")
        if intr:
            _, ev = run("hitl-demo", bob, resume(thread, intr["id"], "resolved", {"action_id": decision}), timeout=120)
            check(f"resume {decision} → '{expect}'", expect in text(ev), repr(text(ev)))
    thread = f"e2e-hitl-{uuid.uuid4().hex[:8]}"
    _, ev = run("hitl-demo", bob, ask("e2e cancel", thread), timeout=120)
    intr = interrupt_of(ev)
    if intr:
        _, ev = run("hitl-demo", bob, resume(thread, intr["id"], "cancelled"), timeout=120)
        check("cancel → RUN_FINISHED", bool(ev) and ev[-1]["type"] == "RUN_FINISHED", str(ev[-1:]))
        _, ev = run("hitl-demo", bob, ask("e2e other user", thread), timeout=120)
        intr = interrupt_of(ev)
        _, ev = run("hitl-demo", alice, resume(thread, intr["id"], "resolved", {"action_id": "approve"}), timeout=120)
        check("another user cannot resume the pause", bool(ev) and ev[-1]["type"] == "RUN_ERROR", str(ev[-1:]))

    # services gateway (LLM/MCP for runtimes)
    env = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if "=" in line and not line.startswith("#"))
    r = httpx.get(f"{SERVICES}/v1/models")
    check("services gateway without key → 401", r.status_code == 401, f"got {r.status_code}")
    r = httpx.get(f"{SERVICES}/v1/models", headers={"Authorization": f"Bearer {env['LANGFLOW_RUNTIME_GATEWAY_KEY']}"})
    check("services gateway with runtime key → 200", r.status_code == 200, f"got {r.status_code}")

    # audit line with the user
    logs = subprocess.run(["docker", "compose", "logs", "agentgateway", "--since", "15m", "--no-log-prefix"],
                          cwd=ROOT, capture_output=True, text=True).stdout
    check("audit log has hitl-demo runs by bob",
          any("route=default/agent-hitl-demo" in l and 'user.name="bob"' in l for l in logs.splitlines()))

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
