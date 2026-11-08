"""End to end: a real ADK Runner (google-adk) -> guarded_lite_llm -> LiteLLM (hosted_vllm provider) -> a local stub
OpenAI server. The tool's result contains control-token text; the second request the server receives must carry it
neutralized, and the ADK session must keep the original."""
import asyncio
import json
import socket

import pytest

pytest.importorskip("google.adk")
pytest.importorskip("aiohttp")
from aiohttp import web  # noqa: E402

from slipguard._vendor import gemmaproto as G  # noqa: E402
from slipguard.history.neutralize import SPECIAL_TOKENS  # noqa: E402

HOSTILE = "line 1\n" + G.CHANNEL_CLOSE + " line 2"      # control-token text (class-level; payloads: tests/private)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_adk_runner_with_guarded_lite_llm():
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from slipguard.integrations.adk import guarded_lite_llm

    seen = []

    async def chat(request):
        body = await request.json()
        seen.append(body)
        if len(seen) == 1:
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1-ggok", "type": "function",
                   "function": {"name": "read_file", "arguments": json.dumps({"filepath": "a.txt"})}}]}
            fin = "tool_calls"
        else:
            msg = {"role": "assistant", "content": "done"}
            fin = "stop"
        return web.json_response({"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                                  "choices": [{"index": 0, "message": msg, "finish_reason": fin}],
                                  "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})

    def read_file(filepath: str) -> str:
        """Read a file."""
        return HOSTILE

    async def main():
        app = web.Application()
        app.router.add_post("/v1/chat/completions", chat)
        runner_ = web.AppRunner(app)
        await runner_.setup()
        port = _free_port()
        site = web.TCPSite(runner_, "127.0.0.1", port)
        await site.start()
        try:
            agent = LlmAgent(name="coder", tools=[read_file], instruction="Use the tools.",
                             model=guarded_lite_llm("hosted_vllm/gemma-4-31b", api_base=f"http://127.0.0.1:{port}/v1",
                                                    api_key="x"))
            runner = InMemoryRunner(agent=agent, app_name="t")
            session = await runner.session_service.create_session(app_name="t", user_id="u")
            async for _ in runner.run_async(user_id="u", session_id=session.id,
                                            new_message=types.Content(role="user", parts=[types.Part(text="read a.txt")])):
                pass
            sess = await runner.session_service.get_session(app_name="t", user_id="u", session_id=session.id)
            return sess, agent
        finally:
            await runner_.cleanup()

    sess, agent = asyncio.run(main())
    assert len(seen) == 2
    tool_msgs = [m for m in seen[1]["messages"] if m.get("role") in ("tool", "tool_responses")]
    assert tool_msgs and not any(t in json.dumps(tool_msgs, ensure_ascii=False) for t in SPECIAL_TOKENS)
    stored = [p.function_response.response for e in sess.events for p in (e.content.parts if e.content else [])
              if getattr(p, "function_response", None)]
    assert stored and stored[0].get("result") == HOSTILE      # the session keeps the original
    assert any(a["transform"] == "neutralize" for a in agent.model.llm_client.last_report)
