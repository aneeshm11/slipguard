"""The vLLM plugin, loaded exactly as `--tool-parser-plugin` / `--reasoning-parser-plugin` load it (CPU only).
Runs where vLLM is importable and SLIPGUARD_MODEL_DIR points at a Gemma 4 model dir (tokenizer)."""
import json
import os

import pytest

vllm = pytest.importorskip("vllm")
MD = os.environ.get("SLIPGUARD_MODEL_DIR")
if not MD:
    pytest.skip("set SLIPGUARD_MODEL_DIR", allow_module_level=True)

from slipguard._vendor.gemmaproto import STR, render_call  # noqa: E402
from slipguard.integrations import plugin_path  # noqa: E402

EDIT = render_call("edit_file", {"filepath": "a.py", "new_string": "x = 1", "old_string": "x = 0"})
SLIP = EDIT.replace("x = 1" + STR + ",old", "x = 1`,old")
TOOLS = [{"type": "function", "function": {"name": "edit_file", "parameters": {"type": "object", "properties": {
    "filepath": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}},
    "required": ["filepath", "old_string", "new_string"]}}}]


@pytest.fixture(scope="module")
def env():
    from transformers import AutoTokenizer
    from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest
    from vllm.reasoning.abs_reasoning_parsers import ReasoningParserManager
    from vllm.tool_parsers.abstract_tool_parser import ToolParserManager
    ToolParserManager.import_tool_parser(plugin_path("vllm"))
    ReasoningParserManager.import_reasoning_parser(plugin_path("vllm"))
    tok = AutoTokenizer.from_pretrained(MD)
    req = ChatCompletionRequest(model="m", messages=[{"role": "user", "content": "x"}], tools=TOOLS, tool_choice="auto")
    return {"TP": ToolParserManager.get_tool_parser("gemma4_strict"),
            "TPS": ToolParserManager.get_tool_parser("gemma4_strict_schema"),
            "RP": ReasoningParserManager.get_reasoning_parser("gemma4_strict"), "tok": tok, "req": req}


def _stream(env, text, cls="TP"):
    tok, req = env["tok"], env["req"]
    tp = env[cls](tok, req.tools)
    ids = tok.encode(text, add_special_tokens=False)
    stop = tok.convert_tokens_to_ids("<|tool_response>")
    prev, calls, content = "", [], []
    for k, t in enumerate(ids + [stop]):
        dt = tok.decode([t], skip_special_tokens=False) if k < len(ids) else ""
        dm = tp.extract_tool_calls_streaming(prev, prev + dt, dt, [], [], [t], req)
        prev += dt
        if dm is not None:
            content += [dm.content] if dm.content else []
            calls += [(d.function.name, json.loads(d.function.arguments)) for d in dm.tool_calls or []]
    return calls, "".join(content) or None


def test_registered_and_adjusts_request(env):
    tp = env["TP"](env["tok"], env["req"].tools)
    assert tp.adjust_request(env["req"]).skip_special_tokens is False


@pytest.mark.parametrize("text", ["ok " + EDIT, EDIT + EDIT, "a " + SLIP, EDIT + " b " + SLIP, EDIT[:-5]])
def test_streaming_equals_nonstreaming(env, text):
    tp = env["TP"](env["tok"], env["req"].tools)
    info = tp.extract_tool_calls(text, env["req"])
    ns_calls = [(c.function.name, json.loads(c.function.arguments)) for c in info.tool_calls]
    s_calls, s_content = _stream(env, text)
    assert s_calls == ns_calls
    if info.tools_called:
        assert (info.content or "").strip() == (s_content or "").strip()
    else:
        assert info.content == text and s_content == text


def test_slip_is_returned_as_content_never_as_a_call(env):
    tp = env["TP"](env["tok"], env["req"].tools)
    info = tp.extract_tool_calls(SLIP, env["req"])
    assert not info.tools_called and info.content == SLIP


def test_ids_are_marked_strict(env):
    tp = env["TP"](env["tok"], env["req"].tools)
    assert tp.extract_tool_calls(EDIT, env["req"]).tool_calls[0].id.endswith("-ggok")


def test_schema_parser(env):
    bad = render_call("edit_file", {"filepath": "a.py", "new_string": "x"})
    assert env["TP"](env["tok"], env["req"].tools).extract_tool_calls(bad, env["req"]).tools_called
    assert not env["TPS"](env["tok"], env["req"].tools).extract_tool_calls(bad, env["req"]).tools_called


def test_reasoning_split_never_resplits_content(env):
    rp = env["RP"](env["tok"])
    r, c = rp.extract_reasoning("<|channel>thought\nplan<channel|>" + EDIT + " tail <|channel>x", env["req"])
    assert r == "plan" and c == EDIT + " tail <|channel>x"
    r, c = rp.extract_reasoning("prefilled plan<channel|>" + EDIT, env["req"])
    assert r == "prefilled plan" and c == EDIT
    assert rp.extract_reasoning(EDIT, env["req"]) == (None, EDIT)


def test_repair_parser_marks_ids_and_streams_identically(env):
    from vllm.tool_parsers.abstract_tool_parser import ToolParserManager
    TPR = ToolParserManager.get_tool_parser("gemma4_strict_repair")
    tp = TPR(env["tok"], env["req"].tools)
    info = tp.extract_tool_calls("a " + SLIP + " b", env["req"])
    assert info.tools_called and info.tool_calls[0].id.endswith("-ggrepaired")
    assert json.loads(info.tool_calls[0].function.arguments)["old_string"] == "x = 0"
    env2 = dict(env, TPR=TPR)
    calls, content = _stream(env2, "a " + SLIP + " b", cls="TPR")
    assert calls == [(c.function.name, json.loads(c.function.arguments)) for c in info.tool_calls]
