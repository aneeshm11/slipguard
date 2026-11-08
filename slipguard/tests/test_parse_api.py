"""Unit tests for slipguard.parse (API shapes, error codes, per-call semantics, schema mode, safety)."""
import sys
import time

import pytest

from slipguard._vendor.gemmaproto import STR, TOOL_CALL_OPEN, TOOL_CALL_CLOSE, render_call
from slipguard.parse import (ERROR_CODES, ParseError, StreamParser, extract, parse_call, parse_completion)
from slipguard.parse.engine import MAX_DEPTH

D = STR
EDIT = render_call("edit_file", {"filepath": "a.py", "new_string": "x = 1", "old_string": "x = 0"})
SLIP = EDIT.replace("x = 1" + D + ",old", "x = 1`,old")
TOOLS = [{"type": "function", "function": {"name": "edit_file", "parameters": {"type": "object", "properties": {
    "filepath": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}},
    "required": ["filepath", "old_string", "new_string"]}}}]


def test_error_codes_are_the_spec_codes():
    assert len(ERROR_CODES) == 17


def test_parse_call_roundtrip_and_canonical():
    tc = parse_call(EDIT)
    assert tc.arguments == {"filepath": "a.py", "new_string": "x = 1", "old_string": "x = 0"} and tc.canonical


@pytest.mark.parametrize("text,code", [
    (SLIP, "EXPECTED_SEP"), (EDIT[:-3], "UNTERMINATED"), ("x" + EDIT, "NO_CALL_OPEN"), (EDIT + "x", "TRAILING_TEXT"),
    (TOOL_CALL_OPEN + "call:f(a:1)" + TOOL_CALL_CLOSE, "PAREN_OPENER"),
    (TOOL_CALL_OPEN + "call:f{a:True}" + TOOL_CALL_CLOSE, "INVALID_LITERAL"),
    (TOOL_CALL_OPEN + "call:f{a:1,a:2}" + TOOL_CALL_CLOSE, "DUPLICATE_KEY"),
])
def test_parse_call_errors(text, code):
    with pytest.raises(ParseError) as e:
        parse_call(text)
    assert e.value.code == code


def test_slip_is_loud_in_completion_mode():
    with pytest.raises(ParseError) as e:
        parse_completion("thinking done " + SLIP)
    assert e.value.code == "EXPECTED_SEP"


def test_per_call_delivers_calls_before_the_first_error_and_returns_the_rest_verbatim():
    text = "a " + EDIT + " b " + SLIP + " c " + EDIT
    ex = extract(text)
    assert len(ex.calls) == 1 and ex.calls[0].span == (2, 2 + len(EDIT))
    assert ex.content == "a " + " b " + SLIP + " c " + EDIT   # nothing after the error is delivered as a call
    assert [e.code for e in ex.errors] == ["EXPECTED_SEP"] and not ex.ok


def test_per_call_on_valid_text_equals_completion():
    text = "x " + EDIT + EDIT
    ex, pc = extract(text), parse_completion(text)
    assert [c.span for c in ex.calls] == [c.span for c in pc.calls] and ex.ok


def test_string_opacity():
    inner = TOOL_CALL_CLOSE + "x" + TOOL_CALL_OPEN      # control tokens inside a string are content
    text = render_call("write_file", {"content": "a" + inner + "b", "filepath": "f"})
    pc = parse_completion(text)
    assert len(pc.calls) == 1 and pc.calls[0].arguments["content"] == "a" + inner + "b"
    assert len(extract(text).calls) == 1


def test_deep_nesting_is_a_parse_error_even_with_a_small_stack():
    deep = TOOL_CALL_OPEN + "call:f{a:" + "[" * (MAX_DEPTH + 5) + "]" * (MAX_DEPTH + 5) + "}" + TOOL_CALL_CLOSE
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(120)        # no recursion in the engine
    try:
        with pytest.raises(ParseError) as e:
            parse_completion(deep)
    finally:
        sys.setrecursionlimit(old)
    assert e.value.code == "TOO_DEEP"


def test_linear_time_many_arguments():
    def t(k):
        text = render_call("f", {f"k{i}": f"v{i}" for i in range(k)})
        t0 = time.perf_counter()
        parse_completion(text)
        return time.perf_counter() - t0
    a, b = t(2000), t(16000)
    assert b < 20 * max(a, 1e-3)      # 8x input: linear ~8x; quadratic would be ~64x


def test_streaming_events_and_one_delta_per_call():
    sp = StreamParser(mode="per_call")
    evs = []
    for ch in ("pre " + EDIT):
        evs += sp.feed(ch)
    evs += sp.finish()
    kinds = [e[0] for e in evs]
    assert kinds.count("call_end") == 1 and "".join(e[1] for e in evs if e[0] == "content") == "pre "


