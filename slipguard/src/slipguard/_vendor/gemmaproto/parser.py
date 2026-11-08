"""Reference parser for the Gemma-4 tool-call notation (spec: spec/GEMMA4_PROTOCOL_SPEC.md).

Design goals
------------
* **Exact**: accepts exactly the L1 ("well-formed") language of the spec; on canonical input (what the chat
  template renders) ``render_call(name, args) == text``.
* **Fail-loud**: never drops, absorbs or invents content. Every character of a tool-call region must be
  consumed by the grammar, otherwise ``ParseError`` is raised with a machine-readable ``code``, the
  character ``pos``ition and a message. There is no best-effort mode here (repair is a separate concern).
* **Prefix-safe streaming**: ``IncrementalCallParser`` re-uses the same grammar; values are reported only
  once complete, are never revised, and an error reported on a prefix is reported on every extension.

The grammar is LL(1) over characters, except that a string runs to the FIRST following ``<|"|>``
(there is no escape mechanism); this makes the language unambiguous.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from .serializer import render_call, JULY, JUNE
from .tokens import (STR, TOOL_CALL_OPEN, TOOL_CALL_CLOSE, TOOL_RESP_OPEN, TURN_CLOSE, EOS, CHANNEL_OPEN,
                     CHANNEL_CLOSE, PROTOCOL_TOKENS)

WS = " \t\n\r"
_NUM_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_INT_RE = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_SPECIAL_FLOATS = {"inf": math.inf, "-inf": -math.inf, "nan": math.nan}
_NAME_FORBIDDEN = set(WS) | set("{}()[],:<>\"'`")
_KEY_FORBIDDEN = set(WS) | set(":,{}[]") | set("\"'`")  # quotes: JSON-style keys must fail loudly
_ALL_TOKENS = tuple(PROTOCOL_TOKENS) + (STR,)
MAX_DEPTH = 256  # nesting bound (objects + arrays); the template has none, a parser must have one

ERROR_CODES = {
    "NO_CALL_OPEN": "text does not start with <|tool_call>",
    "NO_CALL_PREFIX": "<|tool_call> not followed by 'call:'",
    "BAD_NAME": "empty/invalid function name, or name not followed by '{'",
    "PAREN_OPENER": "'call:NAME(' instead of 'call:NAME{' (observed drift)",
    "BAD_KEY": "a key is empty or starts with a forbidden character",
    "EXPECTED_COLON": "key not followed by ':'",
    "EXPECTED_VALUE": "nothing that can start a value",
    "INVALID_LITERAL": "bare token that is not true/false/null/number/inf/nan",
    "JSON_STYLE_STRING": "value starts with a quote/backtick: a string not delimited by <|\"|>",
    "STRAY_TOKEN": "a protocol control token outside a string where a key/value was expected, or in content",
    "DUPLICATE_KEY": "a key repeated in one object",
    "EXPECTED_SEP": "after a value: neither ',' nor the closing bracket (where every look-alike-closer slip lands)",
    "EXPECTED_CALL_CLOSE": "the argument object is not followed by <tool_call|>",
    "TRAILING_TEXT": "text after the construct",
    "UNTERMINATED": "input ended inside a string / object / array / call / thought",
    "MISSING_CALL_OPEN": "bare 'call:NAME{' in content without <|tool_call>",
    "TOO_DEEP": f"nesting deeper than MAX_DEPTH={MAX_DEPTH}",
}


class ParseError(ValueError):
    """Raised for any input outside the L1 language. ``code`` is one of ERROR_CODES."""

    def __init__(self, code: str, pos: int, message: str, text: str = "", **extra: Any):
        self.code, self.pos, self.message, self.extra = code, pos, message, extra
        snippet = (text[max(0, pos - 30):pos] + "\u2038" + text[pos:pos + 30]) if text else ""
        super().__init__(f"[{code}] at {pos}: {message}" + (f" | ...{snippet!r}..." if snippet else ""))

    def to_dict(self) -> dict:
        return {"code": self.code, "pos": self.pos, "message": self.message, **self.extra}


class _Incomplete(Exception):
    """Internal: input ended inside a construct (a longer input could still be well-formed)."""

    def __init__(self, what: str, pos: int):
        super().__init__(what)
        self.what, self.pos = what, pos


@dataclass
class ToolCall:
    name: str
    arguments: dict
    span: tuple[int, int]
    key_order: list[str] = field(default_factory=list)
    canonical: bool = False  # True iff text[span] == render_call(name, arguments)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "arguments": self.arguments, "span": list(self.span),
                "key_order": self.key_order, "canonical": self.canonical, "warnings": self.warnings}


class _P:
    """Recursive-descent parser over ``s``."""

    def __init__(self, s: str, allow_ws: bool = True, allow_quoted_keys: bool = True, template: str = JULY):
        self.s, self.n = s, len(s)
        self.allow_ws, self.allow_quoted_keys = allow_ws, allow_quoted_keys
        self.template = template  # JUNE: the June-5 template prints None as the bare literal `None`
        self.warnings: list[str] = []
        self.depth = 0
        self.cur_name: str | None = None          # set once a call's name is confirmed
        self.top_pairs: list[tuple[str, Any]] = []  # committed top-level pairs of the current call
        self.literal_eof_ok = False                 # standalone values: a bare literal may end at EOF

    def err(self, code: str, pos: int, msg: str, **extra: Any) -> ParseError:
        return ParseError(code, pos, msg, self.s, **extra)

    def ws(self, i: int) -> int:
        if self.allow_ws:
            while i < self.n and self.s[i] in WS:
                i += 1
        return i

    def need(self, i: int, what: str) -> None:
        if i >= self.n:
            raise _Incomplete(what, i)

    def _partial_delim_at_end(self, i: int) -> bool:
        return self.n - i < len(STR) and STR.startswith(self.s[i:])

    def _maybe_token_prefix(self, i: int) -> bool:
        """The buffer ends with a proper prefix of a control token starting at i (streaming: wait)."""
        rest = self.s[i:]
        return any(len(rest) < len(t) and t.startswith(rest) for t in _ALL_TOKENS)

    def value(self, i: int) -> tuple[Any, int]:
        i = self.ws(i)
        self.need(i, "value")
        s = self.s
        if s.startswith(STR, i):
            j = s.find(STR, i + len(STR))
            if j < 0:
                raise _Incomplete("string", i)
            return s[i + len(STR):j], j + len(STR)
        if self._partial_delim_at_end(i):
            raise _Incomplete("string", i)
        c = s[i]
        if c == "<" and self._maybe_token_prefix(i):
            raise _Incomplete("token", i)
        if c == "{":
            return self.obj(i)
        if c == "[":
            return self.arr(i)
        for tok in PROTOCOL_TOKENS:
            if s.startswith(tok, i):
                raise self.err("STRAY_TOKEN", i, f"protocol token {tok} where a value was expected", token=tok)
        j = i
        while j < self.n and s[j] not in ",}]" and s[j] not in WS and s[j] != "<":
            j += 1
        if j >= self.n and not self.literal_eof_ok:
            raise _Incomplete("literal", i)
        tok = s[i:j]
        if tok == "":
            raise self.err("EXPECTED_VALUE", i, f"expected a value, found {s[i]!r}")
        if tok == "true":
            return True, j
        if tok == "false":
            return False, j
        if tok == "null" or (tok == "None" and self.template == JUNE):
            return None, j
        if tok in _SPECIAL_FLOATS:
            return _SPECIAL_FLOATS[tok], j
        if _NUM_RE.match(tok):
            return (int(tok) if _INT_RE.match(tok) else float(tok)), j
        if tok[:1] in "\"'`":
            raise self.err("JSON_STYLE_STRING", i, f"value starts with {tok[0]!r}: strings must be delimited by <|\"|>",
                           literal=tok[:40])
        raise self.err("INVALID_LITERAL", i, f"bare token {tok[:40]!r} is not true/false/null/number", literal=tok[:40])

    def key(self, i: int) -> tuple[str, int]:
        i = self.ws(i)
        self.need(i, "key")
        s = self.s
        if s.startswith(STR, i):
            if not self.allow_quoted_keys:
                raise self.err("BAD_KEY", i, "quoted key not allowed")
            j = s.find(STR, i + len(STR))
            if j < 0:
                raise _Incomplete("quoted key", i)
            self.warnings.append("quoted_key")
            return s[i + len(STR):j], j + len(STR)
        if self._partial_delim_at_end(i) or (s[i] == "<" and self._maybe_token_prefix(i)):
            raise _Incomplete("key", i)
        j = i
        while j < self.n:
            if s.startswith(STR, j):
                break
            if s[j] == "<" and self._maybe_token_prefix(j):
                raise _Incomplete("key", i)
            if s[j] in _KEY_FORBIDDEN:
                break
            j += 1
        if j >= self.n:
            raise _Incomplete("key", i)
        if j == i:
            raise self.err("BAD_KEY", i, f"expected a key, found {s[i]!r}")
        k = s[i:j]
        for tok in PROTOCOL_TOKENS:
            t = k.find(tok)
            if t >= 0:
                raise self.err("STRAY_TOKEN", i + t, f"protocol token {tok} inside a key", token=tok)
        return k, j

    def colon(self, i: int) -> int:
        i = self.ws(i)
        self.need(i, "':'")
        if self.s[i] != ":":
            raise self.err("EXPECTED_COLON", i, f"expected ':' after key, found {self.s[i]!r}")
        return i + 1

    def pairs(self, i: int, close: str) -> tuple[list[tuple[str, Any]], int]:
        """``pair (',' pair)*`` up to and including ``close``; ``i`` is just after the opener."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self.err("TOO_DEEP", i - 1, f"nesting deeper than {MAX_DEPTH}")
        top = self.depth == 1
        out: list[tuple[str, Any]] = []
        seen: set[str] = set()
        i = self.ws(i)
        self.need(i, repr(close))
        if self.s[i] == close:
            self.depth -= 1
            return out, i + 1
        while True:
            kpos = self.ws(i)
            k, i = self.key(i)
            i = self.colon(i)
            vpos = self.ws(i)
            v, i = self.value(i)
            if k in seen:
                raise self.err("DUPLICATE_KEY", kpos, f"duplicate key {k!r}", key=k)
            seen.add(k)
            out.append((k, v))
            i = self.ws(i)
            self.need(i, f"',' or '{close}'")
            c = self.s[i]
            if c == ",":
                if top:
                    self.top_pairs.append((k, v))
                i += 1
                continue
            if c == close:
                self.depth -= 1
                return out, i + 1
            raise self.err("EXPECTED_SEP", i, f"expected ',' or '{close}' after the value of {k!r}, found {c!r}",
                           after_key=k, value_start=vpos)

    def obj(self, i: int) -> tuple[dict, int]:
        pairs, i = self.pairs(i + 1, "}")
        return dict(pairs), i

    def arr(self, i: int) -> tuple[list, int]:
        out: list = []
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self.err("TOO_DEEP", i, f"nesting deeper than {MAX_DEPTH}")
        i = self.ws(i + 1)
        self.need(i, "']'")
        if self.s[i] == "]":
            self.depth -= 1
            return out, i + 1
        while True:
            v, i = self.value(i)
            out.append(v)
            i = self.ws(i)
            self.need(i, "',' or ']'")
            c = self.s[i]
            if c == ",":
                i += 1
                continue
            if c == "]":
                self.depth -= 1
                return out, i + 1
            raise self.err("EXPECTED_SEP", i, f"expected ',' or ']' in array, found {c!r}")

    def call(self, i: int) -> tuple[ToolCall, int]:
        """Parse one call; ``i`` points at '<|tool_call>'."""
        s = self.s
        start = i
        self.warnings, self.depth, self.cur_name, self.top_pairs = [], 0, None, []
        i += len(TOOL_CALL_OPEN)
        rest = s[i:i + 5]
        if len(rest) < 5 and "call:".startswith(rest):
            raise _Incomplete("'call:'", i)
        if rest != "call:":
            raise self.err("NO_CALL_PREFIX", i, f"expected 'call:' after <|tool_call>, found {s[i:i + 10]!r}")
        i += 5
        j = i
        while j < self.n and s[j] not in _NAME_FORBIDDEN:
            j += 1
        if j >= self.n:
            raise _Incomplete("name", i)
        name = s[i:j]
        if s[j] == "(":
            raise self.err("PAREN_OPENER", j, "function arguments opened with '(' instead of '{'", name=name)
        if s[j] != "{":
            raise self.err("BAD_NAME", j, f"expected '{{' after function name {name!r}, found {s[j]!r}", name=name)
        if not name:
            raise self.err("BAD_NAME", i, "empty function name")
        self.cur_name = name
        pairs, i = self.pairs(j + 1, "}")
        i2 = self.ws(i)
        if self.n - i2 < len(TOOL_CALL_CLOSE) and TOOL_CALL_CLOSE.startswith(s[i2:]):
            raise _Incomplete("'<tool_call|>'", i2)
        if not s.startswith(TOOL_CALL_CLOSE, i2):
            raise self.err("EXPECTED_CALL_CLOSE", i2,
                           f"expected <tool_call|> after the closing '}}', found {s[i2:i2 + 12]!r}")
        end = i2 + len(TOOL_CALL_CLOSE)
        args = dict(pairs)
        tc = ToolCall(name=name, arguments=args, span=(start, end), key_order=[k for k, _ in pairs],
                      warnings=list(self.warnings))
        try:
            tc.canonical = render_call(name, args, template=self.template) == s[start:end]
        except Exception:  # noqa: BLE001 - non-representable content
            tc.canonical = False
        return tc, end


