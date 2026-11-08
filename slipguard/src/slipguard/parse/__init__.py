"""Strict, string-opaque, linear-time Gemma 4 tool-call parsing.

Three ways to parse, one engine (:mod:`slipguard.parse.engine`):

``parse_call(text)``
    exactly one ``<|tool_call>call:NAME{...}<tool_call|>``; anything else raises :class:`ParseError`.
``parse_completion(text)``
    a whole completion (thought, content, calls, terminator), all or nothing: the result has exactly the calls the
    model emitted, or :class:`ParseError` is raised. Same results and errors as the executable specification
    (gemmaproto), which the tests use as the oracle.
``extract(text, tools)`` / ``StreamParser(mode="per_call")``
    runtime semantics used by the server plugins. Calls are delivered **up to the first protocol error**; every
    other region, including a malformed call and everything after it, is returned verbatim as content, and the
    errors are listed. Streaming and non-streaming deliver the same calls and the same content, and a call is never
    delivered partially.

Error codes (``ParseError.code``): see ``ERROR_CODES``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from .._vendor.gemmaproto.parser import ERROR_CODES
from .._vendor.gemmaproto.serializer import JULY, JUNE, render_call
from .._vendor.gemmaproto.tokens import TOOL_CALL_OPEN
from .engine import MAX_DEPTH, Engine, ParseError, ParsedCompletion, ToolCall
from .schema import schema_error, tool_schemas

__all__ = ["parse_call", "parse_completion", "extract", "Extraction", "StreamParser", "ParseError", "ToolCall",
           "ParsedCompletion", "ERROR_CODES", "MAX_DEPTH", "JULY", "JUNE", "render_call"]


def parse_completion(text: str, *, in_thought: bool = False, allow_ws: bool = True, strict_content: bool = True,
                     template: str = JULY) -> ParsedCompletion:
    """Parse a whole completion (decoded with special tokens kept). Raises ParseError on anything outside L1."""
    e = Engine(mode="completion", in_thought=in_thought, allow_ws=allow_ws, strict_content=strict_content,
               template=template)
    e.feed_text(text)
    e.finish()
    return e.result()


def parse_call(text: str, *, allow_ws: bool = True, template: str = JULY) -> ToolCall:
    """Parse exactly one tool call (nothing before or after it)."""
    if not text.startswith(TOOL_CALL_OPEN):
        raise ParseError("NO_CALL_OPEN", 0, "text does not start with <|tool_call>", text)
    e = Engine(mode="completion", parse_thought=False, allow_ws=allow_ws, strict_content=False, template=template)
    e.single = True
    e.s = text
    e.final = True
    e.st, e.cstart, e.cst, e.cpos = "CALL", 0, "HDR", len(TOOL_CALL_OPEN)
    e._run()
    tc = e.calls[0]
    if tc.span[1] != len(text):
        raise ParseError("TRAILING_TEXT", tc.span[1], "text after <tool_call|>", text)
    return tc


@dataclass
class Extraction:
    """Result of the runtime (per-call) parse."""
    calls: list[ToolCall]
    content: str | None
    errors: list[ParseError] = field(default_factory=list)
    thought: str | None = None
    repairs: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"calls": [c.to_dict() for c in self.calls], "content": self.content,
                "errors": [e.to_dict() for e in self.errors], "thought": self.thought, "repairs": self.repairs}


def _filter_for(tools: Iterable[dict] | None, validate: str) -> Callable[[ToolCall], ParseError | None] | None:
    if validate == "syntax" or tools is None:
        return None
    schemas = tool_schemas(tools)
    return lambda tc: schema_error(tc, schemas, strict=(validate == "schema"))


class StreamParser:
    """Incremental parser over one completion.

    ``mode="completion"``: events of the whole-completion parse; raises ParseError as soon as the error is
    determined (prefix-safe: the same code and position as the one-shot parse of the full text).
    ``mode="per_call"``: never raises; events are ``("content", text)``, ``("thought", text)``,
    ``("thought_end", thought)``, ``("call_start", i, name)``, ``("arg", i, key, value)``, ``("call_end", i, call)``,
    ``("terminator", tok)``; a ``call_end`` is final (only strict calls get one). ``errors`` lists protocol errors.
    ``validate``: "syntax" (default), "declared" (the tool must be declared) or "schema" (declared tool, declared
    keys, required keys present, JSON-schema primitive types) -- needs ``tools``.
    """

    def __init__(self, *, mode: str = "completion", tools: Iterable[dict] | None = None, validate: str = "syntax",
                 repair: bool = False, in_thought: bool = False, parse_thought: bool = True,
                 strict_content: bool = True, template: str = JULY):
        self.engine = Engine(mode=mode, in_thought=in_thought, parse_thought=parse_thought,
                             strict_content=strict_content, template=template)
        self.engine.call_filter = _filter_for(tools, validate)
        if repair:
            if mode != "per_call" or not tools:
                raise ValueError("repair needs mode='per_call' and the request's tools")
            from .repair_text import make_repair_fn
            self.engine.repair_fn = make_repair_fn(tools)

    @property
    def repairs(self) -> list[dict]:
        return self.engine.repairs

    def feed(self, chunk: str) -> list[tuple]:
        return self.engine.feed(chunk)

    def feed_text(self, text: str) -> list[tuple]:
        return self.engine.feed_text(text)

    def finish(self) -> list[tuple]:
        return self.engine.finish()

    @property
    def errors(self) -> list[ParseError]:
        return self.engine.errors

    def result(self) -> ParsedCompletion:
        return self.engine.result()


def extract(text: str, tools: Iterable[dict] | None = None, *, validate: str = "syntax", repair: bool = False,
            in_thought: bool = False, parse_thought: bool = False, strict_content: bool = True,
            template: str = JULY) -> Extraction:
    """Runtime parse of model output (per-call delivery up to the first protocol error). Never raises ParseError.
    ``repair=True`` (needs ``tools``): the first malformed call gets one text-only repair attempt (see
    slipguard.parse.repair_text); a repaired call carries ``warnings == ['repaired', 'repair_rule:<kwarg|closer>']`` and is listed in
    ``repairs``."""
    sp = StreamParser(mode="per_call", tools=tools, validate=validate, repair=repair, in_thought=in_thought,
                      parse_thought=parse_thought, strict_content=strict_content, template=template)
    sp.feed_text(text)
    sp.finish()
    e = sp.engine
    content = "".join(e.content)
    return Extraction(calls=list(e.calls), content=content if content else None, errors=list(e.errors),
                      thought=e.thought, repairs=list(e.repairs))