def test_schema_mode():
    bad = render_call("edit_file", {"filepath": "a.py", "new_string": "x"})          # old_string missing
    assert extract(bad).calls and not extract(bad, TOOLS, validate="schema").calls
    assert extract(bad, TOOLS, validate="schema").errors[0].code == "MISSING_REQUIRED"
    assert extract(render_call("rm", {}), TOOLS, validate="declared").errors[0].code == "UNDECLARED_TOOL"
    assert extract(EDIT, TOOLS, validate="schema").calls


def test_feed_text_requires_extension():
    sp = StreamParser(mode="per_call")
    sp.feed_text("abc")
    with pytest.raises(ValueError):
        sp.feed_text("xbcd")


def test_repair_mode_recovers_a_closer_slip_and_says_so():
    ex = extract("pre " + SLIP + " post " + EDIT, TOOLS, repair=True)
    assert len(ex.calls) == 1 and "repaired" in ex.calls[0].warnings
    assert ex.calls[0].arguments == {"filepath": "a.py", "new_string": "x = 1", "old_string": "x = 0"}
    assert ex.repairs and ex.errors[0].code == "EXPECTED_SEP"
    assert ex.content == "pre  post " + EDIT          # nothing after the repaired call is delivered as a call
    assert not extract("pre " + SLIP, TOOLS).calls     # default: no repair


def test_repair_needs_tools_and_per_call():
    with pytest.raises(ValueError):
        StreamParser(mode="per_call", repair=True)
    with pytest.raises(ValueError):
        StreamParser(mode="completion", tools=TOOLS, repair=True)


def test_repair_mode_never_changes_valid_completions_and_streams_identically():
    import random
    from _util import cuts
    r = random.Random(41)
    vals = ["x = 1", 'a "b" `c`', "", "it's", "`,", '",new_string:', "\n  y\n"]
    for _ in range(300):
        args = {k: r.choice(vals) for k in ("filepath", "old_string", "new_string")}
        good = render_call("edit_file", args)
        bad = good.replace(D + ",", r.choice(["`,", '",', "',", "```,"]), 1) if r.random() < 0.6 else good
        text = r.choice(["", "ok "]) + bad + r.choice(["", " tail", good])
        a, b = extract(text, TOOLS, repair=True), extract(text, TOOLS)
        if not b.errors:
            assert [c.span for c in a.calls] == [c.span for c in b.calls] and not a.repairs
        sp = StreamParser(mode="per_call", tools=TOOLS, repair=True)
        evs = []
        for c in cuts(text, r):
            evs += sp.feed(c)
        evs += sp.finish()
        got = [e[2] for e in evs if e[0] == "call_end"]
        assert [(c.span, c.arguments) for c in got] == [(c.span, c.arguments) for c in a.calls], text
        assert ("".join(e[1] for e in evs if e[0] == "content") or None) == a.content
        assert all(e[0] != "call_start" or any(x[0] == "call_end" and x[1] == e[1] for x in evs) for e in evs)


@pytest.mark.parametrize("family", ["many_calls", "many_args", "content_segments"])
def test_linear_time_families(family):
    def text(n):
        if family == "many_calls":
            return "".join(TOOL_CALL_OPEN + f"call:f{{a:{i}}}" + TOOL_CALL_CLOSE for i in range(n))
        if family == "many_args":
            return render_call("f", {f"k{i}": i for i in range(n)})
        return "".join(f"t{i} " + TOOL_CALL_OPEN + f"call:f{{a:{i}}}" + TOOL_CALL_CLOSE for i in range(n))

    def t(n):
        s = text(n)
        best = 1e9
        for _ in range(3):
            t0 = time.perf_counter()
            parse_completion(s)
            best = min(best, time.perf_counter() - t0)
        return best
    a, b = t(1000), t(8000)
    assert b < 20 * max(a, 1e-3), (family, a, b)      # 8x input: linear ~8x, quadratic ~64x


def test_repair_mode_kwarg_drift_on_non_string_argument():
    import json as _json
    import os as _os
    tools = _json.load(open(_os.path.join(_os.path.dirname(__file__), "..", "src", "slipguard", "data", "tools_edit.json")))
    text = TOOL_CALL_OPEN + "call:read_file{filepath:" + D + "a.py" + D + ",start_line=668}" + TOOL_CALL_CLOSE
    assert not extract(text, tools).calls                     # strict: loud (vLLM 0.19.1 silently dropped start_line)
    ex = extract(text, tools, repair=True)
    assert ex.calls[0].arguments == {"filepath": "a.py", "start_line": 668} and "repair_rule:kwarg" in ex.calls[0].warnings
    s = TOOL_CALL_OPEN + 'call:read_file{filepath="a.py"}' + TOOL_CALL_CLOSE   # string-typed: left loud
    assert not extract(s, tools, repair=True).calls
