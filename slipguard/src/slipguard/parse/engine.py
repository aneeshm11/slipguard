"""Resumable, linear-time parser engine for the Gemma 4 tool-call notation.

One engine serves every API of :mod:`slipguard.parse`:

* one-shot (``feed(text)`` + ``finish()``) == ``gemmaproto.parse_completion`` (same result, or the same
  ``ParseError(code, pos)``; checked differentially, gemmaproto is the oracle);
* streaming (any chunking): events are never revised; an error raised on a prefix is raised with the same code and
  position on every extension (prefix safety);
* per-call runtime mode (``mode="per_call"``, used by the server plugins): calls are delivered up to the first
  protocol error; everything else is returned verbatim as content plus explicit errors.

Linear time: the engine keeps one buffer and a cursor per construct. String bodies and content are scanned with
``str.find``; keys, names, literals and whitespace with compiled character-class regexes; every character is examined
O(1) times whatever the chunking. There is no recursion: nesting uses an explicit stack bounded by MAX_DEPTH (256),
so deep input fails with ``TOO_DEEP`` and never with ``RecursionError``.

Grammar, error codes, messages and positions follow the executable specification (gemmaproto 0.1.0, workstream C).
The engine never consults the end of the buffer to *decide* anything: wherever the specification's one-shot parser
would report "incomplete", the engine suspends and resumes when more text arrives (and reports UNTERMINATED on
``finish``).
"""
from __future__ import annotations

import math
import re
from typing import Any

from .._vendor.gemmaproto.parser import ParseError, ToolCall, ParsedCompletion, MAX_DEPTH, _BARE_CALL_RE
from .._vendor.gemmaproto.serializer import render_call, JULY, JUNE
from .._vendor.gemmaproto.tokens import (STR, TOOL_CALL_OPEN, TOOL_CALL_CLOSE, TOOL_RESP_OPEN, TURN_CLOSE, EOS,
                                         CHANNEL_OPEN, CHANNEL_CLOSE, PROTOCOL_TOKENS)

__all__ = ["Engine", "ParseError", "ToolCall", "ParsedCompletion", "MAX_DEPTH"]

_ALL_TOKENS = tuple(PROTOCOL_TOKENS) + (STR,)
_MAXTOK = max(len(t) for t in _ALL_TOKENS)
_LSTR = len(STR)
_LOPEN = len(TOOL_CALL_OPEN)
_LCLOSE = len(TOOL_CALL_CLOSE)
_WS_RE = re.compile(r"[ \t\n\r]*")
_KEY_RUN = re.compile(r"[^ \t\n\r:,{}\[\]\"'`<]*")          # key chars except '<' (checked by hand)
_LIT_RUN = re.compile(r"[^,}\] \t\n\r<]*")                   # literal chars
_NAME_RUN = re.compile(r"[^ \t\n\r{}()\[\],:<>\"'`]*")       # function-name chars
_NUM_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_INT_RE = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_SPECIAL_FLOATS = {"inf": math.inf, "-inf": -math.inf, "nan": math.nan}
_KEY_FORBIDDEN = set(" \t\n\r") | set(":,{}[]") | set("\"'`")
_MARKERS = (TOOL_CALL_OPEN, TURN_CLOSE, TOOL_RESP_OPEN, EOS)   # end a content segment
_TERMINATORS = (TURN_CLOSE, TOOL_RESP_OPEN, EOS)
_MAXMARK = max(len(m) for m in _MARKERS)
_THOUGHT_PREFIX = "thought\n"


class _Suspend(Exception):
    """Internal: the decision needs text beyond the buffer (one-shot: UNTERMINATED at ``pos``)."""

    def __init__(self, what: str, pos: int):
        self.what, self.pos = what, pos


def _held_suffix(s: str, start: int, tokens: tuple[str, ...]) -> int:
    """Smallest index k >= start such that s[k:] may be the beginning of one of ``tokens`` (k == len(s) if none)."""
    n = len(s)
    lo = max(start, n - max(len(t) for t in tokens) + 1)
    for k in range(lo, n):
        rest = s[k:]
        if any(len(rest) < len(t) and t.startswith(rest) for t in tokens):
            return k
    return n


