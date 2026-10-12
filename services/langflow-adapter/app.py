"""Langflow AG-UI adapter: standard AG-UI (incl. interrupts / resume) in front of Langflow's Workflow API.

agentgateway routes Langflow agents here (POST /run) after authenticating the user. The gateway sets:
  x-langflow-flow-id   which flow to run
  x-api-key            the Langflow runtime key (passed through; the adapter holds no secret)
  x-end-user-id        the end user (Langflow scopes memory per end user and thread)

Run:     RunAgentInput → flows that can pause (Human Input, tool approval): background job + its event stream;
         all other flows: stream mode (token streaming)
Pause:   langflow.human_input_required → RUN_FINISHED {outcome: interrupt}
Resume:  RunAgentInput.resume → POST /{job}/resume (or /stop when cancelled) → relay events after the pause
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

import translate

LANGFLOW_URL = os.getenv("LANGFLOW_URL", "http://langflow-runtime:7860").rstrip("/")
FORWARD_HEADERS = ("x-api-key", "x-end-user-id")

FLOW_CACHE_SECONDS = 30  # how quickly a newly published flow's pause capability is picked up

app = FastAPI(title="langflow-agui-adapter")
_flow_cache: dict[str, tuple[float, bool]] = {}


async def flow_can_pause(client: httpx.AsyncClient, flow_id: str, headers: dict) -> bool:
    hit = _flow_cache.get(flow_id)
    if hit and time.monotonic() - hit[0] < FLOW_CACHE_SECONDS:
        return hit[1]
    resp = await client.get(f"{LANGFLOW_URL}/api/v1/flows/{flow_id}", headers={"x-api-key": headers.get("x-api-key", "")})
    pause = resp.status_code == 200 and translate.can_pause(resp.json())
    _flow_cache[flow_id] = (time.monotonic(), pause)
    return pause


async def stream_mode(client: httpx.AsyncClient, body: dict, flow_id: str, headers: dict, rewrite) -> AsyncIterator[bytes]:
    """Flows that cannot pause: Langflow's stream mode, relayed with the client's ids (token streaming)."""
    req = {"flow_id": flow_id, "input_value": translate.last_user_text(body.get("messages") or []),
           "session_id": rewrite.thread_id, "mode": "stream", "stream_protocol": "agui"}
    async with client.stream("POST", f"{LANGFLOW_URL}/api/v2/workflows", headers={**headers, "Accept": "text/event-stream"},
                             json=req) as resp:
        if resp.status_code != 200:
            yield sse(rewrite.error(f"Langflow {resp.status_code}: {(await resp.aread())[:300]!r}"))
            return
        data_lines: list[str] = []
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line == "" and data_lines:
                for out in rewrite(json.loads("\n".join(data_lines)), None):
                    yield sse(out)
                data_lines = []
                if rewrite.done:
                    return
    if not rewrite.done:
        yield sse(rewrite.error("Langflow stream ended without RUN_FINISHED"))


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


def sse(event: dict) -> bytes:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n".encode()


async def langflow_events(client: httpx.AsyncClient, job_id: str, headers: dict, after: str | None):
    """Yield (event, event_id) from a Langflow job's AG-UI event stream, starting after `after`."""
    h = {**headers, "Accept": "text/event-stream"}
    if after:
        h["Last-Event-ID"] = after
    url = f"{LANGFLOW_URL}/api/v2/workflows/{job_id}/events"
    async with client.stream("GET", url, params={"stream_protocol": "agui"}, headers=h) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"Langflow events {resp.status_code}: {(await resp.aread())[:300]!r}")
        data_lines: list[str] = []
        event_id: str | None = None
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line.startswith("id:"):
                event_id = line[3:].strip()
            elif line == "" and data_lines:
                yield json.loads("\n".join(data_lines)), event_id
                data_lines, event_id = [], None
        if data_lines:
            yield json.loads("\n".join(data_lines)), event_id


async def run_stream(body: dict, flow_id: str, headers: dict) -> AsyncIterator[bytes]:
    thread_id = body.get("threadId") or str(uuid.uuid4())
    run_id = body.get("runId") or str(uuid.uuid4())
    resume = body.get("resume") or []
    timeout = httpx.Timeout(30, read=None)  # a run may stream for minutes between events

    async with httpx.AsyncClient(timeout=timeout) as client:
        after: str | None = None
        if resume:
            entry = resume[0]
            try:
                ref = translate.decode_interrupt_id(str(entry.get("interruptId", "")))
            except ValueError as exc:
                yield sse({"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id})
                yield sse({"type": "RUN_ERROR", "message": f"cannot resume: {exc}"})
                return
            job_id, after = ref["job"], ref.get("ev")
            rewrite = translate.EventRewriter(thread_id, run_id, job_id)
            yield sse(rewrite.started())
            if entry.get("status") == "cancelled":
                await client.post(f"{LANGFLOW_URL}/api/v2/workflows/stop", headers=headers, json={"job_id": job_id})
                yield sse({"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id})
                return
            try:
                decision = translate.decision_from_resume(entry)
            except ValueError as exc:
                yield sse(rewrite.error(str(exc)))
                return
            resp = await client.post(f"{LANGFLOW_URL}/api/v2/workflows/{job_id}/resume", headers=headers,
                                     json={"request_id": ref["req"], "decision": decision})
            if resp.status_code != 200:
                yield sse(rewrite.error(f"Langflow resume {resp.status_code}: {resp.text[:300]}"))
                return
        elif not await flow_can_pause(client, flow_id, headers):
            rewrite = translate.EventRewriter(thread_id, run_id, job_id="")
            yield sse(rewrite.started())
            try:
                async for chunk in stream_mode(client, body, flow_id, headers, rewrite):
                    yield chunk
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                yield sse(rewrite.error(f"Langflow stream failed: {exc}"))
            return
        else:
            resp = await client.post(f"{LANGFLOW_URL}/api/v2/workflows", headers=headers, json={
                "flow_id": flow_id,
                "input_value": translate.last_user_text(body.get("messages") or []),
                "session_id": thread_id,
                "mode": "background",
                "stream_protocol": "agui",
            })
            if resp.status_code >= 300:
                yield sse({"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id})
                yield sse({"type": "RUN_ERROR", "message": f"Langflow {resp.status_code}: {resp.text[:300]}"})
                return
            job_id = resp.json()["job_id"]
            rewrite = translate.EventRewriter(thread_id, run_id, job_id)
            yield sse(rewrite.started())

        try:
            async for event, event_id in langflow_events(client, job_id, headers, after):
                for out in rewrite(event, event_id):
                    yield sse(out)
                if rewrite.done:
                    return
        except (httpx.HTTPError, RuntimeError, json.JSONDecodeError) as exc:
            yield sse(rewrite.error(f"Langflow stream failed: {exc}"))
            return
        if not rewrite.done:
            yield sse(rewrite.error("Langflow stream ended without RUN_FINISHED"))


@app.post("/run")
async def run(request: Request) -> StreamingResponse:
    flow_id = request.headers.get("x-langflow-flow-id")
    if not flow_id:
        raise HTTPException(400, "x-langflow-flow-id header missing (set by the gateway route)")
    headers = {h: request.headers[h] for h in FORWARD_HEADERS if h in request.headers}
    body = await request.json()
    return StreamingResponse(run_stream(body, flow_id, headers), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
