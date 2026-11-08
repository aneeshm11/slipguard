"""Integrations: vLLM plugin file, SGLang shim (experimental), ADK and LiteLLM hooks (see slipguard.history)."""
from __future__ import annotations

import os

_FILES = {"vllm": "vllm_plugin.py"}


def plugin_path(kind: str = "vllm") -> str:
    """Absolute path of the plugin file to pass to `vllm serve --tool-parser-plugin / --reasoning-parser-plugin`."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), _FILES[kind])
