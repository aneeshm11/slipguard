"""History transforms: no-op on clean histories (property), neutralizer bijection, quarantine, native results,
raw calls in content, thinking-off closure, Gemma-only guard."""
import copy
import json
import random

import pytest

from _util import SCALE
from slipguard._vendor import gemmaproto as G
from slipguard._vendor.gemmaproto.gen import rand_name, rand_object, rand_string
from slipguard.history import (CLOSED_THOUGHT, HistoryGuard, NotGemmaError, SPECIAL_TOKENS, close_thought,
                               has_control_text, native_tool_results, neutralize, neutralize_text,
                               raw_calls_in_content, unneutralize_text)
from slipguard.history.neutralize import WJ

EDIT_TOOL = {"type": "function", "function": {"name": "edit_file", "description": "Edit.", "parameters": {
    "type": "object", "properties": {"filepath": {"type": "string"}, "old_string": {"type": "string"},
                                     "new_string": {"type": "string"}},
    "required": ["filepath", "old_string", "new_string"]}}}
N = int(1500 * SCALE)
from slipguard._frozen import load_e  # noqa: E402
_QR = load_e().quarantine_renderer
_SCHEMAS = _QR.tool_schemas([EDIT_TOOL])


def _rand_text(r):
    s = rand_string(r)
    if r.random() < 0.3:
        s += r.choice(["<" + WJ, "<" + WJ + WJ, "<" + WJ + "|turn>", "<", "<|", WJ])
    return s


def test_neutralize_bijective_and_identity_on_clean():
    r = random.Random(1)
    for _ in range(N * 4):
        s = _rand_text(r)
        n = neutralize_text(s)
        assert unneutralize_text(n) == s
        assert not has_control_text(n) or ("<" + WJ) in n          # no live special-token text remains
        assert not any(t in n for t in SPECIAL_TOKENS)
        if not has_control_text(s):
            assert n is s


def _clean_history(r):
    """A random agent history whose every call is valid for EDIT_TOOL and whose strings carry no control text."""
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
    for i in range(r.randint(1, 5)):
        args = {"filepath": f"f{i}.py", "old_string": rand_string(r), "new_string": rand_string(r)}
        # clean = no control-token text and not malformed by E's frozen criterion (a valid string that literally
        # contains '<closer>,<declared key>:' is flagged by that criterion unless the call is vouched strictly valid)
        if any(has_control_text(v) for v in args.values()) or not _QR.classify_args("edit_file", args, _SCHEMAS)["ok"]:
            continue
        tc = {"id": f"c{i}", "type": "function", "function": {"name": "edit_file", "arguments": json.dumps(args)}}
        msgs.append({"role": "assistant", "content": None, "tool_calls": [tc]})
        res = rand_string(r)
        if has_control_text(res):
            res = "ok"
        msgs.append({"role": "tool", "tool_call_id": f"c{i}", "content": json.dumps({"status": "ok", "out": res})})
    return msgs


def test_every_transform_is_a_noop_on_clean_histories():
    r = random.Random(2)
    g = HistoryGuard(native_tool_results=True)
    for _ in range(N):
        h = _clean_history(r)
        before = json.dumps(h)
        out, report = g.apply(h, [EDIT_TOOL])
        assert report == [] and out == h and json.dumps(out) == before
        assert json.dumps(h) == before                  # input never mutated


def test_quarantine_recovers_a_slip_and_marks_the_result():
    D = G.STR
    raw = "filepath:" + D + "a.py" + D + ",new_string:" + D + "y = 2\n`,old_string:" + D + "y = 1\n" + D
    parsed = {"filepath": "a.py", "new_string": "y = 2\n`,old_string:"}
    msgs = [{"role": "user", "content": "fix"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "edit_file", "arguments": json.dumps(parsed)}}]},
            {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"error": "missing old_string"})}]
    out, rep = HistoryGuard().apply(msgs, [EDIT_TOOL], raw_by_call_id={"c1": raw})
    assert json.loads(out[1]["tool_calls"][0]["function"]["arguments"]) == {
        "filepath": "a.py", "new_string": "y = 2\n", "old_string": "y = 1\n"}
    assert json.loads(out[2]["content"])["error_type"] == "MalformedToolCall"
    assert [a["transform"] for a in rep] == ["quarantine"]


