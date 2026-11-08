#!/usr/bin/env python3
"""Build src/slipguard/data/conformance_public.jsonl from workstream C's minimal repros (dev-time tool).

Only classes whose inputs are NOT disclosure-sensitive are copied (slips, opener/key drift, header drift, truncation,
delimiter errors, type fidelity, valid-L1 coverage, multiple calls). The control-token-in-string (C6), hang (C7),
quadratic (C8) and deep-nesting (C9) classes are checked by `slipguard verify` with generic, generated inputs, and
with C's exact repros only in tests/private/ (excluded from the public tree).
usage: python tools/build_public_cases.py <C's repros.jsonl>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "src", "slipguard", "data", "conformance_public.jsonl")
CLASS = {
    "E1": ["ABSORB_BACKTICK", "ABSORB_DQUOTE", "ABSORB_FIRST_ARG", "LAST_ARG_CLOSER"],
    "E2": ["KEY_RESTART"],
    "E3": ["JSON_STRING_VALUE", "OPENER_EQUALS_JSON", "OPENER_TRIPLE_QUOTE", "OPENER_JSON_SPACE", "OPENER_BARE"],
    "E4": ["JSON_QUOTED_KEY", "KEY_DRIFT_HALF_QUOTE"],
    "E5": ["HEADER_SPACE", "HEADER_NO_PREFIX", "PAREN_OPENER", "UNCLOSED_CALL"],
    "C2": ["TRUNCATED_CALL"], "C4": ["DOUBLED_DELIMITER"], "C5": ["STRAY_DELIM_AFTER_NUMBER"],
    "C10": ["NULL_FOR_STRING_PARAM", "FLOAT_INTEGRAL", "FLOAT_EXPONENT", "STRING_LOOKS_NUMERIC", "NESTED_OBJECT"],
    "C11": ["PY_LITERAL"], "C12": ["DOTTED_NAME", "HYPHEN_NAME", "WHITESPACE_L1", "SPECIAL_KEY"], "C13": ["TWO_CALLS"],
}
cls_of = {rid: c for c, rids in CLASS.items() for rid in rids}
n = 0
with open(OUT, "w") as fo:
    for line in open(sys.argv[1]):
        d = json.loads(line)
        rid = d["subfamily"]
        if rid not in cls_of:
            continue
        fo.write(json.dumps({"id": rid, "class": cls_of[rid], "text": d["text"], "valid": bool(d["ref"]["valid"]),
                             "intended": d["intended"]}, ensure_ascii=False) + "\n")
        n += 1
print(f"{n} public cases written")
