"""P1-P3: the engine equals the executable specification (gemmaproto) on every input and every chunking."""
import random

import pytest

from _util import SCALE, cuts, mine, mutant, oracle, same, token_soup
from slipguard.parse import StreamParser, extract

N = int(4000 * SCALE)


@pytest.mark.parametrize("gen", [token_soup, mutant])
def test_oneshot_equals_oracle(gen):
    r = random.Random(11 if gen is token_soup else 12)
    bad = []
    for _ in range(N):
        t, it = gen(r), r.random() < 0.2
        o = oracle(t, it)
        if not same(o, mine(t, it)):
            bad.append(t)
    assert not bad, bad[:3]


@pytest.mark.parametrize("gen", [token_soup, mutant])
def test_streaming_any_chunking_equals_oneshot(gen):
    r = random.Random(21 if gen is token_soup else 22)
    bad = []
    for _ in range(N // 2):
        t, it = gen(r), r.random() < 0.2
        o = oracle(t, it)
        for chunks in (list(t), cuts(t, r)):
            if not same(o, mine(t, it, chunks)):
                bad.append(t)
                break
    assert not bad, bad[:3]


def _fold(text, r, in_thought):
    sp = StreamParser(mode="per_call", in_thought=in_thought, parse_thought=True)
    calls, content = [], []
    for c in cuts(text, r):
        for ev in sp.feed(c):
            calls += [ev[2]] if ev[0] == "call_end" else []
            content += [ev[1]] if ev[0] == "content" else []
    for ev in sp.finish():
        calls += [ev[2]] if ev[0] == "call_end" else []
        content += [ev[1]] if ev[0] == "content" else []
    return calls, "".join(content) or None, [(e.code, e.pos) for e in sp.errors]


@pytest.mark.parametrize("gen", [token_soup, mutant])
def test_per_call_stream_equals_nonstream_and_prefix_of_strict(gen):
    r = random.Random(31 if gen is token_soup else 32)
    for _ in range(N // 2):
        t, it = gen(r), r.random() < 0.2
        ex = extract(t, in_thought=it, parse_thought=True)
        calls, content, errs = _fold(t, r, it)
        assert [c.span for c in calls] == [c.span for c in ex.calls], t
        assert content == ex.content, t
        assert errs == [(e.code, e.pos) for e in ex.errors], t
        o = oracle(t, it)
        if o[0] == "ok":    # a strictly valid completion: per-call == whole-completion, no errors
            assert not ex.errors and [c.span for c in ex.calls] == [c.span for c in o[1].calls], t
        else:               # delivered calls all precede the first error
            assert ex.errors and all(c.span[1] <= ex.errors[0].pos for c in ex.calls), t


def test_parse_call_equals_oracle():
    from slipguard._vendor import gemmaproto as G
    from slipguard.parse import ParseError, parse_call
    from slipguard._vendor.gemmaproto.serializer import values_equal
    r = random.Random(51)
    for _ in range(N):
        t = mutant(r) if r.random() < 0.5 else token_soup(r)
        t = t[t.find(G.TOOL_CALL_OPEN):] if G.TOOL_CALL_OPEN in t and r.random() < 0.7 else t
        try:
            o = ("ok", G.parse_call(t))
        except G.ParseError as e:
            o = ("err", (e.code, e.pos))
        try:
            m = ("ok", parse_call(t))
        except ParseError as e:
            m = ("err", (e.code, e.pos))
        assert o[0] == m[0], t
        if o[0] == "err":
            assert o[1] == m[1], t
        else:
            a, b = o[1], m[1]
            assert (a.name, a.span, a.key_order, a.canonical, a.warnings) == (b.name, b.span, b.key_order, b.canonical,
                                                                               b.warnings) and values_equal(a.arguments, b.arguments), t
