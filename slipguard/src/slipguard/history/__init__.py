"""Transcript hygiene for Gemma 4 agents (OpenAI-format message lists). See pipeline.HistoryGuard."""
from .neutralize import SPECIAL_TOKENS, has_control_text, neutralize_text, unneutralize_text
from .pipeline import HistoryGuard, NotGemmaError
from .transforms import (CLOSED_THOUGHT, close_thought, mark_repaired, native_tool_results, needs_closed_thought,
                         neutralize, quarantine, raw_calls_in_content)

__all__ = ["HistoryGuard", "NotGemmaError", "SPECIAL_TOKENS", "has_control_text", "neutralize_text",
           "unneutralize_text", "CLOSED_THOUGHT", "close_thought", "needs_closed_thought", "quarantine", "neutralize",
           "native_tool_results", "raw_calls_in_content", "mark_repaired"]
