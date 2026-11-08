"""Turn every model turn of the public PNC corpus into a conformance case (C's case format).

    python conformance/build_pnc_cases.py <PNC dir> <out cases.jsonl>

Per turn: text = the raw generation (special tokens kept; turns whose prompt ended inside the thought get the
'<|channel>thought\\n' prefix, as in the conformance harness), tools = the episode's tool schema, ref.valid = the
executable specification accepts the whole completion.
  valid turns      intended = the specification's parse (the calls the model emitted).
  ill-formed turns intended = RETRY-DERIVED GOLD when it exists, else None (no intent). The malformed call is the
                   call holding the first protocol error; intent is known only when it is the turn's last call and a
                   later turn of the same episode (within the next 3) restates it: the first CLEAN call to the SAME
                   tool (strictly valid, and not flagged by the frozen quarantine criterion, i.e. no absorbed
                   look-alike + key text) whose every key and every leaf value (strings verbatim, numbers / booleans
                   as text) occurs inside the malformed call's text, and whose canonical rendering is no more than 8
                   characters shorter and no more than 24 characters longer than that text (so the malformed call
                   carries no extra argument the retry dropped). intended = the turn's strictly valid calls before
                   the malformed one + that restated call.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from slipguard._vendor import gemmaproto as G  # noqa: E402
from slipguard.parse import extract  # noqa: E402
from slipguard.parse.reasoning import split_reasoning  # noqa: E402


def enc(v):
    import math
    if isinstance(v, float):
        if math.isnan(v):
            return {"__float__": "nan"}
        if math.isinf(v):
            return {"__float__": "inf" if v > 0 else "-inf"}
        if v == 0.0 and math.copysign(1.0, v) < 0:
            return {"__float__": "-0.0"}
        return v
    if isinstance(v, dict):
        return {str(k): enc(x) for k, x in v.items()}
    if isinstance(v, list):
        return [enc(x) for x in v]
    return v


def _leaves(v):
    """keys and leaf values of a call's arguments, as the text that must occur in the malformed call."""
    if isinstance(v, dict):
        for k, x in v.items():
            yield str(k)
            yield from _leaves(x)
    elif isinstance(v, list):
        for x in v:
            yield from _leaves(x)
    elif isinstance(v, bool):
        yield "true" if v else "false"
    elif v is None:
        yield "null"
    else:
        yield str(v)


def _canon(c):
    body = ",".join(f"{k}:{G.render_value(v, escape_keys=False)}" for k, v in c.arguments.items())
    return f"{G.TOOL_CALL_OPEN}call:{c.name}{{{body}}}<tool_call|>"


def _malformed_call(text):
    """(strictly valid calls before the first error, malformed call's name, its text, is_last) or None."""
    _, content = split_reasoning(text)
    content = content or ""
    ex = extract(content)
    if not ex.errors:
        return None
    pos = ex.errors[0].pos
    k = content.rfind(G.TOOL_CALL_OPEN, 0, pos + 1)
    k = max(k, 0)
    region = content[k:]
    m = re.search(r"call[:,\s]+([\w\-\.]+)", region)
    last = content.find(G.TOOL_CALL_OPEN, k + 1) < 0
    return ex.calls, (m.group(1) if m else None), region, last


def main():
    pnc, out = sys.argv[1], sys.argv[2]
    tools = {s: json.load(open(os.path.join(pnc, "contexts", f"P-swebench-31b-{s}-v1", "manifest.json")))["tools"]
             for s in ("S1", "S2")}
    from slipguard._frozen import load_e
    qr = load_e().quarantine_renderer
    sch = {s: qr.tool_schemas(t) for s, t in tools.items()}
    n = {"valid": 0, "ill_intent_known": 0, "ill_no_intent": 0}
    with open(out, "w") as fo:
        for f in sorted(glob.glob(os.path.join(pnc, "episodes", "*.jsonl"))):
            turns = [json.loads(x) for x in open(f, encoding="utf-8")]
            turns.sort(key=lambda d: d["turn_index"])
            texts, parsed = [], []
            for d in turns:
                raw = d.get("raw_completion") or ""
                t = raw if raw.startswith("<|channel>") or "<channel|>" not in raw else "<|channel>thought\n" + raw
                texts.append(t)
                try:
                    parsed.append(G.parse_completion(t))
                except G.ParseError:
                    parsed.append(None)
            for i, d in enumerate(turns):
                t = texts[i]
                case = {"id": f"PNC-{d['episode_id']}#{d['turn_index']}", "family": "PNC", "text": t,
                        "tools": tools[d["schema"]], "in_thought": False, "meta": {"schema": d["schema"]}}
                pc = parsed[i]
                if pc is not None:
                    case.update(subfamily="valid" if pc.calls else "valid_no_call", ref={"valid": True},
                                intended=enc([{"name": c.name, "arguments": c.arguments} for c in pc.calls]))
                    n["valid" if pc.calls else "valid_no_call"] = n.get("valid" if pc.calls else "valid_no_call", 0) + 1
                else:
                    mc = _malformed_call(t)
                    gold, j = None, None
                    if mc is not None and mc[3] and mc[1]:
                        prefix, name, region, _ = mc
                        for j in range(i + 1, min(i + 4, len(turns))):
                            pj = parsed[j]
                            c = next((c for c in (pj.calls if pj else []) if c.name == name), None)
                            if c is not None and all(x in region for x in _leaves(c.arguments)) \
                                    and -24 <= len(region) - len(_canon(c)) <= 8 \
                                    and qr.classify_args(c.name, c.arguments, sch[d["schema"]])["ok"]:
                                gold = c
                                break
                    if gold is not None:
                        calls = [{"name": c.name, "arguments": c.arguments} for c in prefix]
                        calls.append({"name": gold.name, "arguments": gold.arguments})
                        case.update(subfamily="ill_intent_known", ref={"valid": False}, intended=enc(calls),
                                    meta={**case["meta"], "gold_from_turn": turns[j]["turn_index"]})
                        n["ill_intent_known"] += 1
                    else:
                        why = "no_error_located" if mc is None else "not_last_call" if not mc[3] else "no_restating_retry"
                        case.update(subfamily="ill_no_intent", ref={"valid": False}, intended=None,
                                    meta={**case["meta"], "no_intent": why})
                        n["ill_no_intent"] += 1
                        n["no_intent_" + why] = n.get("no_intent_" + why, 0) + 1
                fo.write(json.dumps(case, ensure_ascii=False) + "\n")
    print(json.dumps(n))


if __name__ == "__main__":
    main()
