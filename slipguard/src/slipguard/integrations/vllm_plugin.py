"""vLLM plugin: a strict Gemma 4 tool-call parser and a string-aware Gemma 4 reasoning parser.

    vllm serve <gemma-4 model> --enable-auto-tool-choice \\
        --tool-parser-plugin "$(slipguard plugin-path vllm)" --tool-call-parser gemma4_strict \\
        --reasoning-parser-plugin "$(slipguard plugin-path vllm)" --reasoning-parser gemma4_strict

Registered names
  tool parsers       gemma4_strict          strict L1 calls (syntax only)
                     gemma4_strict_schema   + the call must match the request's tool schema (declared tool and keys,
                                            required keys, JSON-schema primitive types)
                     gemma4_strict_repair   + one opt-in text-only repair of the first malformed call (never silent:
                                            id suffix -ggrepaired, logged)
  reasoning parser   gemma4_strict          the thought is the leading <|channel>...<channel|> block (or, when the
                                            prompt ended inside a thought, the text before the first <channel|>);
                                            the content after it is never split again

Behaviour (identical in streaming and non-streaming):
  * calls are delivered up to the first protocol error; the malformed region and everything after it is returned
    verbatim as content (fail-visible), never as a call;
  * a call is delivered only when its <tool_call|> has arrived, in ONE streaming delta (name + full arguments JSON);
    arguments are never streamed piecemeal and a truncated call is never delivered;
  * strings are opaque: control tokens inside <|"|>...<|"|> are content (no truncation, deletion or extra calls);
  * linear time for any chunking; no recursion (deep nesting is a parse error, never RecursionError).
Tested with vLLM 0.19.1, 0.24.0, 0.31.0, 0.32.0 and 0.33.0 (one file; only the protocol import path differs). Unofficial;
not part of vLLM.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Sequence
from typing import Any

from vllm.tool_parsers.abstract_tool_parser import ToolParser, ToolParserManager

try:  # vLLM >= 0.31
    from vllm.entrypoints.generate.base.protocol import (DeltaFunctionCall, DeltaMessage, DeltaToolCall,
                                                         ExtractedToolCallInformation, FunctionCall, ToolCall)
except ImportError:  # vLLM 0.19 - 0.30
    from vllm.entrypoints.openai.engine.protocol import (DeltaFunctionCall, DeltaMessage, DeltaToolCall,
                                                         ExtractedToolCallInformation, FunctionCall, ToolCall)
from vllm.reasoning.abs_reasoning_parsers import ReasoningParser, ReasoningParserManager

try:  # vLLM loads this file by path: the slipguard package itself must be importable in vLLM's own environment
    from slipguard.parse import StreamParser, extract
    from slipguard.parse.reasoning import split_reasoning
except ModuleNotFoundError as _e:
    if not (_e.name or "").startswith("slipguard"):
        raise
    import sys as _sys
    raise ModuleNotFoundError(
        f"slipguard's vLLM plugin ({__file__}) imports the slipguard package, which is not installed in vLLM's Python "
        f"environment ({_sys.executable}). Install it there (`{_sys.executable} -m pip install slipguard`: the core "
        "package, no extras; from a checkout: `... -m pip install ./slipguard`) and restart vLLM; until then the "
        "gemma4_strict parsers are not registered.", name=_e.name) from _e

logger = logging.getLogger("slipguard.vllm")

TOOL_CALL_OPEN, TOOL_CALL_CLOSE = "<|tool_call>", "<tool_call|>"
CH_OPEN, CH_CLOSE = "<|channel>", "<channel|>"
_THOUGHT_LABEL = "thought\n"
_MARKLEN = max(len(CH_OPEN), len(CH_CLOSE), len(TOOL_CALL_OPEN))


def _tools_as_dicts(tools: Any) -> list[dict] | None:
    if not tools:
        return None
    out = []
    for t in tools:
        if isinstance(t, dict):
            out.append(t)
        elif hasattr(t, "model_dump"):
            out.append(t.model_dump(exclude_none=True))
        else:
            out.append(dict(t))
    return out


def _args_json(args: dict) -> str:
    return json.dumps(args, ensure_ascii=False)


def _call_id(call: Any = None) -> str:
    """vLLM-style id + provenance suffix: '-ggok' = delivered strictly valid (slipguard.history never quarantines it),
    '-ggrepaired' = repaired from text (slipguard.history adds a protocol warning to its tool result)."""
    sfx = "-ggrepaired" if call is not None and "repaired" in (call.warnings or []) else "-ggok"
    return f"chatcmpl-tool-{uuid.uuid4().hex[:16]}{sfx}"


def _content_or_none(s: str | None) -> str | None:
    return s if s and s.strip() else None


def _ended_on_stop(parser: Any, delta_text: str, delta_token_ids: Sequence[int] | None) -> bool:
    """The generation ended on a stop token: vLLM puts its id last in the final delta but does not output its text.
    (A stop token whose text IS in the delta was generated as content, e.g. with ignore_eos: not an end.)"""
    if not delta_token_ids or delta_token_ids[-1] not in parser._stop_ids:
        return False
    return not delta_text.endswith(parser._stop_text.get(delta_token_ids[-1], "\x00"))


def _token_id(tokenizer: Any, tok: str) -> int | None:
    """Id of one special token without building the whole vocabulary (vLLM constructs parsers per request)."""
    try:
        i = tokenizer.convert_tokens_to_ids(tok)
    except Exception:  # noqa: BLE001
        return None
    return i if isinstance(i, int) and i >= 0 and i != getattr(tokenizer, "unk_token_id", None) else None


def _stop_ids(parser: Any) -> frozenset[int]:
    """Gemma 4 stop tokens (<eos>, <turn|>, <|tool_response>): vLLM puts the stop token's id in the last delta."""
    parser._stop_text = {}
    for t in ("<eos>", "<turn|>", "<|tool_response>"):
        i = _token_id(parser.model_tokenizer, t)
        if i is not None:
            parser._stop_text[i] = t
    return frozenset(parser._stop_text)


