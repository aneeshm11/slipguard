"""History transforms on OpenAI-format chat messages. Every transform is pure (deep copies), returns
``(messages, actions)``, and is the identity -- ``actions == []`` and the output equal to the input -- on a clean
history (tested).

  quarantine            workstream E's frozen shipped renderer (the `fullp` behaviour): malformed historical calls are
                        re-rendered (recovered from the raw emission when known, else sanitized) and their tool results
                        become a MalformedToolCall error
  raw_calls_in_content  assistant text that still carries raw Gemma tool-call markup (a call a fail-loud parser
                        returned as content) is replaced by a short notice, so the corrupted call is not shown again
  native_tool_results   exact inverse of ADK 1.36.1 + LiteLLM's tool-result serialization ``json.dumps({'result': c})``
                        (opt-in; off by default)
  neutralize            control-token text in tool results, string arguments, keys and names made inert (reversible)
  close_thought         prompt-level: the closed empty thought after a tool response when thinking is off
"""
from __future__ import annotations

import copy
import json
from typing import Any, Iterable

from .neutralize import has_control_text, neutralize_text, neutralize_value, value_has_control_text

TOOL_CALL_OPEN, TOOL_CALL_CLOSE = "<|tool_call>", "<tool_call|>"
TOOL_RESPONSE_CLOSE = "<tool_response|>"
CLOSED_THOUGHT = "<|channel>thought\n<channel|>"
CLOSED_THOUGHT_IDS = (100, 45518, 107, 101)      # Gemma 4 tokenizer: <|channel> 'thought' '\n' <channel|>
TOOL_RESPONSE_CLOSE_ID = 51
REPAIRED_SUFFIX = "-ggrepaired"
STRICT_SUFFIX = "-ggok"          # tool-call ids of calls delivered by slipguard's strict parser (plugin / lite proxy)


def strict_ids(messages: list[dict]) -> set[str]:
    """Ids of historical calls that slipguard's strict parser delivered: strictly valid when emitted."""
    return {tc["id"] for m in messages if m.get("role") == "assistant" for tc in (m.get("tool_calls") or [])
            if isinstance(tc.get("id"), str) and tc["id"].endswith(STRICT_SUFFIX)}


def _text_of(content: Any) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return None


# ------------------------------------------------------------------------------------------------- quarantine
def quarantine(messages: list[dict], tools: list[dict] | None, raw_by_call_id: dict[str, str] | None = None,
               strictly_valid_ids: Iterable[str] | None = None) -> tuple[list[dict], list[dict]]:
    """Workstream E's frozen ``quarantine_messages`` (canonical=False, as in the evaluated `fullp` cfg)."""
    from .._frozen import load_e
    qr = load_e().quarantine_renderer
    if not tools:
        return copy.deepcopy(messages), []
    out, actions = qr.quarantine_messages(messages, tools, raw_by_call_id=raw_by_call_id, canonical=False,
                                          strictly_valid_ids=set(strictly_valid_ids) if strictly_valid_ids else None)
    return out, [{"transform": "quarantine", **a} for a in actions]


