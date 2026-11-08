"""HistoryGuard: one call that applies the history transforms in a fixed order.

    g = HistoryGuard()                       # quarantine + raw-call removal + neutralization (native results: off)
    messages2, report = g.apply(messages, tools, raw_by_call_id=None)

Order: raw calls in content -> quarantine (+ repaired-call warnings) -> native tool results (opt-in) -> neutralize.
Clean histories come back unchanged (``messages2 == messages`` and ``report == []``).

Gemma-only by design: quarantine text and closure tokens are Gemma 4 specific, and the quarantine text induces a
different protocol failure in another model family (Qwen3-8B, workstream X). ``model=`` names that do not look like
Gemma 4 are refused unless ``allow_non_gemma=True``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from . import transforms as T

_GEMMA4 = re.compile(r"gemma[-_ ]?4", re.I)


class NotGemmaError(ValueError):
    pass


@dataclass
class HistoryGuard:
    quarantine: bool = True
    raw_calls: bool = True
    neutralize: bool = True
    native_tool_results: bool = False      # PREREG_v2.3 pending: off by default
    model: str | None = None
    allow_non_gemma: bool = False

    def __post_init__(self) -> None:
        if self.model is not None and not _GEMMA4.search(self.model) and not self.allow_non_gemma:
            raise NotGemmaError(f"slipguard's history transforms are tailored to Gemma 4; model {self.model!r} does not "
                                "look like Gemma 4 (pass allow_non_gemma=True to override)")

    def apply(self, messages: list[dict], tools: list[dict] | None = None, *,
              raw_by_call_id: dict[str, str] | None = None,
              strictly_valid_ids: Iterable[str] | None = None) -> tuple[list[dict], list[dict]]:
        report: list[dict] = []
        msgs = messages
        if self.raw_calls:
            msgs, a = T.raw_calls_in_content(msgs)
            report += a
        if self.quarantine:
            sv = set(strictly_valid_ids or ()) | T.strict_ids(msgs)      # + calls delivered by slipguard's strict parser
            msgs, a = T.quarantine(msgs, tools, raw_by_call_id=raw_by_call_id, strictly_valid_ids=sv or None)
            report += a
            msgs, a = T.mark_repaired(msgs)
            report += a
        if self.native_tool_results:
            msgs, a = T.native_tool_results(msgs)
            report += a
        if self.neutralize:
            msgs, a = T.neutralize(msgs)
            report += a
        if msgs is messages:
            import copy
            msgs = copy.deepcopy(messages)
        return msgs, report