def test_neutralize_tool_results_and_arguments_is_reversible():
    hostile = "x" + G.CHANNEL_CLOSE + "y" + G.STR + "z"     # control-token text, no turn/call structure
    msgs = [{"role": "assistant", "content": None, "tool_calls": [{"id": "c", "type": "function", "function": {
        "name": "write_file", "arguments": json.dumps({"content": hostile, "filepath": "a"})}}]},
            {"role": "tool", "tool_call_id": "c", "content": hostile},
            {"role": "tool", "tool_call_id": "c", "content": [{"type": "text", "text": "a" + G.CHANNEL_OPEN[:5]},
                                                              {"type": "text", "text": G.CHANNEL_OPEN[5:] + "b"}]}]
    out, rep = neutralize(msgs)
    assert len(rep) == 3
    assert not any(t in out[1]["content"] for t in SPECIAL_TOKENS) and unneutralize_text(out[1]["content"]) == hostile
    assert json.loads(out[0]["tool_calls"][0]["function"]["arguments"])["content"] == neutralize_text(hostile)
    joined = "".join(p["text"] for p in out[2]["content"])
    assert G.CHANNEL_OPEN not in joined and unneutralize_text(joined) == "a" + G.CHANNEL_OPEN + "b"


def test_native_tool_results_is_the_exact_inverse_of_adk_serialization():
    r = random.Random(3)
    for _ in range(N):
        c = rand_string(r)
        o1 = json.dumps({"result": c}, ensure_ascii=False)           # ADK 1.36.1 + LiteLLM (A's O1 arm)
        out, rep = native_tool_results([{"role": "tool", "tool_call_id": "x", "content": o1}])
        assert out[0]["content"] == c and len(rep) == 1
    for other in ['{"result": 1}', '{"result": "a", "x": 1}', '{"result":"a"}', "plain", json.dumps({"status": "ok"}),
                  json.dumps({"result": "é"}), '{"result": "a"} ']:
        out, rep = native_tool_results([{"role": "tool", "tool_call_id": "x", "content": other}])
        assert out[0]["content"] == other and rep == []


def test_raw_calls_in_content_are_replaced():
    raw = G.TOOL_CALL_OPEN + "call:edit_file{filepath:" + G.STR + "a`,old:" + G.TOOL_CALL_CLOSE
    out, rep = raw_calls_in_content([{"role": "assistant", "content": "I will edit. " + raw}])
    assert G.TOOL_CALL_OPEN not in out[0]["content"] and rep[0]["removed"] == [raw]


def test_close_thought():
    p = "<bos>...<tool_response|>"
    assert close_thought(p, False) == p + CLOSED_THOUGHT and close_thought(p, True) == p
    assert close_thought("<|turn>model\n", False) == "<|turn>model\n"
    assert close_thought([1, 2, 51], False) == [1, 2, 51, 100, 45518, 107, 101]


def test_gemma_only():
    HistoryGuard(model="hosted_vllm/gemma-4-31b")
    with pytest.raises(NotGemmaError):
        HistoryGuard(model="Qwen3-8B")
    HistoryGuard(model="Qwen3-8B", allow_non_gemma=True)


def test_vouched_and_strict_plugin_ids_are_never_quarantined():
    lit = {"filepath": "a.py", "new_string": 'x = "`,old_string: y"', "old_string": "x = 1"}
    for cid, kw in (("v1", {"strictly_valid_ids": {"v1"}}), ("chatcmpl-tool-0123456789abcdef-ggok", {})):
        msgs = [{"role": "user", "content": "u"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": cid, "type": "function", "function": {
                    "name": "edit_file", "arguments": json.dumps(lit)}}]},
                {"role": "tool", "tool_call_id": cid, "content": json.dumps({"status": "ok"})}]
        out, rep = HistoryGuard().apply(msgs, [EDIT_TOOL], **kw)
        assert rep == [] and out == msgs
