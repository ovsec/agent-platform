import pytest

import translate

HUMAN_INPUT = {
    "kind": "node_input",
    "prompt": "Please delete iFlow X",
    "options": [{"label": "Approve", "action_id": "approve"}, {"label": "Reject", "action_id": "reject"}],
    "paused_at": "2026-10-10T14:12:05.761187+00:00",
    "request_id": "HumanInput-hitl:d9d7c98b-5a7e-418f-9f39-3df00fb10584",
    "fallback_action": None,
    "timeout_seconds": 259200,
    "allowed_decisions": ["approve", "reject"],
}


def test_last_user_text_string_and_parts():
    assert translate.last_user_text([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]) == "a"
    parts = [{"type": "text", "text": "x"}, {"type": "binary", "id": "f"}, {"type": "text", "text": "y"}]
    assert translate.last_user_text([{"role": "user", "content": parts}]) == "x\ny"
    assert translate.last_user_text([]) == ""


def test_interrupt_id_round_trip_keeps_colons():
    iid = translate.encode_interrupt_id("job-1", "HumanInput-hitl:job-1", "7")
    assert translate.decode_interrupt_id(iid) == {"job": "job-1", "req": "HumanInput-hitl:job-1", "ev": "7"}
    with pytest.raises(ValueError):
        translate.decode_interrupt_id("other-runtime-id")


def test_human_input_becomes_standard_interrupt():
    i = translate.interrupt_from_human_input(HUMAN_INPUT, job_id="d9d7", event_id="3")
    assert i["reason"] == "input_required"
    assert i["message"] == "Please delete iFlow X"
    assert i["responseSchema"]["properties"]["action_id"]["enum"] == ["approve", "reject"]
    assert i["responseSchema"]["properties"]["action_id"]["x-labels"]["approve"] == "Approve"
    assert i["expiresAt"].startswith("2026-10-13T14:12:05")
    assert translate.decode_interrupt_id(i["id"])["req"] == HUMAN_INPUT["request_id"]


def test_tool_approval_maps_to_tool_call_reason():
    i = translate.interrupt_from_human_input({**HUMAN_INPUT, "kind": "tool_approval", "tool_call_id": "tc1"},
                                             job_id="j", event_id=None)
    assert i["reason"] == "tool_call" and i["toolCallId"] == "tc1"


def test_decision_from_resume():
    assert translate.decision_from_resume({"payload": {"action_id": "approve"}}) == {"action_id": "approve"}
    assert translate.decision_from_resume({"payload": "reject"}) == {"action_id": "reject"}
    with pytest.raises(ValueError):
        translate.decision_from_resume({"payload": {}})


def test_rewriter_relabels_and_ends_on_pause():
    r = translate.EventRewriter("t1", "r1", "job")
    assert r({"type": "RUN_STARTED", "threadId": "alice::t1", "runId": "job"}, "0") == []
    msg = r({"type": "TEXT_MESSAGE_START", "messageId": "m", "role": "assistant"}, "1")
    assert msg == [{"type": "TEXT_MESSAGE_START", "messageId": "m", "role": "assistant"}]
    out = r({"type": "CUSTOM", "name": translate.HUMAN_INPUT_EVENT, "value": HUMAN_INPUT}, "2")
    assert r.done and out[0]["type"] == "RUN_FINISHED" and out[0]["threadId"] == "t1"
    assert out[0]["outcome"]["type"] == "interrupt"
    assert translate.decode_interrupt_id(out[0]["outcome"]["interrupts"][0]["id"])["ev"] == "2"


def test_rewriter_finishes_with_client_ids():
    r = translate.EventRewriter("t1", "r1", "job")
    assert r({"type": "RUN_FINISHED", "threadId": "alice::t1", "runId": "job"}, "9") == [
        {"type": "RUN_FINISHED", "threadId": "t1", "runId": "r1"}]
    assert r.done


def test_can_pause():
    assert translate.can_pause({"data": {"nodes": [{"data": {"type": "HumanInput", "node": {}}}]}})
    assert not translate.can_pause({"data": {"nodes": [{"data": {"type": "Agent", "node": {"template": {}}}}]}})
    gated = {"data": {"type": "APIRequest", "node": {"template": {"tools_metadata": {"value": [
        {"name": "make_api_request", "approval_actions": ["approve", "reject"]}]}}}}}
    assert translate.can_pause({"data": {"nodes": [gated]}})
    ungated = {"data": {"type": "APIRequest", "node": {"template": {"tools_metadata": {"value": [
        {"name": "make_api_request", "approval_actions": []}]}}}}}
    assert not translate.can_pause({"data": {"nodes": [ungated]}})


def test_agent_tool_approval_interrupt_shows_the_call():
    value = {**HUMAN_INPUT, "kind": "tool_approval", "prompt": "Approve tool call: make_api_request",
             "action_requests": [{"name": "make_api_request", "args": {"url_input": "http://x/monitor"}}]}
    i = translate.interrupt_from_human_input(value, job_id="j", event_id="4")
    assert i["reason"] == "tool_call"
    assert i["metadata"]["tool"] == "make_api_request"
    assert i["metadata"]["toolArgs"] == {"url_input": "http://x/monitor"}


def test_rewriter_drops_langflow_internal_custom_events():
    r = translate.EventRewriter("t1", "r1", "job")
    assert r({"type": "CUSTOM", "name": "langflow.log", "value": {}}, "1") == []
    assert r({"type": "CUSTOM", "name": "my.app.event", "value": 1}, "2") == [
        {"type": "CUSTOM", "name": "my.app.event", "value": 1}]