def _odd_delims(text: str) -> bool:
    return text.count(STR) % 2 == 1


def parse_call(text: str, *, allow_ws: bool = True, template: str = JULY) -> ToolCall:
    """Parse exactly one tool call ``<|tool_call>call:NAME{...}<tool_call|>`` (nothing before/after).

    ``template=JUNE`` additionally accepts the bare literal ``None`` (how the June-5 template prints null)."""
    if not text.startswith(TOOL_CALL_OPEN):
        raise ParseError("NO_CALL_OPEN", 0, "text does not start with <|tool_call>", text)
    p = _P(text, allow_ws=allow_ws, template=template)
    try:
        tc, end = p.call(0)
    except _Incomplete as e:
        raise ParseError("UNTERMINATED", e.pos, f"input ended inside {e.what}", text, inside=e.what,
                         odd_delimiters=_odd_delims(text)) from None
    except ParseError as e:
        e.extra.setdefault("odd_delimiters", _odd_delims(text))
        raise
    if end != len(text):
        raise ParseError("TRAILING_TEXT", end, "text after <tool_call|>", text)
    return tc


@dataclass
class ParsedCompletion:
    thought: str | None
    content: list[str]
    calls: list[ToolCall]
    terminator: str | None

    def to_dict(self) -> dict:
        return {"thought": self.thought, "content": self.content, "calls": [c.to_dict() for c in self.calls],
                "terminator": self.terminator}