class Engine:
    """Incremental parser over ONE completion. See module docstring.

    Parameters
    ----------
    mode            "completion" (whole completion strict, raises ParseError) or "per_call" (never raises; calls up to
                    the first protocol error, the rest verbatim as content, errors listed).
    in_thought      the prompt ended inside an open thought channel (JULY template, thinking on, after a tool result).
    parse_thought   parse a leading ``<|channel>thought`` block (False: the caller already split the thought off).
    strict_content  content may not contain a stray <tool_call|>, <|"|>, <|channel> or a bare ``call:NAME{``.
    template        JULY (default) or JUNE (JUNE additionally accepts the bare literal ``None`` for null).
    """

    def __init__(self, *, mode: str = "completion", in_thought: bool = False, parse_thought: bool = True,
                 allow_ws: bool = True, strict_content: bool = True, template: str = JULY):
        if mode not in ("completion", "per_call"):
            raise ValueError(f"unknown mode {mode!r}")
        self.mode, self.in_thought, self.allow_ws = mode, in_thought, allow_ws
        self.strict_content, self.template = strict_content, template
        self.s = ""
        self.final = False
        self.error: ParseError | None = None       # completion mode: the raised error (re-raised on later calls)
        self.errors: list[ParseError] = []          # per_call mode: every protocol error (first one stops delivery)
        self.thought: str | None = None
        self.content: list[str] = []
        self.calls: list[ToolCall] = []
        self.terminator: str | None = None
        self._ev: list[tuple] = []
        # top-level state
        self.st = ("THOUGHT0" if (parse_thought or in_thought) else "CONTENT")
        self.pos = 0
        self.seg = 0                 # start of the current content segment
        self.cscan = 0               # content: no marker starts before this index
        self.cemit = 0               # content: emitted up to here
        self.tstart = 0              # thought body start
        self.temit = 0               # thought: emitted up to here
        self.tscan = 0
        self.dead = False            # per_call: after the first error everything is content
        self.single = False          # parse_call: stop after the first call
        self.call_filter = None      # optional ToolCall -> ParseError | None (schema checks), applied at call end
        self.repair_fn = None        # per_call, opt-in: (region_text, start) -> ToolCall | None (text-only repair)
        self.repairs: list[dict] = []
        self.rscan = 0
        self._reset_call()

    # ------------------------------------------------------------------------------------------- public driver
    def feed(self, chunk: str) -> list[tuple]:
        """Append text; return the newly committed events."""
        if chunk:
            s = self.s
            self.s = ""
            s += chunk          # local in-place append (amortised O(len(chunk)) in CPython)
            self.s = s
        return self._run()

    def feed_text(self, text: str) -> list[tuple]:
        """Give the WHOLE text so far (it must extend the previous one): no copying (server plugins)."""
        k = len(self.s)
        if len(text) < k or text[max(0, k - 64):k] != self.s[max(0, k - 64):]:
            raise ValueError("feed_text: text must extend the previous text")
        self.s = text
        return self._run()

    def finish(self) -> list[tuple]:
        self.final = True
        return self._run()

    def result(self) -> ParsedCompletion:
        return ParsedCompletion(thought=self.thought, content=list(self.content), calls=list(self.calls),
                                terminator=self.terminator)

    # ------------------------------------------------------------------------------------------- helpers
    def _reset_call(self) -> None:
        self.cstart = -1             # index of '<|tool_call>' of the call being parsed
        self.cname: str | None = None
        self.stack: list[list] = []  # frames: ['obj', pairs, seen, key, kpos, vpos, top] / ['arr', items]
        self.cst = None              # call sub-state
        self.cpos = 0
        self.j = 0                   # scan cursor inside the current token/string
        self.tok_start = 0
        self.warnings: list[str] = []
        self.argn = 0                # top-level args already emitted
        # call_start / arg events of the call being parsed: emitted at once in completion mode (prefix-safe, as the
        # specification's incremental parser does); held until call_end in per_call mode (a call is atomic there)
        self._cev: list[tuple] = []

    def _err(self, code: str, pos: int, msg: str, **extra: Any) -> ParseError:
        return ParseError(code, pos, msg, self.s, **extra)

    def _ws(self, i: int) -> int:
        return _WS_RE.match(self.s, i).end() if self.allow_ws else i

    def _need(self, i: int, what: str) -> None:
        if i >= len(self.s):
            raise _Suspend(what, i)

    def _partial_delim_at_end(self, i: int) -> bool:
        s = self.s
        return len(s) - i < _LSTR and STR.startswith(s[i:])

    def _maybe_token_prefix(self, i: int) -> bool:
        s = self.s
        if len(s) - i >= _MAXTOK:
            return False
        rest = s[i:]
        return any(len(rest) < len(t) and t.startswith(rest) for t in _ALL_TOKENS)

    # ------------------------------------------------------------------------------------------- run loop
    def _run(self) -> list[tuple]:
        if self.error is not None:
            raise self.error
        while self.st != "DONE":
            try:
                st = self.st
                if st == "CONTENT":
                    self._content()
                elif st == "CALL":
                    self._call()
                elif st == "THOUGHT":
                    self._thought()
                elif st == "THOUGHT0":
                    self._thought0()
                elif st == "REPAIR":
                    self._repair()
                else:
                    self._dead()
            except _Suspend as e:
                if not self.final:
                    break
                self._fail(self._unterminated_error(e))
            except ParseError as e:
                if self.st == "CALL":
                    e.extra.setdefault("odd_delimiters", self.s[self.cstart:].count(STR) % 2 == 1)
                self._fail(e)
        if self.mode == "completion" and self._cev:
            self._ev.extend(self._cev)
            self._cev = []
        ev, self._ev = self._ev, []
        return ev

    def _fail(self, e: ParseError) -> None:
        if self.mode == "completion":
            self.error = e
            self.st = "DONE"
            self._ev = []
            raise e
        # per_call: remember the error; from here on everything is content and no call is delivered
        self.errors.append(e)
        self.dead = True
        n = len(self.s)
        if self.st == "CALL" and self.repair_fn is not None:
            # opt-in text-only repair: wait for the end of the malformed call's region, then try once
            cstart = self.cstart
            self._reset_call()
            self.cstart, self.rscan, self.st = cstart, cstart + _LOPEN, "REPAIR"
            self._failed_error = e
            return
        if self.st == "CALL":
            self.seg = self.cemit = self.cscan = self.cstart
            self._reset_call()
        elif self.st in ("THOUGHT", "THOUGHT0"):
            self.thought = self.s[self.tstart:] if self.st == "THOUGHT" else None
            self.seg = self.cemit = self.cscan = n
        self.st = "DEAD"

    def _unterminated_error(self, e: _Suspend) -> ParseError:
        if self.st in ("THOUGHT", "THOUGHT0"):
            return ParseError("UNTERMINATED", len(self.s), "thought channel never closed", self.s, inside="thought")
        return ParseError("UNTERMINATED", e.pos, f"input ended inside {e.what}", self.s, inside=e.what,
                          odd_delimiters=self.s[self.cstart:].count(STR) % 2 == 1)

    # ------------------------------------------------------------------------------------------- thought
    def _thought0(self) -> None:
        s = self.s
        if self.in_thought:
            self.tstart = self.temit = self.tscan = 0
            self.st = "THOUGHT"
            return
        lo = len(CHANNEL_OPEN)
        if len(s) < lo and CHANNEL_OPEN.startswith(s) and not self.final:
            raise _Suspend("thought", 0)
        if not s.startswith(CHANNEL_OPEN):
            self.st = "CONTENT"
            return
        # the body starts after 'thought\n' when the block starts with it (no <channel|> can occur inside it)
        if len(s) < lo + len(_THOUGHT_PREFIX) and _THOUGHT_PREFIX.startswith(s[lo:]) and not self.final:
            raise _Suspend("thought", 0)
        self.tstart = lo + len(_THOUGHT_PREFIX) if s.startswith(_THOUGHT_PREFIX, lo) else lo
        self.temit = self.tstart
        self.tscan = lo
        self.st = "THOUGHT"

    def _thought(self) -> None:
        s = self.s
        j = s.find(CHANNEL_CLOSE, self.tscan)
        if j < 0:
            if not self.final:
                safe = _held_suffix(s, self.temit, (CHANNEL_CLOSE,))
                if safe > self.temit:
                    self._ev.append(("thought", s[self.temit:safe]))
                    self.temit = safe
                self.tscan = max(self.tscan, safe)
            raise _Suspend("thought", len(s))
        if j > self.temit:
            self._ev.append(("thought", s[self.temit:j]))
        self.thought = s[self.tstart:j]
        self._ev.append(("thought_end", self.thought))
        self.temit = j
        self.pos = self.seg = self.cscan = self.cemit = j + len(CHANNEL_CLOSE)
        self.st = "CONTENT"

    # ------------------------------------------------------------------------------------------- content
    def _content(self) -> None:
        s = self.s
        # the next call opener first; terminators only before it (as the specification does). Searching every
        # marker to the end of the buffer would make a completion with many calls quadratic.
        best = s.find(TOOL_CALL_OPEN, self.cscan)
        bm = TOOL_CALL_OPEN if best >= 0 else None
        lim = best if best >= 0 else len(s)
        for m in _TERMINATORS:
            k = s.find(m, self.cscan, lim)
            if k >= 0 and (best < 0 or k < best):
                best, bm = k, m
        if best < 0:
            if self.final:
                self._end_segment(len(s))
                self.st = "DONE"
                return
            safe = _held_suffix(s, max(self.seg, self.cemit), _MARKERS)
            if safe > self.cemit:
                self._ev.append(("content", s[self.cemit:safe]))
                self.cemit = safe
            self.cscan = max(self.cscan, safe)
            raise _Suspend("content", len(s))
        self._end_segment(best)
        if bm == TOOL_CALL_OPEN:
            if self.dead:            # per_call: no call after a protocol error
                self.cscan = best + _LOPEN
                self.st = "DEAD"
                return
            self.cstart = best
            self.cst = "HDR"
            self.cpos = best + _LOPEN
            self.st = "CALL"
        else:
            self.terminator = bm
            self._ev.append(("terminator", bm))
            self.st = "DONE"

    def _end_segment(self, end: int) -> None:
        s = self.s
        if end > self.cemit:
            self._ev.append(("content", s[self.cemit:end]))
            self.cemit = end
        if end > self.seg:
            seg = s[self.seg:end]
            if self.strict_content:
                err = self._content_error(seg, self.seg)
                if err is not None:
                    if self.mode == "completion":
                        raise err
                    self.errors.append(err)
                    self.dead = True
            self.content.append(seg)
        self.seg = self.cscan = end

    def _content_error(self, seg: str, base: int) -> ParseError | None:
        for bad in (TOOL_CALL_CLOSE, STR, CHANNEL_OPEN):
            k = seg.find(bad)
            if k >= 0:
                return ParseError("STRAY_TOKEN", base + k, f"{bad} outside a tool call", self.s, token=bad)
        m = _BARE_CALL_RE.search(seg)
        if m:
            return ParseError("MISSING_CALL_OPEN", base + m.start(), "bare 'call:NAME{' without <|tool_call>", self.s)
        return None

    # ------------------------------------------------------------------------------------------- repair (per_call)
    def _repair(self) -> None:
        """Region of a malformed call = up to the first <tool_call|> after its opener (the vLLM/E convention).
        If ``repair_fn`` accepts the region, the repaired call is delivered (and recorded); either way nothing after
        the region is delivered as a call."""
        s = self.s
        k = s.find(TOOL_CALL_CLOSE, self.rscan)
        if k < 0 and not self.final:
            self.rscan = max(self.rscan, len(s) - _LCLOSE + 1)
            raise _Suspend("repair", len(s))
        tc = None
        if k >= 0:
            end = k + _LCLOSE
            try:
                tc = self.repair_fn(s[self.cstart:end], self.cstart)
            except Exception:  # noqa: BLE001 - a failing repair is no repair
                tc = None
        if tc is not None:
            idx = len(self.calls)
            self._ev.append(("call_start", idx, tc.name))
            for key in tc.key_order:
                self._ev.append(("arg", idx, key, tc.arguments[key]))
            self._ev.append(("call_end", idx, tc))
            self.calls.append(tc)
            err = getattr(self, "_failed_error", None)
            rule = next((w.split(":", 1)[1] for w in tc.warnings if w.startswith("repair_rule:")), None)
            self.repairs.append({"index": idx, "name": tc.name, "span": list(tc.span), "rule": rule,
                                 "error": err.to_dict() if err is not None else None})
            self.seg = self.cemit = self.cscan = end
        else:
            self.seg = self.cemit = self.cscan = self.cstart
        self.cstart = -1
        self.st = "DEAD"

    # ------------------------------------------------------------------------------------------- dead (per_call)
    def _dead(self) -> None:
        """per_call after the first protocol error: the rest of the text is content, verbatim (nothing dropped)."""
        s = self.s
        n = len(s)
        if n > self.cemit:
            self._ev.append(("content", s[self.cemit:n]))
            self.cemit = n
        if not self.final:
            raise _Suspend("content", n)
        if n > self.seg:
            self.content.append(s[self.seg:n])
        self.seg = self.cscan = n
        self.st = "DONE"

    # ------------------------------------------------------------------------------------------- calls
    def _call(self) -> None:
        s = self.s
        while True:
            cst = self.cst
            if cst == "HDR":
                p = self.cpos
                rest = s[p:p + 5]
                if len(rest) < 5 and "call:".startswith(rest):
                    raise _Suspend("'call:'", p)
                if rest != "call:":
                    raise self._err("NO_CALL_PREFIX", p, f"expected 'call:' after <|tool_call>, found {s[p:p + 10]!r}")
                self.tok_start = self.j = p + 5
                self.cst = "NAME"
            elif cst == "NAME":
                i = self.tok_start
                j = _NAME_RUN.match(s, self.j).end()
                self.j = j
                if j >= len(s):
                    raise _Suspend("name", i)
                name = s[i:j]
                if s[j] == "(":
                    raise self._err("PAREN_OPENER", j, "function arguments opened with '(' instead of '{'", name=name)
                if s[j] != "{":
                    raise self._err("BAD_NAME", j, f"expected '{{' after function name {name!r}, found {s[j]!r}", name=name)
                if not name:
                    raise self._err("BAD_NAME", i, "empty function name")
                self.cname = name
                self._cev.append(("call_start", len(self.calls), name))
                self._open_obj(j + 1)
            elif cst == "OBJ_FIRST":
                i = self._ws(self.cpos)
                self.cpos = i
                self._need(i, repr("}"))
                if s[i] == "}":
                    self._close(i + 1)
                else:
                    self.cst = "KEY"
            elif cst == "KEY":
                i = self._ws(self.cpos)
                self.cpos = i
                self._need(i, "key")
                fr = self.stack[-1]
                fr[4] = i   # kpos
                if s.startswith(STR, i):
                    self.tok_start = i
                    self.j = i + _LSTR
                    self.cst = "QKEY"
                    continue
                if self._partial_delim_at_end(i) or (s[i] == "<" and self._maybe_token_prefix(i)):
                    raise _Suspend("key", i)
                self.tok_start = self.j = i
                self.cst = "BKEY"
            elif cst == "QKEY":
                i = self.tok_start
                k = s.find(STR, self.j)
                if k < 0:
                    self.j = max(self.j, len(s) - _LSTR + 1)
                    raise _Suspend("quoted key", i)
                self.warnings.append("quoted_key")
                self.stack[-1][3] = s[i + _LSTR:k]
                self.cpos = k + _LSTR
                self.cst = "COLON"
            elif cst == "BKEY":
                i = self.tok_start
                j = self.j
                n = len(s)
                while True:
                    j = _KEY_RUN.match(s, j).end()
                    if j >= n:
                        self.j = j
                        raise _Suspend("key", i)
                    if s[j] == "<":
                        if s.startswith(STR, j):
                            break
                        if self._maybe_token_prefix(j):
                            self.j = j
                            raise _Suspend("key", i)
                        j += 1
                        continue
                    break   # a forbidden character
                if j == i:
                    raise self._err("BAD_KEY", i, f"expected a key, found {s[i]!r}")
                k = s[i:j]
                for tok in PROTOCOL_TOKENS:
                    t = k.find(tok)
                    if t >= 0:
                        raise self._err("STRAY_TOKEN", i + t, f"protocol token {tok} inside a key", token=tok)
                self.stack[-1][3] = k
                self.cpos = j
                self.cst = "COLON"
            elif cst == "COLON":
                i = self._ws(self.cpos)
                self.cpos = i
                self._need(i, "':'")
                if s[i] != ":":
                    raise self._err("EXPECTED_COLON", i, f"expected ':' after key, found {s[i]!r}")
                self.cpos = i + 1
                self.cst = "VALUE"
            elif cst == "VALUE":
                i = self._ws(self.cpos)
                self.cpos = i
                fr = self.stack[-1]
                if fr[0] == "obj":
                    fr[5] = i   # vpos
                self._need(i, "value")
                if s.startswith(STR, i):
                    self.tok_start = i
                    self.j = i + _LSTR
                    self.cst = "STRING"
                    continue
                if self._partial_delim_at_end(i):
                    raise _Suspend("string", i)
                c = s[i]
                if c == "<" and self._maybe_token_prefix(i):
                    raise _Suspend("token", i)
                if c == "{":
                    self._open_obj(i + 1)
                    continue
                if c == "[":
                    self._open_arr(i)
                    continue
                for tok in PROTOCOL_TOKENS:
                    if s.startswith(tok, i):
                        raise self._err("STRAY_TOKEN", i, f"protocol token {tok} where a value was expected", token=tok)
                self.tok_start = self.j = i
                self.cst = "LITERAL"
            elif cst == "STRING":
                i = self.tok_start
                k = s.find(STR, self.j)
                if k < 0:
                    self.j = max(self.j, len(s) - _LSTR + 1)
                    raise _Suspend("string", i)
                self._value_done(s[i + _LSTR:k], k + _LSTR)
            elif cst == "LITERAL":
                i = self.tok_start
                j = _LIT_RUN.match(s, self.j).end()
                self.j = j
                if j >= len(s):
                    raise _Suspend("literal", i)
                self._value_done(self._literal(s[i:j], i), j)
            elif cst == "OBJ_SEP":
                i = self._ws(self.cpos)
                self.cpos = i
                self._need(i, "',' or '}'")
                fr = self.stack[-1]
                c = s[i]
                if c == ",":
                    if fr[6]:
                        k, v = fr[1][-1]
                        self._cev.append(("arg", len(self.calls), k, v))
                        self.argn += 1
                    self.cpos = i + 1
                    self.cst = "KEY"
                elif c == "}":
                    self._close(i + 1)
                else:
                    raise self._err("EXPECTED_SEP", i, f"expected ',' or '}}' after the value of {fr[3]!r}, found {c!r}",
                                    after_key=fr[3], value_start=fr[5])
            elif cst == "ARR_FIRST":
                i = self._ws(self.cpos)
                self.cpos = i
                self._need(i, "']'")
                if s[i] == "]":
                    self._close(i + 1)
                else:
                    self.cst = "VALUE"
            elif cst == "ARR_SEP":
                i = self._ws(self.cpos)
                self.cpos = i
                self._need(i, "',' or ']'")
                c = s[i]
                if c == ",":
                    self.cpos = i + 1
                    self.cst = "VALUE"
                elif c == "]":
                    self._close(i + 1)
                else:
                    raise self._err("EXPECTED_SEP", i, f"expected ',' or ']' in array, found {c!r}")
            elif cst == "CLOSE":
                i2 = self._ws(self.cpos)
                self.cpos = i2
                if len(s) - i2 < _LCLOSE and TOOL_CALL_CLOSE.startswith(s[i2:]):
                    raise _Suspend("'<tool_call|>'", i2)
                if not s.startswith(TOOL_CALL_CLOSE, i2):
                    raise self._err("EXPECTED_CALL_CLOSE", i2,
                                    f"expected <tool_call|> after the closing '}}', found {s[i2:i2 + 12]!r}")
                self._finish_call(i2 + _LCLOSE)
                return
            else:  # pragma: no cover
                raise AssertionError(cst)

    def _open_obj(self, i: int) -> None:
        depth = len(self.stack) + 1
        if depth > MAX_DEPTH:
            raise self._err("TOO_DEEP", i - 1, f"nesting deeper than {MAX_DEPTH}")
        self.stack.append(["obj", [], set(), None, None, None, depth == 1])
        self.cpos = i
        self.cst = "OBJ_FIRST"

    def _open_arr(self, i: int) -> None:
        if len(self.stack) + 1 > MAX_DEPTH:
            raise self._err("TOO_DEEP", i, f"nesting deeper than {MAX_DEPTH}")
        self.stack.append(["arr", []])
        self.cpos = i + 1
        self.cst = "ARR_FIRST"

    def _close(self, end: int) -> None:
        fr = self.stack.pop()
        if fr[0] == "obj":
            v = dict(fr[1])
            if fr[6]:          # the call's argument object
                self.top_pairs = fr[1]
                self.cpos = end
                self.cst = "CLOSE"
                return
        else:
            v = fr[1]
        self._value_done(v, end)

    def _value_done(self, v: Any, end: int) -> None:
        fr = self.stack[-1]
        if fr[0] == "obj":
            k = fr[3]
            if k in fr[2]:
                raise self._err("DUPLICATE_KEY", fr[4], f"duplicate key {k!r}", key=k)
            fr[2].add(k)
            fr[1].append((k, v))
            self.cst = "OBJ_SEP"
        else:
            fr[1].append(v)
            self.cst = "ARR_SEP"
        self.cpos = end

    def _literal(self, tok: str, i: int) -> Any:
        if tok == "":
            raise self._err("EXPECTED_VALUE", i, f"expected a value, found {self.s[i]!r}")
        if tok == "true":
            return True
        if tok == "false":
            return False
        if tok == "null" or (tok == "None" and self.template == JUNE):
            return None
        if tok in _SPECIAL_FLOATS:
            return _SPECIAL_FLOATS[tok]
        if _NUM_RE.match(tok):
            return int(tok) if _INT_RE.match(tok) else float(tok)
        if tok[:1] in "\"'`":
            raise self._err("JSON_STYLE_STRING", i, f"value starts with {tok[0]!r}: strings must be delimited by <|\"|>",
                            literal=tok[:40])
        raise self._err("INVALID_LITERAL", i, f"bare token {tok[:40]!r} is not true/false/null/number", literal=tok[:40])

    def _finish_call(self, end: int) -> None:
        s = self.s
        pairs = self.top_pairs
        args = dict(pairs)
        idx = len(self.calls)
        tc = ToolCall(name=self.cname, arguments=args, span=(self.cstart, end), key_order=[k for k, _ in pairs],
                      warnings=list(self.warnings))
        try:
            tc.canonical = render_call(self.cname, args, template=self.template) == s[self.cstart:end]
        except Exception:  # noqa: BLE001 - non-representable content
            tc.canonical = False
        if self.call_filter is not None:
            err = self.call_filter(tc)
            if err is not None:
                raise err
        for k, v in pairs[self.argn:]:
            self._cev.append(("arg", idx, k, v))
        self._ev.extend(self._cev)
        self._cev = []
        self._ev.append(("call_end", idx, tc))
        self.calls.append(tc)
        self._reset_call()
        self.pos = self.seg = self.cscan = self.cemit = end
        self.st = "DONE" if self.single else "CONTENT"
