"""slipguard -- tool-call hygiene for Gemma 4 agents (unofficial; not affiliated with or endorsed by Google).

Modules
  slipguard.parse      strict, string-opaque, linear-time parser (one-shot, streaming, per-call runtime mode)
  slipguard.repair     intent-preserving decoding (verify-then-repair) proxy + Python API (the evaluated code, frozen)
  slipguard.history    transcript hygiene for OpenAI-format message lists (+ ADK / LiteLLM integrations)
  slipguard.template   patched Gemma 4 chat template (thinking-off closure, control-token neutralization)
  slipguard.integrations.vllm_plugin   vLLM --tool-parser-plugin / --reasoning-parser-plugin file
"""
from ._name import DIST_NAME, TAGLINE
from ._version import __version__
from .parse import ParseError, ToolCall, extract, parse_call, parse_completion, StreamParser

__all__ = ["__version__", "DIST_NAME", "TAGLINE", "ParseError", "ToolCall", "extract", "parse_call",
           "parse_completion", "StreamParser"]
