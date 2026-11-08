"""Reference serializer: an exact Python port of the Gemma-4 chat-template macros
(models/gemma-4-31b-it-qat-w4a16-ct/chat_template.jinja, header "Published: 2026-07-09").

  render_value        <- macro format_argument(argument, escape_keys)
  render_call         <- the tool_calls loop of an assistant message
  render_tool_response<- macro format_tool_response_block(tool_name, response)
  render_declaration  <- macro format_function_declaration(tool_data) (+ format_parameters)

Two template versions are supported (``template=`` keyword, default JULY):
  JULY = "2026-07-09"  current official template (md5 f016bd4b...), shipped with the downloaded checkpoints
  JUNE = "2026-06-05"  earlier template used by the main-track logs (md5 d6c5bd0d...). Differences that affect
                       the notation: a None value prints as ``None`` (no none-branch in format_argument), and a
                       *string* ``function.arguments`` is printed verbatim inside ``call:NAME{...}`` (July raises).

Equality with the real Jinja templates is checked by tests/test_template_equivalence.py.
All functions are pure and dependency-free.
"""
from __future__ import annotations

import math
from typing import Any

from .tokens import STR, TOOL_CALL_OPEN, TOOL_CALL_CLOSE, TOOL_RESP_OPEN, TOOL_RESP_CLOSE


JULY = "2026-07-09"
JUNE = "2026-06-05"
TEMPLATES = (JULY, JUNE)


class TemplateError(Exception):
    """Raised where the official template itself raises (e.g. string-typed arguments)."""


def jinja_str(x: Any) -> str:
    """What Jinja's ``{{ x }}`` prints for a scalar that is not none/str/bool (i.e. Python ``str``)."""
    return str(x)


def _lower_if_str(k: Any) -> Any:
    return k.lower() if isinstance(k, str) else k


def dictsort_items(d: dict) -> list[tuple[Any, Any]]:
    """Jinja ``dictsort`` with its defaults: by key, case-INsensitive, stable for case-only ties."""
    return sorted(d.items(), key=lambda kv: _lower_if_str(kv[0]))


def render_value(v: Any, escape_keys: bool = True, template: str = JULY) -> str:
    """macro format_argument(argument, escape_keys=True).

    Tool-call arguments and tool responses call it with escape_keys=False (bare keys at every depth);
    tool declarations use the default escape_keys=True (keys wrapped in <|"|>).
    """
    if v is None:
        return "null" if template == JULY else "None"
    if isinstance(v, str):
        return STR + v + STR
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, dict):
        parts = []
        for k, val in dictsort_items(v):
            key = (STR + k + STR) if escape_keys else jinja_str(k)
            parts.append(key + ":" + render_value(val, escape_keys=escape_keys, template=template))
        return "{" + ",".join(parts) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(render_value(x, escape_keys=escape_keys, template=template) for x in v) + "]"
    return jinja_str(v)


def render_args_body(arguments: dict | str | None, template: str = JULY) -> str:
    """The text between ``call:NAME{`` and ``}<tool_call|>``."""
    if arguments is None:
        return ""
    if isinstance(arguments, str):
        if template == JUNE:
            return arguments  # printed verbatim (e.g. an un-decoded OpenAI JSON string -> call:f{{"a": 1}})
        raise TemplateError("chat_template: tool_calls[].function.arguments must be a JSON object (mapping), not a string.")
    if not isinstance(arguments, dict):
        if template == JUNE:
            return jinja_str(arguments)
        raise TemplateError("chat_template: tool_calls[].function.arguments must be a JSON object (mapping), not a string.")
    return ",".join(jinja_str(k) + ":" + render_value(v, escape_keys=False, template=template)
                    for k, v in dictsort_items(arguments))


def render_call(name: str, arguments: dict | str | None, template: str = JULY) -> str:
    """One rendered tool call, exactly as the template writes it into the history."""
    return TOOL_CALL_OPEN + "call:" + name + "{" + render_args_body(arguments, template) + "}" + TOOL_CALL_CLOSE


def render_tool_response(tool_name: str, response: Any, template: str = JULY) -> str:
    """macro format_tool_response_block(tool_name, response)."""
    if isinstance(response, dict):
        body = "response:" + tool_name + "{" + ",".join(
            jinja_str(k) + ":" + render_value(v, escape_keys=False, template=template)
            for k, v in dictsort_items(response)) + "}"
    else:
        body = "response:" + tool_name + "{value:" + render_value(response, escape_keys=False, template=template) + "}"
    return TOOL_RESP_OPEN + body + TOOL_RESP_CLOSE


# ---------------------------------------------------------------------------------------------
# Tool declarations (system turn).  Port of format_parameters / format_function_declaration.
# Jinja semantics reproduced: missing keys are Undefined (falsy, print as ''), `| upper` on
# Undefined gives '', `| default([])` only replaces Undefined (not None).
# ---------------------------------------------------------------------------------------------
_UNDEF = object()


def _get(d: Any, k: str) -> Any:
    if isinstance(d, dict) and k in d:
        return d[k]
    return _UNDEF


def _truthy(x: Any) -> bool:
    return x is not _UNDEF and bool(x)


def _upper(x: Any) -> str:
    if x is _UNDEF or x is None:
        return "" if x is _UNDEF else "NONE"
    return str(x).upper()


def _default_list(x: Any) -> Any:
    return [] if x is _UNDEF else x


def _p(x: Any) -> str:
    """Jinja print of a value (Undefined -> '')."""
    return "" if x is _UNDEF else jinja_str(x)


