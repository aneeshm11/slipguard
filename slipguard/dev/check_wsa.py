"""Dev check (CPU): the SHIPPED weight-audit code reproduces F's frozen sweep reports from F's frozen records.

    python dev/check_wsa.py <F's wsa out dir> [--render <PNC dir> <tokenizer dir> [N]]

1. For every checkpoint of sweep_report.json (reference 31b_bf16) and sweep_report_e4bref.json (reference e4b_bf16):
   slipguard.weights.summarize / compare / flag on F's records == the report's fields: every summary key (floats to
   1e-9), the median-deficit POINT estimate, FLAG and SEVERE (the reference's own verdict is undefined in the report).
   The sweep records predate the `n_prior_bad` record field (the sweep script joined it from the items file); it is
   joined here from the SHIPPED pack. Bootstrap CIs are compared with a tolerance and reported (the sweep script drew
   all checkpoints from one RNG stream; compare() reseeds per comparison).
2. --render: the shipped renderer reproduces the shipped pack's prompt_tokens for the first N items of each pack.
Prints one JSON summary.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))


def close(a, b):
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def main():
    from slipguard import weights as W
    out_dir = sys.argv[1]
    res = {"reports": {}, "mismatches": []}
    for rep_name in ("sweep_report.json", "sweep_report_e4bref.json"):
        rep = json.load(open(os.path.join(out_dir, rep_name)))
        items = {(it["episode_id"], it["turn_index"]): it for it in
                 (json.loads(l) for l in gzip.open(W.pack_path("audit16k"), "rt"))}

        def load(name):
            recs = W.load_records(os.path.join(out_dir, f"audit_sweep_{name}.records.jsonl"))
            for r in recs:
                r.setdefault("n_prior_bad", items[(r["episode_id"], r["turn_index"])]["n_prior_bad"])
            return recs
        ref = load(rep["reference"])
        n = 0
        for ck, want in rep["checkpoints"].items():
            recs = load(ck)
            s = W.summarize(recs)
            p = W.compare(recs, ref)
            fl, sev = W.flag(s, p)
            for k, v in s.items():
                if k in want and not close(v, want[k]):
                    res["mismatches"].append([rep_name, ck, k, v, want[k]])
            pv = want.get("paired_vs_ref") or {}
            if pv:
                if p["n"] != pv["n"] or not close(p["median_deficit"][0], pv["median_deficit"][0]):
                    res["mismatches"].append([rep_name, ck, "paired.n/point", [p["n"], p["median_deficit"][0]],
                                              [pv["n"], pv["median_deficit"][0]]])
                res["max_ci_bound_diff_nats"] = max(res.get("max_ci_bound_diff_nats", 0.0),
                                                    *(abs(a - b) for a, b in zip(p["median_deficit"][1:], pv["median_deficit"][1:])))
            if ck != rep["reference"] and (want.get("FLAG") != fl or want.get("SEVERE") != sev):
                res["mismatches"].append([rep_name, ck, "FLAG/SEVERE", [fl, sev], [want.get("FLAG"), want.get("SEVERE")]])
            n += 1
        res["reports"][rep_name] = {"reference": rep["reference"], "checkpoints": n}
    if "--render" in sys.argv:
        i = sys.argv.index("--render")
        pnc, tokdir = sys.argv[i + 1], sys.argv[i + 2]
        lim = int(sys.argv[i + 3]) if len(sys.argv) > i + 3 else 20
        import importlib
        from slipguard._frozen import load_wsa
        load_wsa()
        Rn = importlib.import_module("slipguard._wsaudit.render").PNCRenderer(pnc, tokdir)
        for pk in W.PACKS:
            items = [json.loads(l) for l in gzip.open(W.pack_path(pk), "rt")][:lim]
            ok = 0
            for it in items:
                t = Rn.turn(it["episode_id"], it["turn_index"])
                ok += len(Rn.encode(Rn.render(t["request"]["messages"], it["schema"]))) == it["prompt_tokens"]
            res[f"render_{pk}"] = [ok, len(items)]
    res["ok"] = not res["mismatches"] and all(v[0] == v[1] for k, v in res.items() if k.startswith("render_"))
    print(json.dumps(res, indent=1, default=str))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