_BARE_CALL_RE = re.compile(r"(?:^|[^\w])call:[\w\-\.]+[{(]")


def parse_completion(text: str, *, in_thought: bool = False, allow_ws: bool = True,
                     strict_content: bool = True, template: str = JULY) -> ParsedCompletion:
    """Parse a whole model completion (decoded with skip_special_tokens=False).

    ``in_thought``: the prompt ended with ``<|channel>thought\\n`` (thinking on, after a tool response).
    ``strict_content``: content may not contain a stray <tool_call|>, <|"|>, <|channel> or a bare
    ``call:NAME{`` / ``call:NAME(`` (signatures of a lost or garbled call) -> ParseError.
    """
    i = 0
    thought = None
    if in_thought or text.startswith(CHANNEL_OPEN):
        j = text.find(CHANNEL_CLOSE)
        if j < 0:
            raise ParseError("UNTERMINATED", len(text), "thought channel never closed", text, inside="thought")
        thought = text[:j] if in_thought else text[len(CHANNEL_OPEN):j]
        if not in_thought and thought.startswith("thought\n"):
            thought = thought[len("thought\n"):]
        i = j + len(CHANNEL_CLOSE)
    p = _P(text, allow_ws=allow_ws, template=template)
    content: list[str] = []
    calls: list[ToolCall] = []
    terminator = None
    while i < len(text):
        nxt = text.find(TOOL_CALL_OPEN, i)
        seg_end = len(text) if nxt < 0 else nxt
        best = None
        for term in (TURN_CLOSE, TOOL_RESP_OPEN, EOS):
            t = text.find(term, i, seg_end)
            if t >= 0 and (best is None or t < best[0]):
                best = (t, term)
        if best is not None:
            seg_end, terminator, nxt = best[0], best[1], -1
        seg = text[i:seg_end]
        if seg:
            if strict_content:
                for bad in (TOOL_CALL_CLOSE, STR, CHANNEL_OPEN):
                    k = seg.find(bad)
                    if k >= 0:
                        raise ParseError("STRAY_TOKEN", i + k, f"{bad} outside a tool call", text, token=bad)
                m = _BARE_CALL_RE.search(seg)
                if m:
                    raise ParseError("MISSING_CALL_OPEN", i + m.start(), "bare 'call:NAME{' without <|tool_call>", text)
            content.append(seg)
        if nxt < 0:
            break
        try:
            tc, i = p.call(nxt)
        except _Incomplete as e:
            raise ParseError("UNTERMINATED", e.pos, f"input ended inside {e.what}", text, inside=e.what,
                             odd_delimiters=_odd_delims(text[nxt:])) from None
        except ParseError as e:
            e.extra.setdefault("odd_delimiters", _odd_delims(text[nxt:]))
            raise
        calls.append(tc)
    return ParsedCompletion(thought=thought, content=content, calls=calls, terminator=terminator)


