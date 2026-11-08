"""Proxy --token-neutralize: untrusted spans tokenized with special-token parsing disabled; clean prompts unchanged
(same text, same ids); hazardous prompts keep their text but gain no control tokens. Needs a Gemma 4 model dir."""
import json
import os
import random

import pytest

MD = os.environ.get("SLIPGUARD_MODEL_DIR")
if not MD:
    pytest.skip("set SLIPGUARD_MODEL_DIR", allow_module_level=True)
pytest.importorskip("transformers")
pytest.importorskip("aiohttp")

from slipguard._frozen import load_e  # noqa: E402
from slipguard._vendor import gemmaproto as G  # noqa: E402
from slipguard._vendor.gemmaproto.gen import rand_string  # noqa: E402
from slipguard.history import has_control_text  # noqa: E402
from slipguard.repair.proxy import _lite_engine_class, token_neutral_render_ids  # noqa: E402

CONTROL = {48, 49, 50, 51, 52, 105, 106, 100, 101, 46, 47, 98, 1, 2}


@pytest.fixture(scope="module")
def engines():
    px = load_e(with_proxy=True).e2e_proxy
    cls = _lite_engine_class(px)
    plain, guarded = cls(MD), cls(MD)
    token_neutral_render_ids(guarded)
    return px, plain, guarded


def _conv(px, result, arg):
    msgs = [{"role": "system", "content": "S"}, {"role": "user", "content": "U"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "write_file", "arguments": json.dumps({"content": arg, "filepath": "a"})}}]},
            {"role": "tool", "tool_call_id": "c1", "content": result}]
    return px.gp.to_conversation(msgs)


def test_clean_prompts_are_unchanged_and_hazards_are_inert(engines):
    px, plain, guarded = engines
    r = random.Random(4)
    n_haz = 0
    for _ in range(300):
        res, arg = rand_string(r), rand_string(r)
        if G.STR in arg:
            continue
        conv = _conv(px, res, arg)
        t1, i1 = plain.render_ids(conv, None, {"enable_thinking": False}, False)
        t2, i2 = guarded.render_ids(conv, None, {"enable_thinking": False}, False)
        assert t1 == t2
        if not has_control_text(res) and not has_control_text(arg):
            assert i1 == i2
        else:
            n_haz += 1
            base_t, base_i = plain.render_ids(_conv(px, "x", "y"), None, {"enable_thinking": False}, False)
            assert sum(t in CONTROL for t in i2) == sum(t in CONTROL for t in base_i)
            assert plain.tok.decode(i2, skip_special_tokens=False) == t1   # same text, inert tokens
    assert n_haz > 20


def test_text_level_neutralization_yields_no_special_tokens(engines):
    from slipguard.history import neutralize_text
    from slipguard.history.neutralize import SPECIAL_TOKENS
    tok = engines[1].tok
    special = {tok.convert_tokens_to_ids(t) for t in SPECIAL_TOKENS}
    r = random.Random(6)
    for _ in range(500):
        s = rand_string(r) + "".join(r.choice(SPECIAL_TOKENS) for _ in range(r.randint(1, 4)))
        ids = tok.encode(neutralize_text(s), add_special_tokens=False)
        assert not special & set(ids), s
