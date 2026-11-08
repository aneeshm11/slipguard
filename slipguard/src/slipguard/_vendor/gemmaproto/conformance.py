"""Outcome taxonomy for differential testing (pure Python; imported by the workers in every env).

Given what a parser returned for a case and the case's INTENDED calls (when known), classify the behaviour:

  EXACT           calls == intended (names, count, order, keys, type-exact values)
  TYPE_DIFF       same structure, a scalar has a different type/spelling ("42" vs 42, "1e+20" vs 1e20)
  DROPPED_ARG     a call lacks an intended key (and nothing else is wrong)               -> silent loss
  EMPTY_ARGS      arguments == {} although intended non-empty                           -> silent loss
  CORRUPT_VALUE   same keys, some value differs (absorbed text, truncated string, ...)  -> silent corruption
  EXTRA_KEY       keys not intended appear (junk keys built from swallowed text)        -> silent corruption
  CALL_COUNT      number of calls differs                                                -> silent
  WRONG_NAME      function name differs                                                  -> silent
  AS_CONTENT      no call returned; the text is surfaced as content                     -> visible degradation
  NO_OUTPUT       no call and no content                                                 -> silent loss
  LOUD            the parser raised / returned an explicit error                         -> fail-loud
  HANG            per-case timeout fired                                                 -> availability bug
  CRASH           worker process died (assigned by the supervisor)

Without intended calls the outcome is NO_INTENT and only the fingerprint is compared across parsers.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .serializer import values_equal

SILENT = {"DROPPED_ARG", "EMPTY_ARGS", "CORRUPT_VALUE", "EXTRA_KEY", "CALL_COUNT", "WRONG_NAME", "NO_OUTPUT"}


def typed(v: Any) -> Any:
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, int):
        return {"i": str(v)}
    if isinstance(v, float):
        return {"f": repr(v)}
    if isinstance(v, dict):
        return {str(k): typed(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [typed(x) for x in v]
    return {"repr": repr(v)}


def fingerprint(calls: list) -> str:
    norm = [{"name": c.get("name"), "arguments": typed(c.get("arguments"))} for c in calls or []]
    return hashlib.sha1(json.dumps(norm, sort_keys=True, ensure_ascii=False).encode("utf-8", "surrogatepass")).hexdigest()[:16]


def _loose(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return repr(v).lower()
        f = float(v)
        return repr(int(f)) if f.is_integer() and abs(f) < 1e16 else repr(f)
    if isinstance(v, dict):
        return {str(k): _loose(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_loose(x) for x in v]
    return repr(v)


def _loose_scalar_str(v: Any) -> Any:
    """'42' -> '42', 42 -> '42', '1e+20' -> '1e+20' parsed as float when possible."""
    lv = _loose(v)
    if isinstance(lv, str):
        try:
            f = float(lv)
            return repr(int(f)) if f.is_integer() and abs(f) < 1e16 else repr(f)
        except ValueError:
            return lv
    return lv


def _loose_eq(a: Any, b: Any) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_loose_eq(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_loose_eq(x, y) for x, y in zip(a, b))
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return False
    return _loose_scalar_str(a) == _loose_scalar_str(b)


def classify(out: dict, intended: list | None) -> str:
    st = out.get("status")
    if st == "timeout":
        return "HANG"
    if st == "crash":
        return "CRASH"
    if st == "exception" or out.get("loud"):
        return "LOUD"
    calls = out.get("calls") or []
    if intended is None:
        return "NO_INTENT"
    if not calls:
        if intended == []:
            return "EXACT"
        return "AS_CONTENT" if (out.get("content") or "").strip() else "NO_OUTPUT"
    if len(calls) != len(intended):
        return "CALL_COUNT"
    worst = "EXACT"
    rank = ["EXACT", "TYPE_DIFF", "DROPPED_ARG", "EXTRA_KEY", "CORRUPT_VALUE", "EMPTY_ARGS", "WRONG_NAME"]
    for got, want in zip(calls, intended):
        ga, wa = got.get("arguments"), want.get("arguments")
        if got.get("name") != want.get("name"):
            c = "WRONG_NAME"
        elif not isinstance(ga, dict):
            c = "CORRUPT_VALUE"
        elif values_equal(ga, wa):
            c = "EXACT"
        elif ga == {} and wa:
            c = "EMPTY_ARGS"
        elif _loose_eq(ga, wa):
            c = "TYPE_DIFF"
        elif set(ga) < set(wa) and all(values_equal(ga[k], wa[k]) or _loose_eq(ga[k], wa[k]) for k in ga):
            c = "DROPPED_ARG"
        elif set(ga) - set(wa):
            c = "EXTRA_KEY"
        else:
            c = "CORRUPT_VALUE" if set(ga) == set(wa) else "DROPPED_ARG"
        if rank.index(c) > rank.index(worst):
            worst = c
    return worst


def compact_calls(calls: list, limit: int = 3000) -> list:
    """Small, JSON-safe summary of returned calls (full values only when short)."""
    out = []
    for c in calls or []:
        a = c.get("arguments")
        s = json.dumps(typed(a), ensure_ascii=False)
        item = {"name": c.get("name"), "keys": list(a.keys()) if isinstance(a, dict) else None,
                "lens": {k: len(v) for k, v in a.items() if isinstance(v, str)} if isinstance(a, dict) else None}
        if len(s) <= limit:
            item["arguments_typed"] = typed(a)
        out.append(item)
    return out
