"""LiteLLM SDK integration (tested with litellm 1.104): a pre-call hook that rewrites the messages.

    import litellm
    from slipguard.integrations.litellm_hook import SlipGuardHook
    litellm.callbacks.append(SlipGuardHook())
    await litellm.acompletion(model="hosted_vllm/gemma-4-31b", messages=..., tools=...)

LiteLLM runs ``async_pre_call_deployment_hook`` only on the async path (``acompletion``); the synchronous
``completion()`` has no hook that may modify the request -- use the async API (ADK always does) or
``slipguard.history.HistoryGuard`` directly. The hook never mutates the caller's list: it returns new kwargs.
"""
from __future__ import annotations

from typing import Any

from ..history import HistoryGuard
from .adk import _warn_thinking_off

try:
    from litellm.integrations.custom_logger import CustomLogger
except ImportError:  # pragma: no cover - optional dependency
    CustomLogger = object  # type: ignore[misc,assignment]


class SlipGuardHook(CustomLogger):  # type: ignore[misc,valid-type]
    def __init__(self, guard: HistoryGuard | None = None, **kwargs: Any):
        if CustomLogger is not object:
            super().__init__(**kwargs)
        self.guard = guard or HistoryGuard()
        self.last_report: list[dict] = []

    async def async_pre_call_deployment_hook(self, kwargs: dict, call_type: Any) -> dict | None:
        msgs = kwargs.get("messages")
        if not msgs:
            return None
        _warn_thinking_off(msgs, kwargs.get("extra_body"))
        tools = kwargs.get("tools")
        tl = [t if isinstance(t, dict) else dict(t) for t in tools] if tools else None
        new, report = self.guard.apply([m if isinstance(m, dict) else dict(m) for m in msgs], tl)
        self.last_report = report
        if not report:
            return None        # clean history: the request is not touched
        out = dict(kwargs)
        out["messages"] = new
        return out
