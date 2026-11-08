"""Schema checks applied to strictly parsed calls (opt-in: ``validate="declared"`` or ``"schema"``).

A syntactically valid call can still be damaged at the schema level (spec 6: a slip that drops the absorbed value
*and* its delimiters restores parity). These checks make such calls fail loudly too.
"""
from __future__ import annotations

from typing import Any, Iterable

from .._vendor.gemmaproto.parser import ParseError, ToolCall

SCHEMA_ERROR_CODES = {
    "UNDECLARED_TOOL": "the call names a tool that is not declared in the request",
    "UNDECLARED_KEY": "an argument that the tool does not declare",
    "MISSING_REQUIRED": "a required argument is missing",
    "TYPE_MISMATCH": "an argument value does not have the declared JSON-schema type",
}


class SchemaError(ParseError):
    """A strictly valid call that fails the request's tool schema. ``code`` is one of SCHEMA_ERROR_CODES."""


def tool_schemas(tools: Iterable[dict] | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for t in tools or []:
        t = t if isinstance(t, dict) else dict(t)
        f = t.get("function", t)
        if not isinstance(f, dict) or "name" not in f:
            continue
        p = f.get("parameters") or {}
        out[f["name"]] = {"properties": dict(p.get("properties") or {}), "required": list(p.get("required") or [])}
    return out


_PY = {"string": (str,), "integer": (int,), "number": (int, float), "boolean": (bool,), "array": (list,),
       "object": (dict,), "null": (type(None),)}


def type_ok(v: Any, spec: Any) -> bool:
    if not isinstance(spec, dict):
        return True
    ty = spec.get("type")
    if ty is None:
        return True
    tys = [ty] if isinstance(ty, str) else list(ty) if isinstance(ty, (list, tuple)) else []
    if not tys:
        return True
    if v is None and spec.get("nullable"):
        return True
    for t in tys:
        t = str(t).lower()
        py = _PY.get(t)
        if py is None:
            return True             # unknown type keyword: do not judge
        if isinstance(v, bool) and t in ("integer", "number"):
            continue
        if isinstance(v, py):
            return True
    return False


def schema_error(tc: ToolCall, schemas: dict[str, dict], strict: bool = True) -> SchemaError | None:
    sch = schemas.get(tc.name)
    pos = tc.span[0]
    if sch is None:
        return SchemaError("UNDECLARED_TOOL", pos, f"tool {tc.name!r} is not declared", name=tc.name)
    if not strict:
        return None
    props, req = sch["properties"], sch["required"]
    for k in tc.arguments:
        if k not in props:
            return SchemaError("UNDECLARED_KEY", pos, f"{tc.name}: undeclared argument {k!r}", key=k)
    for k in req:
        if k not in tc.arguments:
            return SchemaError("MISSING_REQUIRED", pos, f"{tc.name}: missing required argument {k!r}", key=k)
    for k, v in tc.arguments.items():
        if not type_ok(v, props.get(k)):
            return SchemaError("TYPE_MISMATCH", pos, f"{tc.name}: argument {k!r} has type {type(v).__name__}",
                               key=k)
    return None
