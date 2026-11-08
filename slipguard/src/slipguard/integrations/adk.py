"""Google ADK integration (tested with google-adk 1.36.1 + LiteLLM 1.104).

Full hygiene for an ADK agent that talks to Gemma 4 through LiteLLM -- recommended:

    from slipguard.integrations.adk import guarded_lite_llm
    agent = LlmAgent(model=guarded_lite_llm("hosted_vllm/gemma-4-31b", api_base=...), ...)

``GuardedLiteLLMClient`` rewrites the final OpenAI-format messages (the exact list LiteLLM sends) with
:class:`slipguard.history.HistoryGuard` before every model call. ADK rebuilds the history from the session for every
call, so the session itself is never modified.

``SlipGuardPlugin`` (an ADK ``BasePlugin``, Content level) neutralizes control-token text in function responses and
function-call arguments for agents that do not go through LiteLLM; quarantine needs the message level (above).

Neither hook can add the thinking-off closure (it is not expressible in chat messages): serve the patched template
(``slipguard template-path``) instead. Both warn once when a request is in that state.
"""
from __future__ import annotations

import logging
from typing import Any

from ..history import HistoryGuard
from ..history.neutralize import neutralize_value, value_has_control_text

logger = logging.getLogger("slipguard.adk")
_WARNED = {"thinking_off": False}


def _warn_thinking_off(messages: list, extra_body: dict | None) -> None:
    if _WARNED["thinking_off"] or not messages:
        return
    ctk = (extra_body or {}).get("chat_template_kwargs") or {}
    last = messages[-1]
    role = last.get("role") if isinstance(last, dict) else getattr(last, "role", None)
    if role in ("tool", "tool_responses") and not ctk.get("enable_thinking", False):
        _WARNED["thinking_off"] = True
        logger.warning("slipguard: thinking is off but the prompt ends after a tool result; the shipped Gemma 4 "
                       "templates add no closed thought there, so the model will think anyway. Serve slipguard's "
                       "patched template (`slipguard template-path`) to fix it.")


try:
    from google.adk.models.lite_llm import LiteLLMClient, LiteLlm
except ImportError:  # pragma: no cover - optional dependency
    LiteLLMClient = object  # type: ignore[misc,assignment]
    LiteLlm = None  # type: ignore[assignment]


class GuardedLiteLLMClient(LiteLLMClient):  # type: ignore[misc,valid-type]
    """LiteLLMClient that applies HistoryGuard to the messages of every call."""

    def __init__(self, guard: HistoryGuard | None = None):
        self.guard = guard or HistoryGuard()
        self.last_report: list[dict] = []

    def _clean(self, messages: list, tools: Any, kwargs: dict) -> list:
        _warn_thinking_off(messages, kwargs.get("extra_body"))
        tl = [t if isinstance(t, dict) else dict(t) for t in tools] if tools else None
        new, report = self.guard.apply([m if isinstance(m, dict) else dict(m) for m in messages], tl)
        self.last_report = report
        return new if report else messages

    async def acompletion(self, model, messages, tools, **kwargs):
        return await super().acompletion(model, self._clean(messages, tools, kwargs), tools, **kwargs)

    def completion(self, model, messages, tools, stream=False, **kwargs):
        return super().completion(model, self._clean(messages, tools, kwargs), tools, stream=stream, **kwargs)


def guarded_lite_llm(model: str, guard: HistoryGuard | None = None, **kwargs: Any):
    """``LiteLlm(model, llm_client=GuardedLiteLLMClient(guard), **kwargs)``."""
    if LiteLlm is None:
        raise ImportError("google-adk is not installed (pip install 'slipguard[adk]')")
    return LiteLlm(model=model, llm_client=GuardedLiteLLMClient(guard or HistoryGuard(model=model)), **kwargs)


try:
    from google.adk.plugins.base_plugin import BasePlugin
except ImportError:  # pragma: no cover
    BasePlugin = object  # type: ignore[misc,assignment]


class SlipGuardPlugin(BasePlugin):  # type: ignore[misc,valid-type]
    """Content-level hygiene: control-token text in function responses / call arguments made inert (copies only)."""

    def __init__(self, name: str = "slipguard"):
        super().__init__(name=name)

    async def before_model_callback(self, *, callback_context: Any, llm_request: Any) -> None:
        contents = getattr(llm_request, "contents", None) or []
        changed = False
        new_contents = []
        for content in contents:
            parts = getattr(content, "parts", None) or []
            if not any(_part_hazard(p) for p in parts):
                new_contents.append(content)
                continue
            c2 = content.model_copy(deep=True)
            for p in c2.parts:
                fr = getattr(p, "function_response", None)
                if fr is not None and value_has_control_text(fr.response):
                    fr.response = neutralize_value(fr.response)
                fc = getattr(p, "function_call", None)
                if fc is not None and value_has_control_text(fc.args):
                    fc.args = neutralize_value(fc.args)
            new_contents.append(c2)
            changed = True
        if changed:
            llm_request.contents = new_contents
        return None


async def before_model_callback(callback_context: Any, llm_request: Any) -> None:
    """Plain ADK callback (``LlmAgent(before_model_callback=before_model_callback)``): same as SlipGuardPlugin."""
    await SlipGuardPlugin.before_model_callback(_PLUGIN, callback_context=callback_context, llm_request=llm_request)
    return None


def _part_hazard(p: Any) -> bool:
    fr = getattr(p, "function_response", None)
    fc = getattr(p, "function_call", None)
    return bool((fr is not None and value_has_control_text(fr.response)) or
                (fc is not None and value_has_control_text(fc.args)))


_PLUGIN = SlipGuardPlugin() if BasePlugin is not object else None
