"""T-T1..T-T4: the patched template equals the official one on every hazard-free input (C's identity sets,
regenerated with C's generators and seed), adds exactly the closure, and equals official(N(messages))."""
import copy
import os
import random

import pytest

pytest.importorskip("jinja2")
from _util import SCALE  # noqa: E402
from slipguard._vendor.gemmaproto.gen import rand_name, rand_object, rand_string, rand_tool  # noqa: E402
from slipguard.history import CLOSED_THOUGHT, close_thought, neutralize  # noqa: E402
from slipguard.template import OFFICIAL_MD5, official_md5, render, text  # noqa: E402

BASE = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]
N_CALLS, N_RESP, N_DECL = int(3000 * min(SCALE, 1)), int(1500 * min(SCALE, 1)), int(1500 * min(SCALE, 1))


def both(msgs, tools=None, gen=False, think=False):
    kw = dict(add_generation_prompt=gen, enable_thinking=think)
    return render(msgs, tools, which="official", **kw), render(msgs, tools, which="guarded", **kw)


def test_official_is_the_july_template():
    assert official_md5() == OFFICIAL_MD5


def test_T1_T3_calls():
    r = random.Random(7)                 # C's seed and generator order (tests/test_template_equivalence.py, T1)
    clean = 0
    for _ in range(N_CALLS):
        name, args = rand_name(r), rand_object(r, n=r.randint(0, 6))
        msgs = BASE + [{"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": name, "arguments": copy.deepcopy(args)}}]}]
        o, g = both(msgs)
        nm, rep = neutralize(msgs)
        if not rep:
            clean += 1
            assert o == g
        assert render(nm, which="official") == g          # T-T3
    assert clean > N_CALLS // 2


def test_T1_T2_T3_responses():
    r = random.Random(8)
    for k in range(N_RESP):
        name = rand_name(r)
        if k % 2 == 0:
            msgs = BASE + [{"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": name, "arguments": {}}}]},
                {"role": "tool", "tool_call_id": "c1", "content": rand_string(r)}]
        else:
            msgs = BASE + [{"role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": name, "arguments": {}}}],
                "tool_responses": [{"name": name, "response": rand_object(r, n=r.randint(1, 4))}]}]
        nm, rep = neutralize(msgs)
        for think in (False, True):
            o, g = both(msgs, gen=True, think=think)
            if not rep:
                assert close_thought(o, think) == g                    # T-T1 + T-T2
            on = render(nm, add_generation_prompt=True, enable_thinking=think, which="official")
            assert close_thought(on, think) == g                       # T-T3 (+ closure)


def test_T1_declarations():
    r = random.Random(9)
    for _ in range(N_DECL):
        o, g = both(BASE, tools=[rand_tool(r)])
        assert o == g


@pytest.mark.parametrize("think", [False, True])
@pytest.mark.parametrize("shape", ["after_user", "after_tool_response"])
@pytest.mark.parametrize("reasoning", [False, True])
def test_T1_prompt_shapes(think, shape, reasoning):
    h = list(BASE)
    if shape == "after_tool_response":
        h += [{"role": "assistant", "content": None, "reasoning_content": "r0", "tool_calls": [
            {"id": "c0", "type": "function", "function": {"name": "f", "arguments": {"a": 1}}}]},
              {"role": "tool", "tool_call_id": "c0", "content": "ok"}]
    nxt = {"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "g", "arguments": {"b": "x"}}}]}
    if reasoning:
        nxt["reasoning_content"] = "think"
    o, g = both(h, gen=True, think=think)
    expect_closure = shape == "after_tool_response" and not think
    assert g == (o + CLOSED_THOUGHT if expect_closure else o)
    o, g = both(h + [nxt], gen=False, think=think)
    assert o == g


def test_T4_proxy_canonical_template_accepts_the_patched_template():
    from slipguard._frozen import load_e
    gp = load_e().gemma_protocol
    assert gp.canonical_template(text("guarded"))


def test_renderer_matches_transformers_if_available():
    tr = pytest.importorskip("transformers")
    md = os.environ.get("SLIPGUARD_MODEL_DIR")
    if not md:
        pytest.skip("set SLIPGUARD_MODEL_DIR to a Gemma 4 model dir")
    tok = tr.AutoTokenizer.from_pretrained(md)
    r = random.Random(5)
    for _ in range(200):
        msgs = BASE + [{"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": rand_name(r), "arguments": rand_object(r, n=3)}}]},
            {"role": "tool", "tool_call_id": "c1", "content": rand_string(r)}]
        for which in ("official", "guarded"):
            want = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False,
                                           chat_template=text(which))
            assert render(msgs, which=which) == want


def test_closure_only_template_differs_from_official_only_by_the_closure():
    r = random.Random(10)
    for k in range(300):
        name = rand_name(r)
        msgs = BASE + [{"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": name, "arguments": rand_object(r, n=3)}}]},
            {"role": "tool", "tool_call_id": "c1", "content": rand_string(r)}]
        for think in (False, True):
            o = render(msgs, add_generation_prompt=True, enable_thinking=think, which="official")
            c = render(msgs, add_generation_prompt=True, enable_thinking=think, which="closure")
            assert c == close_thought(o, think)