def _format_parameters(properties: dict, required: Any, filter_keys: bool = False, template: str = JULY) -> str:
    standard_keys = ["description", "type", "properties", "required", "nullable"]
    out: list[str] = []
    found_first = False
    for key, value in dictsort_items(properties):
        add_comma = False

        def comma() -> None:
            nonlocal add_comma
            if add_comma:
                out.append(",")
            else:
                add_comma = True

        if not filter_keys or key not in standard_keys:
            if found_first:
                out.append(",")
            found_first = True
            out.append(f"{key}:{{")
            if _truthy(_get(value, "description")):
                out.append("description:" + STR + _p(_get(value, "description")) + STR)
                add_comma = True
            vtype = _upper(_get(value, "type"))
            if vtype == "STRING":
                if _truthy(_get(value, "enum")):
                    comma()
                    out.append("enum:" + render_value(_get(value, "enum"), template=template))
            elif vtype == "ARRAY":
                items = _get(value, "items")
                if isinstance(items, dict) and items:
                    comma()
                    out.append("items:{")
                    found_items = False
                    for item_key, item_value in dictsort_items(items):
                        if item_value is not None:
                            if found_items:
                                out.append(",")
                            found_items = True
                            if item_key == "properties":
                                out.append("properties:{")
                                if isinstance(item_value, dict):
                                    out.append(_format_parameters(item_value, _default_list(_get(items, "required")), template=template))
                                out.append("}")
                            elif item_key == "required":
                                out.append("required:[" + ",".join(STR + _p(r) + STR for r in item_value) + "]")
                            elif item_key == "type":
                                if isinstance(item_value, str):
                                    out.append("type:" + render_value(item_value.upper(), template=template))
                                else:
                                    out.append("type:" + render_value([str(t).upper() for t in item_value], template=template))
                            else:
                                out.append(f"{item_key}:" + render_value(item_value, template=template))
                    out.append("}")
            if _truthy(_get(value, "nullable")):
                comma()
                out.append("nullable:true")
            if vtype == "OBJECT":
                props = _get(value, "properties")
                if props is not _UNDEF and isinstance(props, dict):
                    comma()
                    out.append("properties:{" + _format_parameters(props, _default_list(_get(value, "required")), template=template) + "}")
                elif isinstance(value, dict):
                    comma()
                    out.append("properties:{" + _format_parameters(value, _default_list(_get(value, "required")),
                                                                    filter_keys=True, template=template) + "}")
                if _truthy(_get(value, "required")):
                    comma()
                    out.append("required:[" + ",".join(STR + _p(it) + STR for it in _default_list(_get(value, "required"))) + "]")
            comma()
            out.append("type:" + STR + _upper(_get(value, "type")) + STR + "}")
    return "".join(out)


def render_declaration(tool: dict, template: str = JULY) -> str:
    """Text between ``<|tool>`` and ``<tool|>`` for one OpenAI-style tool (after the template's `| trim`)."""
    fn = tool["function"]
    out = ["declaration:" + _p(_get(fn, "name")) + "{description:" + STR + _p(_get(fn, "description")) + STR]
    params = _get(fn, "parameters")
    if _truthy(params):
        out.append(",parameters:{")
        if _truthy(_get(params, "properties")):
            out.append("properties:{" + _format_parameters(params["properties"], _get(params, "required"), template=template) + "},")
        if _truthy(_get(params, "required")):
            out.append("required:[" + ",".join(STR + _p(it) + STR for it in params["required"]) + "],")
        if _truthy(_get(params, "type")):
            out.append("type:" + STR + _upper(params["type"]) + STR + "}")
    if "response" in fn:
        rd = fn["response"]
        out.append(",response:{")
        if _truthy(_get(rd, "description")):
            out.append("description:" + STR + _p(_get(rd, "description")) + STR + ",")
        if _upper(_get(rd, "type")) == "OBJECT":
            out.append("type:" + STR + _upper(_get(rd, "type")) + STR + "}")
    out.append("}")
    return "".join(out).strip()


def is_representable(v: Any, *, _depth: int = 0) -> bool:
    """True iff render_value/render_call is injective on v (i.e. v survives parse(render(v))).

    Not representable: strings containing <|"|> (no escaping exists), mapping keys that are empty,
    contain whitespace or one of  : , { } [ ]  or contain <|"|>, and non-JSON scalar types.
    """
    if v is None or isinstance(v, bool):
        return True
    if isinstance(v, str):
        return STR not in v
    if isinstance(v, int):
        return True
    if isinstance(v, float):
        return True  # inf / nan / exponent forms are printed by Python str() and parsed back (see spec)
    if isinstance(v, (list, tuple)):
        return all(is_representable(x, _depth=_depth + 1) for x in v)
    if isinstance(v, dict):
        return all(isinstance(k, str) and is_bare_key(k) and is_representable(x, _depth=_depth + 1) for k, x in v.items())
    return False


_KEY_FORBIDDEN = set(":,{}[]") | set(" \t\n\r\f\v") | set("\"'`")


def is_bare_key(k: str) -> bool:
    """Keys the template can print bare and a parser can read back unambiguously (spec 4.2)."""
    from .tokens import PROTOCOL_TOKENS
    return (bool(k) and STR not in k and not any(t in k for t in PROTOCOL_TOKENS)
            and not any(c in _KEY_FORBIDDEN or c.isspace() for c in k))


def values_equal(a: Any, b: Any) -> bool:
    """Type-exact structural equality (bool is not int, 1 is not 1.0, nan == nan, -0.0 != 0.0)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b and math.copysign(1.0, a) == math.copysign(1.0, b)
    if isinstance(a, dict):
        return set(a.keys()) == set(b.keys()) and all(values_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(values_equal(x, y) for x, y in zip(a, b))
    return a == b