class Gemma4StrictToolParser(ToolParser):
    """Strict, string-opaque Gemma 4 tool parser (per-call delivery up to the first protocol error)."""

    VALIDATE = "syntax"
    REPAIR = False
    supports_required_and_named = False   # vLLM >= 0.24: required/named tool_choice also goes through this parser
    # vLLM >= 0.24 calls finish_streaming() at the end of a stream only for parsers that declare this; the parser
    # accumulates delta_text itself, so it works whether the server passes cumulative or per-delta text.
    engine_based_streaming = True

    def __init__(self, tokenizer: Any, tools: Any = None, *args: Any, **kwargs: Any):
        super().__init__(tokenizer, tools)
        self._sp: StreamParser | None = None
        self._finished = False
        self._logged = 0
        self._stop_ids = _stop_ids(self)

    # -- request ----------------------------------------------------------------------------------------------
    def adjust_request(self, request: Any) -> Any:
        request = super().adjust_request(request)
        if getattr(request, "tools", None) and getattr(request, "tool_choice", None) != "none":
            request.skip_special_tokens = False   # the protocol tokens must reach the parser
        return request

    def _validate_tools(self, request: Any) -> tuple[str, list[dict] | None]:
        if self.VALIDATE == "syntax" and not self.REPAIR:
            return "syntax", None              # the strict parser needs no schema: skip the per-request conversion
        tools = _tools_as_dicts(getattr(request, "tools", None) or self.tools)
        return (self.VALIDATE if tools else "syntax"), tools

    # -- non-streaming ----------------------------------------------------------------------------------------
    def extract_tool_calls(self, model_output: str, request: Any) -> ExtractedToolCallInformation:
        validate, tools = self._validate_tools(request)
        ex = extract(model_output, tools, validate=validate, repair=bool(self.REPAIR and tools))
        for e in ex.errors:
            logger.warning("slipguard: Gemma 4 tool-call protocol error %s at %d (returned as content)", e.code, e.pos)
        for r in ex.repairs:
            logger.warning("slipguard: malformed %s call REPAIRED from text (id suffix -ggrepaired)", r["name"])
        if not ex.calls:
            return ExtractedToolCallInformation(tools_called=False, tool_calls=[], content=model_output)
        calls = [ToolCall(id=_call_id(c), type="function", function=FunctionCall(name=c.name, arguments=_args_json(c.arguments)))
                 for c in ex.calls]
        return ExtractedToolCallInformation(tools_called=True, tool_calls=calls, content=_content_or_none(ex.content))

    # -- streaming --------------------------------------------------------------------------------------------
    def extract_tool_calls_streaming(self, previous_text: str, current_text: str, delta_text: str,
                                     previous_token_ids: Sequence[int], current_token_ids: Sequence[int],
                                     delta_token_ids: Sequence[int], request: Any) -> DeltaMessage | None:
        if self._finished:
            return DeltaMessage(content=delta_text) if delta_text else None
        if self._sp is None:
            validate, tools = self._validate_tools(request)
            self._sp = StreamParser(mode="per_call", tools=tools, validate=validate,
                                    repair=bool(self.REPAIR and tools), parse_thought=False)
        events = self._sp.feed(delta_text)
        if _ended_on_stop(self, delta_text, delta_token_ids):
            events += self._sp.finish()
            self._finished = True
        return self._delta(events)

    def finish_streaming(self) -> DeltaMessage | None:
        """vLLM >= 0.24 calls this at the end of the stream: unterminated or malformed tail -> content."""
        if self._sp is None or self._finished:
            return None
        self._finished = True
        return self._delta(self._sp.finish())

    def _delta(self, events: list[tuple]) -> DeltaMessage | None:
        content: list[str] = []
        deltas: list[DeltaToolCall] = []
        for ev in events:
            if ev[0] == "content":
                content.append(ev[1])
            elif ev[0] == "call_end":
                c = ev[2]
                aj = _args_json(c.arguments)
                idx = len(self.prev_tool_call_arr)
                self.prev_tool_call_arr.append({"name": c.name, "arguments": aj})
                self.streamed_args_for_tool.append(aj)
                self.current_tool_id = idx
                self.current_tool_name_sent = True
                if "repaired" in c.warnings:
                    logger.warning("slipguard: malformed %s call REPAIRED from text (id suffix -ggrepaired)", c.name)
                deltas.append(DeltaToolCall(index=idx, id=_call_id(c), type="function",
                                            function=DeltaFunctionCall(name=c.name, arguments=aj)))
        for e in self._sp.errors[self._logged:]:
            logger.warning("slipguard: Gemma 4 tool-call protocol error %s at %d (streamed as content)", e.code, e.pos)
        self._logged = len(self._sp.errors)
        if not content and not deltas:
            return None
        return DeltaMessage(content="".join(content) or None, tool_calls=deltas)