def parse_value_text(text: str, *, allow_ws: bool = True) -> Any:
    """Parse one standalone value (tool responses, declarations, tests). A bare literal may end at EOF."""
    p = _P(text, allow_ws=allow_ws)
    p.literal_eof_ok = True
    try:
        v, i = p.value(0)
    except _Incomplete as e:
        raise ParseError("UNTERMINATED", e.pos, f"input ended inside {e.what}", text, inside=e.what) from None
    i = p.ws(i)
    if i != len(text):
        raise ParseError("TRAILING_TEXT", i, "text after value", text)
    return v


def parse_args_body(body: str, *, allow_ws: bool = True) -> dict:
    """Parse the text between ``call:NAME{`` and the final ``}`` (i.e. what regex-based extractors capture)."""
    p = _P("{" + body + "}", allow_ws=allow_ws)
    try:
        v, i = p.obj(0)
    except _Incomplete as e:
        raise ParseError("UNTERMINATED", max(0, e.pos - 1), f"input ended inside {e.what}", body, inside=e.what,
                         odd_delimiters=_odd_delims(body)) from None
    except ParseError as e:
        e.pos = max(0, e.pos - 1)
        e.extra.setdefault("odd_delimiters", _odd_delims(body))
        raise
    if i != len(body) + 2:
        raise ParseError("TRAILING_TEXT", i - 1, "text after the argument object", body)
    return v


