"""The README's ADK history-guard snippet (task 2), run verbatim with real ADK objects: an InMemoryRunner turn through
guarded_lite_llm -> LiteLLM (hosted_vllm) -> a local stub OpenAI server. Only the api_base URL is replaced."""
import asyncio
import json
import os
import re
import socket

import pytest

README = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "README.md")
MARK = "<!-- verified: tests/test_readme_snippets.py"


def _snippet() -> str:
    if not os.path.exists(README):
        pytest.skip("README.md not next to the tests")
    text = open(README, encoding="utf-8").read()
    i = text.index(MARK)
    m = re.search(r"```python\n(.*?)```", text[i:], re.S)
    return m.group(1)


def test_readme_adk_snippet_is_short_and_self_contained():
    code = _snippet()
    lines = [l for l in code.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    assert 3 <= len(lines) <= 5 and "guarded_lite_llm" in code and "http://127.0.0.1:8000/v1" in code
    compile(code, "README-snippet", "exec")


def test_readme_adk_snippet_runs_with_real_adk():
    pytest.importorskip("google.adk")
    pytest.importorskip("litellm")
    pytest.importorskip("aiohttp")
    from aiohttp import web
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from slipguard._vendor import gemmaproto as G
    from slipguard.history.neutralize import SPECIAL_TOKENS

    hostile = "line 1\n" + G.CHANNEL_CLOSE + " line 2"      # control-token text in a tool result (class level)
    seen = []

    async def chat(request):
        body = await request.json()
        seen.append(body)
        if len(seen) == 1:
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1-ggok", "type": "function",
                   "function": {"name": "read_file", "arguments": json.dumps({"filepath": "a.txt"})}}]}
            fin = "tool_calls"
        else:
            msg, fin = {"role": "assistant", "content": "done"}, "stop"
        return web.json_response({"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                                  "choices": [{"index": 0, "message": msg, "finish_reason": fin}],
                                  "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})

    def read_file(filepath: str) -> str:
        """Read a file from the workspace."""
        return hostile

    async def main():
        app = web.Application()
        app.router.add_post("/v1/chat/completions", chat)
        srv = web.AppRunner(app)
        await srv.setup()
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        await web.TCPSite(srv, "127.0.0.1", port).start()
        try:
            ns = {"read_file": read_file}
            exec(_snippet().replace("http://127.0.0.1:8000/v1", f"http://127.0.0.1:{port}/v1"), ns)   # the README block
            agent = ns["agent"]
            runner = InMemoryRunner(agent=agent, app_name="t")
            sess = await runner.session_service.create_session(app_name="t", user_id="u")
            async for _ in runner.run_async(user_id="u", session_id=sess.id,
                                            new_message=types.Content(role="user", parts=[types.Part(text="read a.txt")])):
                pass
            return agent, await runner.session_service.get_session(app_name="t", user_id="u", session_id=sess.id)
        finally:
            await srv.cleanup()

    agent, sess = asyncio.run(main())
    assert len(seen) == 2                                      # tool call, then the answer after the tool result
    tool_msgs = [m for m in seen[1]["messages"] if m.get("role") in ("tool", "tool_responses")]
    assert tool_msgs and not any(t in json.dumps(tool_msgs, ensure_ascii=False) for t in SPECIAL_TOKENS)
    stored = [p.function_response.response for e in sess.events for p in (e.content.parts if e.content else [])
              if getattr(p, "function_response", None)]
    assert stored and stored[0].get("result") == hostile      # the ADK session keeps the original
    assert any(a["transform"] == "neutralize" for a in agent.model.llm_client.last_report)
