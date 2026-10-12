"""Pure translation between standard AG-UI and Langflow's Workflow API (no I/O, unit-tested).

Langflow (1.12) streams AG-UI events, but signals a human-in-the-loop pause with its own
CUSTOM `langflow.human_input_required` event on a *background* job, and resumes through
POST /api/v2/workflows/{job_id}/resume. Standard AG-UI (what portals like assistant-ui speak)
ends the run with RUN_FINISHED outcome {type: "interrupt", interrupts: [...]} and resumes with
a new run whose RunAgentInput carries `resume: [{interruptId, status, payload}]`.

The adapter is stateless: everything needed to resume (job id, Langflow request id, the SSE event id
to continue after) travels inside the interrupt id handed to the client.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta
from typing import Any

INTERRUPT_PREFIX = "lf."
HUMAN_INPUT_EVENT = "langflow.human_input_required"


def can_pause(flow: dict) -> bool:
    """True when a flow can suspend for a human: a Human Input node, or a tool that requires approval.

    Pausing only works for background jobs; flows that cannot pause run in stream mode, which streams
    tokens as they are generated (background mode delivers each message in one piece).
    """
    for node in (flow.get("data") or {}).get("nodes") or []:
        data = node.get("data") or {}
        if data.get("type") == "HumanInput":
            return True
        if _approval_flag(data.get("node") or {}):
            return True
    return False


def _approval_flag(value: Any) -> bool:
    """A tool action gated for approval: Langflow stores `approval_actions` (approve/edit/reject/respond)."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "approval_actions" and isinstance(v, list) and v:
                return True
            if _approval_flag(v):
                return True
    elif isinstance(value, list):
        return any(_approval_flag(v) for v in value)
    return False


def last_user_text(messages: list[dict]) -> str:
    """Text of the latest user message; AG-UI content is a string or a list of parts."""
    for message in reversed(messages or []):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def encode_interrupt_id(job_id: str, request_id: str, event_id: str | None) -> str:
    raw = json.dumps({"job": job_id, "req": request_id, "ev": event_id}, separators=(",", ":")).encode()
    return INTERRUPT_PREFIX + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_interrupt_id(interrupt_id: str) -> dict:
    if not interrupt_id.startswith(INTERRUPT_PREFIX):
        raise ValueError("not a Langflow interrupt id")
    b64 = interrupt_id[len(INTERRUPT_PREFIX):]
    data = json.loads(base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4)))
    if not isinstance(data, dict) or not data.get("job") or not data.get("req"):
        raise ValueError("incomplete Langflow interrupt id")
    return data


def interrupt_from_human_input(value: dict, *, job_id: str, event_id: str | None) -> dict:
    """Langflow's human_input_required payload → one standard AG-UI interrupt."""
    options = [o for o in value.get("options") or [] if isinstance(o, dict) and o.get("action_id")]
    allowed = value.get("allowed_decisions") or [o["action_id"] for o in options]
    kind = str(value.get("kind") or "")
    tool_call_id = value.get("tool_call_id") or value.get("toolCallId")
    # Agent tool approval (kind tool_approval): the pending call(s) come as action_requests [{name, args, ...}]
    action = (value.get("action_requests") or [{}])[0] or {}
    if action.get("name") and not value.get("tool_name"):
        value = {**value, "tool_name": action["name"], "tool_args": action.get("args")}
    tool_call_id = tool_call_id or action.get("id") or action.get("tool_call_id")
    interrupt: dict[str, Any] = {
        "id": encode_interrupt_id(job_id, str(value["request_id"]), event_id),
        "reason": "tool_call" if (tool_call_id or "tool" in kind) else "input_required",
        "message": str(value.get("prompt") or value.get("message") or "Your decision is needed to continue."),
        "responseSchema": {
            "type": "object",
            "properties": {
                "action_id": {
                    "type": "string",
                    "title": "Decision",
                    "enum": allowed,
                    "x-labels": {o["action_id"]: o.get("label") or o["action_id"] for o in options},
                },
            },
            "required": ["action_id"],
        },
        "metadata": {
            "runtime": "langflow",
            "kind": kind,
            "options": options,
            "fallbackAction": value.get("fallback_action"),
            **({"tool": value["tool_name"]} if value.get("tool_name") else {}),
            **({"toolArgs": value["tool_args"]} if value.get("tool_args") is not None else {}),
        },
    }
    if tool_call_id:
        interrupt["toolCallId"] = str(tool_call_id)
    expires = _expires_at(value.get("paused_at"), value.get("timeout_seconds"))
    if expires:
        interrupt["expiresAt"] = expires
    return interrupt


def _expires_at(paused_at: Any, timeout_seconds: Any) -> str | None:
    try:
        start = datetime.fromisoformat(str(paused_at))
        return (start + timedelta(seconds=float(timeout_seconds))).isoformat()
    except (TypeError, ValueError):
        return None


def decision_from_resume(entry: dict) -> dict:
    """AG-UI resume entry payload → Langflow decision ({"action_id": ...})."""
    payload = entry.get("payload")
    if isinstance(payload, dict) and payload.get("action_id"):
        return {k: v for k, v in payload.items() if v is not None}
    if isinstance(payload, str) and payload:
        return {"action_id": payload}
    raise ValueError("resume payload must be {\"action_id\": ...} or an action id string")


class EventRewriter:
    """Turns one Langflow AG-UI job stream into one standard AG-UI run for the client.

    - the client's threadId/runId replace Langflow's (`<end user>::<thread>`, job id)
    - Langflow's RUN_STARTED events (one per attach/resume) are dropped; the adapter emits its own once
    - the human-input CUSTOM event becomes RUN_FINISHED with an interrupt outcome (terminal)
    - other Langflow-internal CUSTOM events (`langflow.*`) are dropped
    """

    def __init__(self, thread_id: str, run_id: str, job_id: str) -> None:
        self.thread_id, self.run_id, self.job_id = thread_id, run_id, job_id
        self.done = False

    def started(self) -> dict:
        return {"type": "RUN_STARTED", "threadId": self.thread_id, "runId": self.run_id}

    def error(self, message: str) -> dict:
        self.done = True
        return {"type": "RUN_ERROR", "message": message}

    def __call__(self, event: dict, event_id: str | None) -> list[dict]:
        etype = event.get("type")
        if etype == "RUN_STARTED":
            return []
        if etype == "CUSTOM" and event.get("name") == HUMAN_INPUT_EVENT:
            self.done = True
            interrupt = interrupt_from_human_input(event.get("value") or {}, job_id=self.job_id, event_id=event_id)
            return [{"type": "RUN_FINISHED", "threadId": self.thread_id, "runId": self.run_id,
                     "outcome": {"type": "interrupt", "interrupts": [interrupt]}}]
        if etype == "CUSTOM" and str(event.get("name", "")).startswith("langflow."):
            return []  # Langflow-internal side channel (logs, content blocks, ...): meaningless to AG-UI clients
        if etype in ("RUN_FINISHED", "RUN_ERROR"):
            self.done = True
        if "threadId" in event:
            event = {**event, "threadId": self.thread_id}
        if "runId" in event:
            event = {**event, "runId": self.run_id}
        return [event]