# ------------------------------------------------------------------------------------------------
# Prefix-safe incremental parser (streaming)
# ------------------------------------------------------------------------------------------------
class IncrementalCallParser:
    """Feed text chunks of ONE completion; receive committed events.

    Events: ("content", text) / ("call_start", idx, name) / ("arg", idx, key, value) / ("call_end", idx, ToolCall).
    Guarantees (tests/test_properties.py):
      * an event is emitted only when it can no longer change (complete values, separator seen);
      * for every chunking, the concatenated events equal those of the one-shot parse (content merged);
      * a ParseError raised on a prefix is raised with the same code and position on the full text.
    The implementation re-parses the buffer each feed (O(n^2) worst case): it is a reference, not a server.
    """

    def __init__(self, allow_ws: bool = True):
        self.buf = ""
        self.allow_ws = allow_ws
        self.emitted: list[tuple] = []

    def feed(self, chunk: str) -> list[tuple]:
        self.buf += chunk
        return self._advance(final=False)

    def finish(self) -> list[tuple]:
        return self._advance(final=True)

    def _events_for(self, final: bool) -> list[tuple]:
        s = self.buf
        ev: list[tuple] = []
        p = _P(s, allow_ws=self.allow_ws)
        i = 0
        idx = 0
        while True:
            nxt = s.find(TOOL_CALL_OPEN, i)
            if nxt < 0:
                tail = s[i:]
                keep = 0
                if not final:
                    for k in range(1, len(TOOL_CALL_OPEN)):
                        if tail.endswith(TOOL_CALL_OPEN[:k]):
                            keep = k
                if tail[:len(tail) - keep]:
                    ev.append(("content", tail[:len(tail) - keep]))
                return ev
            if nxt > i:
                ev.append(("content", s[i:nxt]))
            try:
                tc, end = p.call(nxt)
            except _Incomplete as e:
                if final:
                    raise ParseError("UNTERMINATED", e.pos, f"input ended inside {e.what}", s, inside=e.what) from None
                if p.cur_name is not None:
                    ev.append(("call_start", idx, p.cur_name))
                    ev.extend(("arg", idx, k, v) for k, v in p.top_pairs)
                return ev
            ev.append(("call_start", idx, tc.name))
            ev.extend(("arg", idx, k, tc.arguments[k]) for k in tc.key_order)
            ev.append(("call_end", idx, tc))
            idx += 1
            i = end

    def _advance(self, final: bool) -> list[tuple]:
        evs = self._events_for(final)
        out: list[tuple] = []
        m = len(self.emitted)
        for t, e in enumerate(evs):
            if t < m:
                old = self.emitted[t]
                if _same_event(old, e):
                    continue
                if old[0] == "content" and e[0] == "content" and e[1].startswith(old[1]):
                    out.append(("content", e[1][len(old[1]):]))
                    continue
                raise AssertionError(f"prefix-safety violated: {old!r} -> {e!r}")
            out.append(e)
        self.emitted = evs
        return out


