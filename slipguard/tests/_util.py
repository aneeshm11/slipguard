import os
import random

from slipguard._vendor import gemmaproto as G
from slipguard._vendor.gemmaproto.serializer import values_equal
from slipguard.parse import ParseError
from slipguard.parse.engine import Engine

SCALE = float(os.environ.get("SLIPGUARD_TEST_SCALE", "1"))

# protocol fragments (token soup), incl. partial tokens; built from the token constants, no payload literals
FR = [G.STR, "{", "}", "[", "]", ",", ":", " ", "\n", G.TOOL_CALL_OPEN, "call:", "f", "edit_file", "a", "old_string",
      G.TOOL_CALL_CLOSE, G.TURN_CLOSE, G.TOOL_RESP_OPEN, G.EOS, G.CHANNEL_OPEN, G.CHANNEL_CLOSE, "thought\n",
      G.STR[:3], G.TOOL_CALL_OPEN[:6], G.TOOL_CALL_CLOSE[:-1], "call", "true", "null", "None", "1", "-2.5e3", "nan",
      "`", '"', "'", "(", "x", "<", "|", ">", G.TURN_OPEN, G.THINK, "k:", "é"]


def token_soup(r: random.Random) -> str:
    t = "".join(r.choice(FR) for _ in range(r.randint(0, 40)))
    if r.random() < 0.5:
        t = G.TOOL_CALL_OPEN + "call:f{" + t
    if r.random() < 0.2:
        t = G.CHANNEL_OPEN + "thought\n" + t
    return t


def mutant(r: random.Random) -> str:
    from slipguard._vendor.gemmaproto.gen import rand_name, rand_object
    t = G.render_call(rand_name(r), rand_object(r, n=r.randint(0, 6)))
    for _ in range(r.randint(0, 2)):
        i = r.randrange(len(t))
        t = t[:i] + r.choice(["`", '"', "", ",", "}", " ", G.STR, "\n", "]"]) + t[i + 1:]
    pre = r.choice(["", "x ", G.CHANNEL_OPEN + "thought\nok" + G.CHANNEL_CLOSE, "a" + G.TOOL_CALL_OPEN])
    return pre + t + r.choice(["", G.TURN_CLOSE, " tail", G.TOOL_RESP_OPEN])


def oracle(text, in_thought=False):
    try:
        return ("ok", G.parse_completion(text, in_thought=in_thought))
    except G.ParseError as e:
        return ("err", (e.code, e.pos))


def mine(text, in_thought=False, chunks=None):
    e = Engine(mode="completion", in_thought=in_thought)
    try:
        if chunks is None:
            e.feed_text(text)
        else:
            for c in chunks:
                e.feed(c)
        e.finish()
        return ("ok", e.result())
    except ParseError as er:
        return ("err", (er.code, er.pos))


def same(a, b):
    if a[0] != b[0]:
        return False
    if a[0] == "err":
        return a[1] == b[1]
    x, y = a[1], b[1]
    if (x.thought, x.terminator, x.content) != (y.thought, y.terminator, y.content) or len(x.calls) != len(y.calls):
        return False
    return all(p.name == q.name and values_equal(p.arguments, q.arguments) and p.span == q.span and
               p.key_order == q.key_order and p.canonical == q.canonical and p.warnings == q.warnings
               for p, q in zip(x.calls, y.calls))


def cuts(text, r):
    pts = sorted(set(r.randrange(0, len(text) + 1) for _ in range(r.randint(1, 12))))
    out, p = [], 0
    for q in pts + [len(text)]:
        out.append(text[p:q])
        p = q
    return out
