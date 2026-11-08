"""ADK (GuardedLiteLLMClient, SlipGuardPlugin) and LiteLLM (SlipGuardHook) integrations, without a network."""
import asyncio
import json

import pytest

from slipguard._vendor import gemmaproto as G
from slipguard.history.neutralize import SPECIAL_TOKENS

EDIT_TOOL = {"type": "function", "function": {"name": "edit_file", "description": "Edit.", "parameters": {
    "type": "object", "properties": {"filepath": {"type": "string"}, "old_string": {"type": "string"},
                                     "new_string": {"type": "string"}},
    "required": ["filepath", "old_string", "new_string"]}}}
HOSTILE = "x" + G.CHANNEL_CLOSE + "y"      # control-token text (class-level; payloads: tests/private)
CLEAN = [{"role": "user", "content": "u"},
         {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
             "name": "edit_file", "arguments": json.dumps({"filepath": "a", "old_string": "x", "new_string": "y"})}}]},
         {"role": "tool", "tool_call_id": "c1", "content": "ok"}]
DIRTY = CLEAN[:2] + [{"role": "tool", "tool_call_id": "c1", "content": HOSTILE}]


def test_litellm_hook_noop_on_clean_and_rewrites_dirty():
    pytest.importorskip("litellm")
    from slipguard.integrations.litellm_hook import SlipGuardHook
    h = SlipGuardHook()
    assert asyncio.run(h.async_pre_call_deployment_hook({"messages": CLEAN, "tools": [EDIT_TOOL]}, None)) is None
    out = asyncio.run(h.async_pre_call_deployment_hook({"messages": DIRTY, "tools": [EDIT_TOOL], "model": "m"}, None))
    assert out["model"] == "m" and not any(t in out["messages"][2]["content"] for t in SPECIAL_TOKENS)
    assert DIRTY[2]["content"] == HOSTILE        # caller's list untouched


def test_litellm_hook_runs_inside_acompletion():
    litellm = pytest.importorskip("litellm")
    from slipguard.integrations.litellm_hook import SlipGuardHook
    h = SlipGuardHook()
    litellm.callbacks = [h]
    try:
        asyncio.run(litellm.acompletion(model="openai/gemma-4-31b", messages=DIRTY, tools=[EDIT_TOOL],
                                        mock_response="done", api_key="x"))
    finally:
        litellm.callbacks = []
    assert any(a["transform"] == "neutralize" for a in h.last_report)


def test_adk_guarded_client_rewrites_the_messages_litellm_receives():
    pytest.importorskip("google.adk")
    from slipguard.integrations.adk import GuardedLiteLLMClient, guarded_lite_llm
    seen = {}

    class Capture(GuardedLiteLLMClient):
        pass

    async def fake(self, model, messages, tools, **kw):          # replaces LiteLLMClient.acompletion (no network)
        seen["messages"] = messages
        return "resp"
    import google.adk.models.lite_llm as L
    orig = L.LiteLLMClient.acompletion
    L.LiteLLMClient.acompletion = fake
    try:
        c = Capture()
        assert asyncio.run(c.acompletion("hosted_vllm/gemma-4", CLEAN, [EDIT_TOOL])) == "resp"
        assert seen["messages"] is CLEAN
        asyncio.run(c.acompletion("hosted_vllm/gemma-4", DIRTY, [EDIT_TOOL]))
        assert not any(t in seen["messages"][2]["content"] for t in SPECIAL_TOKENS)
    finally:
        L.LiteLLMClient.acompletion = orig
    assert guarded_lite_llm("hosted_vllm/gemma-4-31b").llm_client.__class__.__name__ == "GuardedLiteLLMClient"


def test_adk_plugin_neutralizes_copies_only():
    pytest.importorskip("google.adk")
    from google.adk.models.llm_request import LlmRequest
    from google.genai import types
    from slipguard.integrations.adk import SlipGuardPlugin
    resp = types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
        id="c1", name="read_file", response={"result": HOSTILE}))])
    req = LlmRequest(contents=[resp])
    asyncio.run(SlipGuardPlugin().before_model_callback(callback_context=None, llm_request=req))
    assert not any(t in req.contents[0].parts[0].function_response.response["result"] for t in SPECIAL_TOKENS)
    assert resp.parts[0].function_response.response["result"] == HOSTILE     # the session's object is untouched


def test_adk_plain_callback():
    pytest.importorskip("google.adk")
    from google.adk.models.llm_request import LlmRequest
    from google.genai import types
    from slipguard.integrations.adk import before_model_callback
    req = LlmRequest(contents=[types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
        id="c1", name="read_file", response={"result": HOSTILE}))])])
    assert asyncio.run(before_model_callback(callback_context=None, llm_request=req)) is None
    assert not any(t in req.contents[0].parts[0].function_response.response["result"] for t in SPECIAL_TOKENS)