def _same_event(a: tuple, b: tuple) -> bool:
    if a[0] != b[0]:
        return False
    if a[0] == "arg":
        from .serializer import values_equal
        return a[1] == b[1] and a[2] == b[2] and values_equal(a[3], b[3])
    if a[0] == "call_end":
        return a[1] == b[1]
    return a == b


# ------------------------------------------------------------------------------------------------
# Diagnostics on (lenient-parser) outputs: absorbed-argument detection
# ------------------------------------------------------------------------------------------------
_CLOSER_ALT = r'(?P<closer>\\"\\"\\"|"""|\'\'\'|```|\\"|\\\'|"|\'|`|\u201d|\u2019|)'


def absorbed_arg_pattern(keys: list[str]) -> re.Pattern:
    """Regex for '<look-alike closer>,<key>:' inside a string value (the slip signature)."""
    alt = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    return re.compile(_CLOSER_ALT + r"(?P<sp1>\s*),(?P<sp2>\s*)(?P<key>" + alt + r")(?P<sp3>\s*):")


def find_absorbed(args: dict, declared: list[str]) -> list[dict]:
    """In each string argument, find '<closer>,<declared-but-absent key>:' signatures.

    Only keys declared for the tool AND absent from ``args`` count (keeps false positives on code that
    merely mentions a key name low).
    """
    out: list[dict] = []
    if not isinstance(args, dict):
        return out
    missing = [k for k in declared if k not in args]
    if not missing:
        return out
    pat = absorbed_arg_pattern(missing)
    for host, v in args.items():
        if not isinstance(v, str):
            continue
        for m in pat.finditer(v):
            out.append({"host_key": host, "absorbed_key": m.group("key"), "closer": m.group("closer"),
                        "offset": m.start(), "tail_after": len(v) - m.end()})
    return out
