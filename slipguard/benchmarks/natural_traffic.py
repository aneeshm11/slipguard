"""Machine-sourced natural-traffic numbers -> results/natural_traffic.json (every value regenerable; public inputs).

    python benchmarks/natural_traffic.py --pnc <PNC dir> --realistic <dir of realistic.py outputs> \
        [--perf-realistic results/PERF_REALISTIC.json] --out results/natural_traffic.json

Inputs: the public PNC corpus (every model turn: raw generation, the calls vLLM 0.19.1 delivered, the tool schema)
and, for the per-version delivered-call counts and timings, the per-turn outputs of benchmarks/realistic.py.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    from slipguard import __version__
    from slipguard._frozen import load_e
    from slipguard.parse import extract
    from slipguard.parse.reasoning import split_reasoning
    pnc, rdir, out = _arg("--pnc"), _arg("--realistic"), _arg("--out")
    qr = load_e().quarantine_renderer
    tools = {s: json.load(open(os.path.join(pnc, "contexts", f"P-swebench-31b-{s}-v1", "manifest.json")))["tools"]
             for s in ("S1", "S2")}
    sch = {s: qr.tool_schemas(t) for s, t in tools.items()}
    n_turns = logged_calls = 0
    refused_turns = refused_calls = 0
    by_code = collections.Counter()
    e_flagged = kwarg_dropped = 0
    rep = collections.Counter()
    for f in sorted(glob.glob(os.path.join(pnc, "episodes", "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            n_turns += 1
            raw = d.get("raw_completion") or ""
            logged = ((d.get("response") or {}).get("message") or {}).get("tool_calls") or []
            logged_calls += len(logged)
            text = raw if raw.startswith("<|channel>") or "<channel|>" not in raw else "<|channel>thought\n" + raw
            _, content = split_reasoning(text)
            ex = extract(content or "")
            if len(ex.calls) >= len(logged):
                continue
            refused_turns += 1
            refused_calls += len(logged) - len(ex.calls)
            code = ex.errors[0].code if ex.errors else "none"
            by_code[code] += 1
            la = {}
            for tc in logged:
                try:
                    la.update(json.loads(tc["function"]["arguments"]))
                except (ValueError, TypeError):
                    pass
            if any(not qr.classify_args(tc["function"]["name"], json.loads(tc["function"]["arguments"]),
                                        sch[d["schema"]])["ok"] for tc in logged):
                e_flagged += 1
            if code == "EXPECTED_COLON" and ex.errors:
                seg = (content or "")[max(0, ex.errors[0].pos - 60):ex.errors[0].pos]
                m = re.search(r"([A-Za-z_]\w*)\s*=\s*([^,{}]*)$", seg)
                if m and m.group(1) not in la:
                    kwarg_dropped += 1
            er = extract(content or "", tools[d["schema"]], repair=True)
            if er.repairs:
                rep["repaired"] += 1
                rep["repaired_" + (er.repairs[0].get("rule") or "unknown")] += 1
            else:
                rep["loud"] += 1
    per_version = {}
    for f in sorted(glob.glob(os.path.join(rdir, "*__*.jsonl"))):
        env, impl = os.path.basename(f)[:-6].rsplit("__", 1)
        rows = [json.loads(x) for x in open(f)]
        per_version[f"{env}|{impl}"] = {"turns": len(rows), "calls_delivered": sum(r.get("n_calls", 0) for r in rows),
                                        "calls_logged_by_vllm_0.19.1": sum(r["logged_calls"] for r in rows),
                                        "turns_with_more_calls_than_logged": sum(r.get("n_calls", 0) > r["logged_calls"] for r in rows),
                                        "turns_with_fewer_calls_than_logged": sum(r.get("n_calls", 0) < r["logged_calls"] for r in rows)}
    perf = {}
    pr = _arg("--perf-realistic")
    if pr and os.path.exists(pr):
        perf = json.load(open(pr))
    res = {
        "source": "public PNC corpus (every model turn); slipguard " + __version__,
        "turns": n_turns, "calls_delivered_by_vllm_0.19.1": logged_calls,
        "strict_refusals": {"turns": refused_turns, "calls": refused_calls,
                            "turns_pct": round(100 * refused_turns / n_turns, 3),
                            "first_error_code": dict(by_code.most_common()),
                            "turns_with_a_call_flagged_malformed_by_the_quarantine_criterion": e_flagged,
                            "turns_with_key_eq_value_drift_dropped_by_vllm": kwarg_dropped},
        "repair_mode_on_refused_turns": {"repaired": rep["repaired"], "repaired_kwarg": rep["repaired_kwarg"],
                                         "repaired_closer": rep["repaired_closer"], "loud": rep["loud"]},
        "per_version_call_counts": per_version,
        "timing": perf,
    }
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("timing", "per_version_call_counts")}, indent=1))


if __name__ == "__main__":
    main()
