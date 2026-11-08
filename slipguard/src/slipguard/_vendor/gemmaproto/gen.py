"""Seeded random generators for property tests and the grammar-based fuzz corpus.

``rand_value`` draws from the *representable* domain of the spec (strings without <|"|>, bare-representable keys)
with a heavy bias toward the edge cases that real parsers get wrong.
"""
from __future__ import annotations

import math
import random
import string
from typing import Any

from .tokens import (TOOL_CALL_OPEN, TOOL_CALL_CLOSE, TURN_OPEN, TURN_CLOSE, CHANNEL_OPEN, CHANNEL_CLOSE,
                     TOOL_RESP_OPEN, TOOL_RESP_CLOSE)

TRICKY_FRAGMENTS = [
    "}", "{", "]", "[", ",", ":", "}<tool_call|>", "},k:", TOOL_CALL_CLOSE,
    "f{a:1}", TURN_CLOSE, "user\n", CHANNEL_OPEN, CHANNEL_CLOSE, TOOL_RESP_OPEN,
    TOOL_RESP_CLOSE, '<|"', '|>', '"|>', "<|'|>", "<|”|>", '"', '\\"', "'", "`", "```", '"""', "'''",
    "`,old_string:", '",new_string:', ",filepath:", "\\n", "\n", "\r\n", "\t", "\\", "\\\\", "${x}", "%s", "{0}",
    "null", "true", "1e+20", "  ", "", "<", ">", "|", "call:f{", "call:f(", "]]>", "<!--", "-->",
    "é", "中文", "\U0001F600", "​", "﻿", "‮", "é", "\u0000", "\x7f",
]
CODE_SNIPPETS = [
    'def f(x):\n    return {"a": x, \'b\': [1, 2]}\n',
    'print(f"value: {x!r}")',
    "s = 'it''s'  # comment with `backticks`",
    'raise ValueError("bad input: %s" % (value,))',
    'x = """triple\n"quoted" text"""',
    "if a[0] == ']': pass",
    "const t = `template ${a}`;",
    "json.dumps({\"k\": \"v\\n\"})",
    "re.compile(r'\\s+,\\s*')",
    "```python\nprint('hi')\n```",
    "    return self._cache.get(key, default)",
    "SELECT * FROM t WHERE name = 'O''Brien';",
]
KEY_CHARS = string.ascii_letters + string.digits + "_"


def rand_string(r: random.Random, payloads: list[str] | None = None, max_len: int = 60) -> str:
    u = r.random()
    if u < 0.10:
        return ""
    if u < 0.30:
        return "".join(r.choice(string.printable) for _ in range(r.randint(1, max_len)))
    if u < 0.55:
        return "".join(r.choice(TRICKY_FRAGMENTS + [r.choice(string.ascii_letters)]) for _ in range(r.randint(1, 8)))
    if u < 0.75:
        return r.choice(CODE_SNIPPETS)
    if u < 0.90 and payloads:
        return r.choice(payloads)
    return "".join(chr(r.choice([r.randint(0x20, 0x7e), r.randint(0xa0, 0x2fff), r.randint(0x4e00, 0x9fff),
                                  r.randint(0x1f300, 0x1faff)])) for _ in range(r.randint(1, 20)))


def rand_key(r: random.Random) -> str:
    u = r.random()
    if u < 0.6:
        k = r.choice(string.ascii_letters + "_") + "".join(r.choice(KEY_CHARS) for _ in range(r.randint(0, 12)))
    elif u < 0.8:
        k = r.choice(["filepath", "old_string", "new_string", "allow_multiple", "content", "command", "start_line",
                      "end_line", "query", "path", "a", "A", "b", "B", "Z", "z", "_", "x1", "X1"])
    elif u < 0.9:
        k = r.choice(["kebab-case", "dotted.key", "$ref", "@type", "a/b", "q?", "x+y", "été", "名前", "a<b"])
    else:
        k = "".join(r.choice(KEY_CHARS) for _ in range(r.randint(1, 40)))
    return k


def rand_number(r: random.Random) -> int | float:
    u = r.random()
    if u < 0.35:
        return r.randint(-1000, 1000)
    if u < 0.45:
        return r.choice([0, -1, 2 ** 31, 2 ** 53 + 1, 2 ** 63, -(2 ** 64) - 7, 10 ** 30])
    if u < 0.75:
        return round(r.uniform(-1e3, 1e3), r.randint(0, 6))
    return r.choice([0.0, -0.0, 0.1, 1.0, 1e-05, 1e+20, 1.5e300, 5e-324, 123456789.0, 1e16, math.inf, -math.inf,
                     math.nan, 2.5, -3.75e-7])


def rand_value(r: random.Random, depth: int = 0, payloads: list[str] | None = None, max_depth: int = 4) -> Any:
    u = r.random()
    if depth >= max_depth:
        u = u * 0.7
    if u < 0.40:
        return rand_string(r, payloads)
    if u < 0.52:
        return rand_number(r)
    if u < 0.58:
        return r.choice([True, False])
    if u < 0.62:
        return None
    if u < 0.81:
        return [rand_value(r, depth + 1, payloads, max_depth) for _ in range(r.choice([0, 1, 2, 3, 5]))]
    return rand_object(r, depth + 1, payloads, max_depth)


def rand_object(r: random.Random, depth: int = 0, payloads: list[str] | None = None, max_depth: int = 4,
                n: int | None = None) -> dict:
    d: dict = {}
    for _ in range(r.choice([0, 1, 2, 3, 4, 6]) if n is None else n):
        k = rand_key(r)
        if k not in d:
            d[k] = rand_value(r, depth, payloads, max_depth)
    return d


def rand_name(r: random.Random) -> str:
    return r.choice(["edit_file", "read_file", "write_file", "run_command", "get_status", "submit_patch", "f",
                     "get-weather", "module.func", "search_v2", "Tool9"])


def rand_schema(r: random.Random, depth: int = 0) -> dict:
    """Random JSON-schema fragment of the kind tool frameworks emit (for declaration rendering tests)."""
    t = r.choice(["string", "integer", "number", "boolean", "array", "object", "string", "string"])
    s: dict = {"type": t}
    if r.random() < 0.5:
        s["description"] = rand_string(r, max_len=30).replace('<|"|>', "")
    if t == "string" and r.random() < 0.3:
        s["enum"] = [rand_key(r) for _ in range(r.randint(1, 4))]
    if t == "array" and depth < 3:
        s["items"] = rand_schema(r, depth + 1)
    if t == "object" and depth < 3 and r.random() < 0.8:
        props = {rand_key(r): rand_schema(r, depth + 1) for _ in range(r.randint(0, 4))}
        s["properties"] = props
        if props and r.random() < 0.6:
            s["required"] = r.sample(list(props), r.randint(1, len(props)))
    if r.random() < 0.15:
        s["nullable"] = True
    if r.random() < 0.1:
        s["default"] = rand_value(r, 3)
    return s


def rand_tool(r: random.Random) -> dict:
    props = {rand_key(r): rand_schema(r, 1) for _ in range(r.randint(0, 6))}
    params: dict = {"type": "object", "properties": props}
    if props and r.random() < 0.7:
        params["required"] = r.sample(list(props), r.randint(1, len(props)))
    return {"type": "function", "function": {"name": rand_name(r), "description": rand_string(r, max_len=40).replace('<|"|>', ""),
                                             "parameters": params}}
