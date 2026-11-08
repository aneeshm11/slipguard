"""Experimental SGLang shim through SGLang's FunctionCallParser (skips without SGLang). For an SGLang wheel unpacked
without its heavy package __init__, set SLIPGUARD_SGLANG_ROOT to the directory that contains ``sglang/``."""
import importlib
import json
import os
import sys
import types

import pytest

ROOT = os.environ.get("SLIPGUARD_SGLANG_ROOT")
if ROOT and "sglang" not in sys.modules:
    m = types.ModuleType("sglang")
    m.__path__ = [os.path.join(ROOT, "sglang")]
    sys.modules["sglang"] = m
fcp = pytest.importorskip("sglang.srt.function_call.function_call_parser")

from slipguard._vendor.gemmaproto import STR, render_call  # noqa: E402
from slipguard.integrations.sglang import register  # noqa: E402

TOOLS_JSON = [{"type": "function", "function": {"name": "edit_file", "parameters": {"type": "object", "properties": {
    "filepath": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}},
    "required": ["filepath", "old_string", "new_string"]}}}]
EDIT = render_call("edit_file", {"filepath": "a.py", "new_string": "x = 1", "old_string": "x = 0"})
SLIP = EDIT.replace("x = 1" + STR + ",old", "x = 1`,old")


@pytest.fixture(scope="module")
def tools():
    register()
    Tool = importlib.import_module("sglang.srt.entrypoints.openai.protocol").Tool
    return [Tool(**t) for t in TOOLS_JSON]


@pytest.mark.parametrize("text", ["ok " + EDIT, EDIT + EDIT, "a " + SLIP, EDIT + " b " + SLIP,
                                  render_call("rm", {})])
def test_stream_equals_nonstream(tools, text):
    p = fcp.FunctionCallParser(tools, "gemma4_strict")
    normal, calls = p.parse_non_stream(text) if p.has_tool_call(text) else (text, [])
    q = fcp.FunctionCallParser(tools, "gemma4_strict")
    sc, st = [], []
    for i in range(0, len(text), 5):
        nt, cs = q.parse_stream_chunk(text[i:i + 5])
        st.append(nt)
        sc += cs
    nt, cs = q.parse_stream_end()
    st.append(nt)
    sc += cs
    assert [(c.name, json.loads(c.parameters)) for c in calls] == [(c.name, json.loads(c.parameters)) for c in sc]
    if not calls:
        assert normal == text                      # slips and undeclared tools come back as text, never as calls