def mark_repaired(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Tool results of calls that slipguard's lenient mode repaired (id suffix) get a protocol_warning."""
    ids = {tc.get("id") for m in messages if m.get("role") == "assistant" for tc in (m.get("tool_calls") or [])
           if isinstance(tc.get("id"), str) and tc["id"].endswith(REPAIRED_SUFFIX)}
    if not ids:
        return copy.deepcopy(messages), []
    out, actions = copy.deepcopy(messages), []
    for m in out:
        if m.get("role") == "tool" and m.get("tool_call_id") in ids:
            note = ("protocol_warning: this tool call was emitted malformed and repaired from its text before it "
                    "was executed; check the result.")
            if isinstance(m.get("content"), str):
                m["content"] = m["content"] + "\n" + note
            actions.append({"transform": "mark_repaired", "id": m.get("tool_call_id")})
    return out, actions


# ------------------------------------------------------------------------------------------------- raw calls
def raw_calls_in_content(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Replace raw Gemma tool-call markup left in assistant text (a malformed call returned as content) by a notice."""
    if not any(m.get("role") == "assistant" and TOOL_CALL_OPEN in (_text_of(m.get("content")) or "") for m in messages):
        return copy.deepcopy(messages), []
    out, actions = copy.deepcopy(messages), []
    for i, m in enumerate(out):
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        if isinstance(c, str) and TOOL_CALL_OPEN in c:
            new, removed = _strip_raw_calls(c)
            m["content"] = new
            actions.append({"transform": "raw_calls_in_content", "message": i, "removed": removed})
        elif isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and p.get("type") == "text" and TOOL_CALL_OPEN in (p.get("text") or ""):
                    p["text"], removed = _strip_raw_calls(p["text"])
                    actions.append({"transform": "raw_calls_in_content", "message": i, "removed": removed})
    return out, actions


NOTICE = "[A tool call in this message was malformed and was not executed. Re-issue it if it is still needed.]"


def _strip_raw_calls(text: str) -> tuple[str, list[str]]:
    parts, removed, i = [], [], 0
    while True:
        p = text.find(TOOL_CALL_OPEN, i)
        if p < 0:
            parts.append(text[i:])
            break
        parts.append(text[i:p])
        e = text.find(TOOL_CALL_CLOSE, p + len(TOOL_CALL_OPEN))
        n = text.find(TOOL_CALL_OPEN, p + len(TOOL_CALL_OPEN))
        end = len(text) if e < 0 else e + len(TOOL_CALL_CLOSE)
        if 0 <= n < end:
            end = n
        removed.append(text[p:end])
        parts.append(NOTICE)
        i = end
    return "".join(parts), removed


# ------------------------------------------------------------------------------------------------- native results
def native_tool_results(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Exact inverse of ADK 1.36.1 + LiteLLM's serialization of a text tool result: content
    ``json.dumps({'result': c}, ensure_ascii=False)`` with a string ``c`` becomes ``c``. Anything else is unchanged."""
    out, actions = copy.deepcopy(messages), []
    for i, m in enumerate(out):
        if m.get("role") != "tool" or not isinstance(m.get("content"), str):
            continue
        c = _unwrap_result(m["content"])
        if c is not None:
            m["content"] = c
            actions.append({"transform": "native_tool_results", "message": i})
    return out, actions


def _unwrap_result(s: str) -> str | None:
    if not s.startswith('{"result": '):
        return None
    try:
        o = json.loads(s)
    except ValueError:
        return None
    if isinstance(o, dict) and len(o) == 1 and isinstance(o.get("result"), str) \
            and json.dumps({"result": o["result"]}, ensure_ascii=False) == s:
        return o["result"]
    return None


# ------------------------------------------------------------------------------------------------- neutralize
def neutralize(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Make control-token text inert in tool results, historical call arguments (deep, keys included), call names
    and tool-result names. System, user and model text and thoughts are not touched (trusted principals or the
    model's own output)."""
    out, actions = copy.deepcopy(messages), []
    for i, m in enumerate(out):
        role = m.get("role")
        if role == "tool":
            c = m.get("content")
            if isinstance(c, str) and has_control_text(c):
                m["content"] = neutralize_text(c)
                actions.append({"transform": "neutralize", "message": i, "field": "content"})
            elif isinstance(c, list):
                # the template concatenates the text parts: neutralize the concatenation (a token may span parts),
                # keep it in the first text part and empty the others
                tparts = [p for p in c if isinstance(p, dict) and p.get("type") == "text"]
                joined = "".join(p.get("text") or "" for p in tparts)
                if has_control_text(joined):
                    tparts[0]["text"] = neutralize_text(joined)
                    for p in tparts[1:]:
                        p["text"] = ""
                    actions.append({"transform": "neutralize", "message": i, "field": "content[].text"})
            if isinstance(m.get("name"), str) and has_control_text(m["name"]):
                m["name"] = neutralize_text(m["name"])
                actions.append({"transform": "neutralize", "message": i, "field": "name"})
        elif role == "assistant":
            for tr in m.get("tool_responses") or []:      # legacy Gemma-native field on assistant messages
                if isinstance(tr, dict):
                    if isinstance(tr.get("name"), str) and has_control_text(tr["name"]):
                        tr["name"] = neutralize_text(tr["name"])
                        actions.append({"transform": "neutralize", "message": i, "field": "tool_responses[].name"})
                    if value_has_control_text(tr.get("response")):
                        tr["response"] = neutralize_value(tr["response"])
                        actions.append({"transform": "neutralize", "message": i, "field": "tool_responses[].response"})
            for tc in m.get("tool_calls") or []:
                f = tc.get("function") or {}
                if isinstance(f.get("name"), str) and has_control_text(f["name"]):
                    f["name"] = neutralize_text(f["name"])
                    actions.append({"transform": "neutralize", "message": i, "field": "tool_calls[].function.name"})
                a = f.get("arguments")
                if isinstance(a, str):
                    if not has_control_text(a):
                        continue           # JSON text without control-token text: no value inside has any
                    try:
                        args = json.loads(a)
                    except ValueError:
                        f["arguments"] = neutralize_text(a)
                    else:
                        f["arguments"] = json.dumps(neutralize_value(args), ensure_ascii=False)
                    actions.append({"transform": "neutralize", "message": i, "field": "tool_calls[].function.arguments"})
                elif isinstance(a, (dict, list)) and value_has_control_text(a):
                    f["arguments"] = neutralize_value(a)
                    actions.append({"transform": "neutralize", "message": i, "field": "tool_calls[].function.arguments"})
    return out, actions


# ------------------------------------------------------------------------------------------------- closure
def needs_closed_thought(prompt: str | list[int], enable_thinking: bool | None) -> bool:
    """The rendered prompt ends right after a tool response and thinking is off (the template added nothing)."""
    if enable_thinking:
        return False
    if isinstance(prompt, str):
        return prompt.endswith(TOOL_RESPONSE_CLOSE)
    return bool(prompt) and prompt[-1] == TOOL_RESPONSE_CLOSE_ID


def close_thought(prompt: str | list[int], enable_thinking: bool | None) -> str | list[int]:
    """Append the closed empty thought ``<|channel>thought\\n<channel|>`` (text or Gemma 4 token ids) when the
    prompt ends after a tool response with thinking off -- the branch the shipped templates are missing. With it,
    Gemma 4 did not re-open a thought in 188/188 contexts; without it, it thinks anyway (583/587, 584/588)."""
    if not needs_closed_thought(prompt, enable_thinking):
        return prompt
    if isinstance(prompt, str):
        return prompt + CLOSED_THOUGHT
    return list(prompt) + list(CLOSED_THOUGHT_IDS)