class Gemma4StrictSchemaToolParser(Gemma4StrictToolParser):
    """gemma4_strict + the request's tool schema (a schema violation is a protocol error, returned as content)."""
    VALIDATE = "schema"


class Gemma4StrictRepairToolParser(Gemma4StrictToolParser):
    """gemma4_strict_schema + ONE opt-in text-only repair of the first malformed call (closer slips only; see
    slipguard.parse.repair_text). Never silent: the repaired call's id ends in '-ggrepaired', a warning is logged, and
    nothing after it is delivered as a call. Token-level repair (slipguard proxy) is preferred where available."""
    VALIDATE = "schema"
    REPAIR = True


class Gemma4StrictReasoningParser(ReasoningParser):
    """Reasoning parser that never re-splits the content on stray channel tokens (see split_reasoning).

    Streaming accumulates ``delta_text`` itself (it never relies on the server's cumulative ``current_text``), so it
    declares ``engine_based_streaming``: together with the tool parser, vLLM >= 0.24 then hands both parsers per-delta
    text instead of re-concatenating the whole output at every step."""

    engine_based_streaming = True

    def __init__(self, tokenizer: Any, *args: Any, **kwargs: Any):
        super().__init__(tokenizer, *args, **kwargs)
        tid = lambda t: _token_id(self.model_tokenizer, t)  # noqa: E731
        self.start_id, self.end_id = tid(CH_OPEN), tid(CH_CLOSE)
        self.tool_call_id = tid(TOOL_CALL_OPEN)
        self.turn_id, self.tool_response_id = tid("<|turn>"), tid("<|tool_response>")
        self._phase = "undecided"        # undecided -> reasoning -> content
        self._rstart = 0
        self._remit = 0
        self._buf = ""
        self._uscan = 0
        self._rscan = 0
        self._stop_ids = _stop_ids(self)

    def adjust_request(self, request: Any) -> Any:
        request.skip_special_tokens = False
        return request

    def is_reasoning_end(self, input_ids: Sequence[int]) -> bool:
        for t in reversed(input_ids):
            if t == self.start_id:
                return False
            if t == self.tool_call_id or t == self.end_id:
                return True
            if t in (self.turn_id, self.tool_response_id):
                return False
        return False

    def extract_content_ids(self, input_ids: list[int]) -> list[int]:
        ids = list(input_ids)
        if self.end_id in ids:
            return ids[ids.index(self.end_id) + 1:]
        return ids if self.start_id not in ids else []

    def extract_reasoning(self, model_output: str, request: Any) -> tuple[str | None, str | None]:
        return split_reasoning(model_output)

    def extract_reasoning_streaming(self, previous_text: str, current_text: str, delta_text: str,
                                    previous_token_ids: Sequence[int], current_token_ids: Sequence[int],
                                    delta_token_ids: Sequence[int]) -> DeltaMessage | None:
        if self._phase == "content":
            return DeltaMessage(content=delta_text) if delta_text else None
        buf = self._buf
        self._buf = ""
        buf += delta_text          # in-place append (amortised O(len(delta)))
        self._buf = buf
        s = buf
        if self._phase == "undecided":
            if len(s) < len(CH_OPEN) and CH_OPEN.startswith(s):
                return None
            if s.startswith(CH_OPEN):
                if len(s) < len(CH_OPEN) + len(_THOUGHT_LABEL) and _THOUGHT_LABEL.startswith(s[len(CH_OPEN):]):
                    return None
                self._rstart = len(CH_OPEN) + (len(_THOUGHT_LABEL) if s.startswith(_THOUGHT_LABEL, len(CH_OPEN)) else 0)
                self._remit = self._rscan = self._rstart
                self._phase = "reasoning"
            else:
                # prompt-prefilled thought vs plain content: decided by the FIRST of <channel|> (prefilled thought),
                # <|tool_call> or <|channel> (content). Incremental scan: each character is looked at O(1) times.
                lo = max(0, self._uscan - _MARKLEN + 1)
                best, which = -1, None
                for m in (CH_CLOSE, TOOL_CALL_OPEN, CH_OPEN):
                    k = s.find(m, lo)
                    if k >= 0 and (best < 0 or k < best):
                        best, which = k, m
                self._uscan = len(s)
                if which == CH_CLOSE:
                    self._phase = "content"
                    rest = s[best + len(CH_CLOSE):]
                    return DeltaMessage(reasoning=s[:best] or None, content=rest or None)
                if which is not None or _ended_on_stop(self, delta_text, delta_token_ids):
                    self._phase = "content"
                    return DeltaMessage(content=s) if s else None
                return None   # keep buffering (cannot tell reasoning from content yet)
        # reasoning phase (incremental search for the closing <channel|>)
        j = s.find(CH_CLOSE, max(self._rstart, self._rscan - len(CH_CLOSE) + 1))
        if j < 0:
            self._rscan = len(s)
            safe = len(s)
            for k in range(1, len(CH_CLOSE)):
                if s.endswith(CH_CLOSE[:k]):
                    safe = len(s) - k
            out = s[self._remit:safe] if safe > self._remit else ""
            self._remit = max(self._remit, safe)
            return DeltaMessage(reasoning=out) if out else None
        r = s[self._remit:j]
        self._remit = j
        self._phase = "content"
        rest = s[j + len(CH_CLOSE):]
        return DeltaMessage(reasoning=r or None, content=rest or None)

    def has_engine_confirmed_reasoning_end(self) -> bool:
        """vLLM >= 0.24 (engine-based streaming): the reasoning phase is over."""
        return self._phase == "content"

    def finish_streaming(self) -> DeltaMessage | None:
        """vLLM >= 0.24 calls this at the reasoning -> content transition: nothing is held back at that point."""
        return None

    def get_streaming_fallback_content(self, text: str, request: Any) -> str | None:
        """vLLM >= 0.24, stream ended before the reasoning phase was decided: the buffered text is content."""
        if self._phase == "undecided" and self._buf:
            self._phase = "content"
            return self._buf
        return None


ToolParserManager.register_module(name="gemma4_strict", module=Gemma4StrictToolParser)
ToolParserManager.register_module(name="gemma4_strict_schema", module=Gemma4StrictSchemaToolParser)
ToolParserManager.register_module(name="gemma4_strict_repair", module=Gemma4StrictRepairToolParser)
ReasoningParserManager.register_module(name="gemma4_strict", module=Gemma4StrictReasoningParser)
