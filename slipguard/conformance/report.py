"""Judge slipguard's conformance results with workstream C's own rules (diff/analyze_x.judge) and write
conformance/RESULTS.{md,json}.

    python conformance/report.py --suite <C's conformance dir> --cases <cases.jsonl> --out <dir> <results.jsonl ...>

Table D: per bug class (C's 16 classes; C13 = TWO_CALLS), the worst verdict over the class's minimal repros.
Table F: per-class presence over C's fuzz corpus (C's CLASS_RULES), plus HANG / EXCEPTION over every input.
Real inputs (family R): exactness on real clean calls, visibility of real slips, real raw outputs.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


SUITE = _arg("--suite")
sys.path.insert(0, os.path.join(SUITE, "diff"))
sys.path.insert(0, SUITE)
from analyze import CLASS_REPROS, CLASS_RULES  # noqa: E402
from analyze_x import judge, input_kind, retained  # noqa: E402

CLASSES = list(CLASS_REPROS) + [("C13 multiple calls / streaming call merge", ["TWO_CALLS"])]
ORDER = {"pass": 0, "n/a": 0, "unknown": 1, "policy": 2, "defect": 3}
SYM = {"pass": "✓", "policy": "~", "defect": "✗", "unknown": "?", "n/a": "·"}


def main():
    cases = {}
    for line in open(_arg("--cases")):
        c = json.loads(line)
        cases[c["id"]] = c
    files = [a for a in sys.argv[1:] if a.endswith(".jsonl") and a != _arg("--cases")]
    res = {}
    for pat in files:
        for f in sorted(glob.glob(pat)):
            for line in open(f):
                d = json.loads(line)
                res[(d["case"], d["target"])] = d
    targets = sorted({t for _, t in res})
    out = {"targets": targets, "n_results": len(res), "table_D": {}, "table_F": {}, "real": {}, "any_input": {}}
    # ---- Table D (minimal repros)
    rid_of = {cid: c.get("subfamily") for cid, c in cases.items() if c.get("family") == "X"}
    by_rid = {rid: cid for cid, rid in rid_of.items()}
    from worker import dec
    for name, rids in CLASSES:
        row = {}
        for t in targets:
            worst, why = "n/a", []
            for rid in rids:
                cid = by_rid.get(rid)
                rec = res.get((cid, t))
                if rec is None:
                    continue
                c = cases[cid]
                intended = dec(c["intended"]) if c.get("intended") is not None else None
                bucket, verdict = judge(input_kind(c["text"]), rec, intended, rid=rid, text=c["text"])
                if worst == "n/a" or ORDER[verdict] > ORDER[worst]:
                    worst = verdict
                if verdict not in ("pass", "n/a"):
                    why.append(f"{rid}:{rec['outcome']}")
            row[t] = {"verdict": worst, "why": why}
        out["table_D"][name] = row
    # ---- Table F (fuzz presence) + any-input safety
    for key, desc, sel, bad in CLASS_RULES:
        row = {}
        for t in targets:
            n = k = 0
            for cid, c in cases.items():
                rec = res.get((cid, t))
                if rec is None or rec.get("outcome") == "SKIPPED":
                    continue
                try:
                    if not sel(c):
                        continue
                except Exception:  # noqa: BLE001
                    continue
                n += 1
                k += bool(bad(rec.get("outcome"), rec))
            row[t] = [k, n]
        out["table_F"][key] = {"desc": desc, "by_target": row}
    for t in targets:
        recs = [r for (cid, tt), r in res.items() if tt == t]
        out["any_input"][t] = {"n": len(recs), "hang": sum(r.get("outcome") == "HANG" or r.get("status") in ("timeout", "hard_hang") for r in recs),
                               "exception": sum(r.get("status") in ("exception", "crash") for r in recs),
                               "skipped": sum(r.get("outcome") == "SKIPPED" for r in recs),
                               "max_ms": max((r.get("ms") or 0) for r in recs) if recs else None}
    # ---- real inputs (family R)
    for t in targets:
        clean = slips = raw = 0
        clean_exact = slips_visible = raw_visible = raw_calls = raw_lost = 0
        for cid, c in cases.items():
            if c.get("family") != "R":
                continue
            rec = res.get((cid, t))
            if rec is None or rec.get("outcome") == "SKIPPED":
                continue
            sf = c.get("subfamily", "")
            o = rec.get("outcome")
            if sf.startswith("real_clean"):
                clean += 1
                clean_exact += o == "EXACT"
            elif sf.startswith("slip_reassembled"):
                slips += 1
                slips_visible += (o == "LOUD") or (o == "AS_CONTENT" and retained(c["text"], rec))
            elif sf.startswith("raw"):
                raw += 1
                if rec.get("n_calls"):
                    raw_calls += 1          # strictly valid L1 calls returned (the parser returns nothing else)
                elif o == "LOUD" or retained(c["text"], rec):
                    raw_visible += 1
                else:
                    raw_lost += 1
            elif sf.startswith("slip") is False and t == "gg.repair":
                pass
        out["real"][t] = {"clean_exact": [clean_exact, clean], "slips_visible": [slips_visible, slips],
                          "raw": {"n": raw, "loud_or_text_returned": raw_visible, "strict_calls_returned": raw_calls,
                                  "lost": raw_lost}}
        if t == "gg.repair":
            rs = collections.Counter()
            for cid, c in cases.items():
                if c.get("family") == "R" and c.get("subfamily", "").startswith("slip_reassembled"):
                    rec = res.get((cid, t))
                    if rec is not None:
                        rs[rec.get("outcome")] += 1
            out["real"][t]["slip_repair_outcomes"] = dict(rs)
    od = _arg("--out")
    os.makedirs(od, exist_ok=True)
    default = [t for t in targets if t != "gg.repair"]
    out["n_targets"] = {"default": len(default), "opt_in_repair": int("gg.repair" in targets), "total": len(targets)}
    L = ["# slipguard conformance (C's suite, C's judging rules)", "",
         f"{out['n_results']} results; {len(targets)} targets = {len(default)} default targets + "
         f"{int('gg.repair' in targets)} opt-in repair target (gg.repair, informational): {', '.join(targets)}.", "",
         "## Table D: per bug class, worst verdict over the class's minimal repros (✓ pass, ~ policy, ✗ defect)", "",
         "| class | " + " | ".join(targets) + " |", "|---|" + "---|" * len(targets)]
    for name, row in out["table_D"].items():
        L.append(f"| {name} | " + " | ".join(SYM[row[t]["verdict"]] + (" " + ",".join(row[t]["why"]) if row[t]["why"] else "")
                                          for t in targets) + " |")
    L += ["", "## Table F: per-class presence over the fuzz corpus (k/n inputs where the defect shows)", "",
          "| class | " + " | ".join(targets) + " |", "|---|" + "---|" * len(targets)]
    for key, v in out["table_F"].items():
        L.append(f"| {key} | " + " | ".join(f"{v['by_target'][t][0]}/{v['by_target'][t][1]}" for t in targets) + " |")
    L += ["", "## Safety on every input", "", "| target | inputs | hang | exception | skipped (stream > 3,000 chars) | max ms |",
          "|---|---|---|---|---|---|"]
    for t, v in out["any_input"].items():
        L.append(f"| {t} | {v['n']} | {v['hang']} | {v['exception']} | {v['skipped']} | {v['max_ms']} |")
    L += ["", "## Real inputs (family R)", "",
          "| target | real clean calls exact | real slips visible | real raw outputs: loud / text returned | strict calls returned | lost |",
          "|---|---|---|---|---|---|"]
    for t, v in out["real"].items():
        rw = v["raw"]
        L.append(f"| {t} | {v['clean_exact'][0]}/{v['clean_exact'][1]} | {v['slips_visible'][0]}/{v['slips_visible'][1]} | "
                 f"{rw['loud_or_text_returned']}/{rw['n']} | {rw['strict_calls_returned']} | {rw['lost']} |")
    if "gg.repair" in out["real"]:
        L += ["", f"gg.repair (opt-in text repair) on the 1,610 real slips: {out['real']['gg.repair'].get('slip_repair_outcomes')}"
              " (EXACT = repaired to the intended call; LOUD = left loud; any other outcome would be a wrong repair)."]
    open(os.path.join(od, "RESULTS.md"), "w").write("\n".join(L) + "\n")
    json.dump(out, open(os.path.join(od, "RESULTS.json"), "w"), indent=1, ensure_ascii=False)
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
