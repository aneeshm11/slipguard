"""EXPERIMENTAL SGLang shim: a strict Gemma 4 function-call detector (``--tool-call-parser gemma4_strict``).

SGLang has no parser-plugin flag. Registration happens through SGLang's general plugin entry point
(``sglang.srt.plugins``, installed with slipguard; restrict with ``SGLANG_PLUGINS=slipguard``), or by calling
:func:`register` in every process that serves HTTP before the server arguments are parsed.

Semantics are those of :mod:`slipguard.parse` (per-call delivery up to the first protocol error; everything else is
returned verbatim as normal text); calls to undeclared tools are refused (returned as text), because SGLang's serving
layer drops them silently. SGLang's own gemma4 reasoning parser runs before the detector and splits the output on
channel tokens even inside strings; slipguard does not ship a replacement for it. ``ToolCallItem.tool_index`` is the call's ordinal, so two calls to the same tool
are never merged by the streaming layer. Tested only through SGLang's function-call modules on CPU (0.5.23).
"""
from __future__ import annotations

import json
from typing import Any, List

from ..parse import StreamParser, extract


def _detector_class():
    from sglang.srt.function_call.base_format_detector import BaseFormatDetector
    from sglang.srt.function_call.core_types import StreamingParseResult, ToolCallItem

    def _tools(tools: Any) -> list[dict] | None:
        out = []
        for t in tools or []:
            out.append(t.model_dump(exclude_none=True) if hasattr(t, "model_dump") else dict(t))
        return out or None

    class Gemma4StrictDetector(BaseFormatDetector):
        def __init__(self):
            super().__init__()
            self.bot_token, self.eot_token = "<|tool_call>", "<tool_call|>"
            self._sp: StreamParser | None = None
            self._n = 0

        def has_tool_call(self, text: str) -> bool:
            return "<|tool_call>" in text

        def detect_and_parse(self, text: str, tools: List[Any]) -> StreamingParseResult:
            # undeclared tools are refused HERE (returned as text): SGLang's serving layer would otherwise drop such a
            # call silently. A leading thought (no reasoning parser configured) stays in the normal text.
            tl = _tools(tools)
            ex = extract(text, tl, validate="declared" if tl else "syntax", parse_thought=True)
            calls = [ToolCallItem(tool_index=i, name=c.name, parameters=json.dumps(c.arguments, ensure_ascii=False))
                     for i, c in enumerate(ex.calls)]
            if not calls:
                return StreamingParseResult(normal_text=text, calls=[])
            head = ""
            if ex.thought is not None:
                k = text.find("<channel|>")
                head = text[:k + len("<channel|>")] if k >= 0 else ""
            return StreamingParseResult(normal_text=head + (ex.content or ""), calls=calls)

        def _result(self, events: list[tuple]) -> StreamingParseResult:
            text, calls = [], []
            for ev in events:
                if ev[0] == "content":
                    text.append(ev[1])
                elif ev[0] == "call_end":
                    c = ev[2]
                    calls.append(ToolCallItem(tool_index=self._n, name=c.name,
                                              parameters=json.dumps(c.arguments, ensure_ascii=False)))
                    self._n += 1
            return StreamingParseResult(normal_text="".join(text), calls=calls)

        def parse_streaming_increment(self, new_text: str, tools: List[Any]) -> StreamingParseResult:
            if self._sp is None:
                tl = _tools(tools)
                self._sp = StreamParser(mode="per_call", tools=tl, validate="declared" if tl else "syntax",
                                        parse_thought=False)
            return self._result(self._sp.feed(new_text))

        def finish(self, tools: List[Any]) -> StreamingParseResult:
            if self._sp is None:
                return StreamingParseResult()
            sp, self._sp = self._sp, None
            return self._result(sp.finish())

        def supports_structural_tag(self) -> bool:
            return False

        def structure_info(self):
            raise NotImplementedError("gemma4_strict does not support structural tags")

    return Gemma4StrictDetector


def register(name: str = "gemma4_strict") -> None:
    """Register the detector under ``name`` (idempotent). Also the ``sglang.srt.plugins`` entry point."""
    from sglang.srt.function_call import parser_names
    from sglang.srt.function_call.function_call_parser import FunctionCallParser
    FunctionCallParser.ToolCallParserEnum[name] = _detector_class()
    if name not in parser_names.TOOL_CALL_PARSER_NAMES:
        parser_names.TOOL_CALL_PARSER_NAMES.append(name)
