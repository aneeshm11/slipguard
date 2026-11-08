"""Summarize benchmarks/perf.py outputs into results/PERF.{md,json}: wall-time and log-log slope side by side,
slipguard vs each runtime's built-in Gemma 4 parser on the same inputs, plus a figure spec for the paper.

    python benchmarks/summarize.py results/perf_*.json
"""
from __future__ import annotations

import json
import math
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")


def fit_slope(points):
    """Least-squares slope of log(ms) on log(n) over points with ms >= 2 (timer noise below)."""
    pts = [(math.log(n), math.log(ms)) for n, ms in points if ms >= 2]
    if len(pts) < 2:
        return None
    mx = sum(x for x, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    return round(sum((x - mx) * (y - my) for x, y in pts) / den, 2) if den else None


def main():
    runs = [json.load(open(p)) for p in sys.argv[1:]]
    table = []
    for r in runs:
        ver = r.get("vllm") or "none"
        by = {}
        for row in r["rows"]:
            by.setdefault((row["mode"], row["family"], row["target"]), []).append(row)
        for (mode, fam, tgt), rows in sorted(by.items()):
            ok = [(x["n"], x["ms"]) for x in rows if x["status"] == "ok"]
            timeouts = [x["n"] for x in rows if x["status"] == "timeout"]
            largest = max(ok) if ok else None
            table.append({"vllm_env": ver, "mode": mode, "family": fam, "target": tgt,
                          "who": "slipguard" if tgt.startswith("gg.") else "built-in",
                          "points": ok, "slope": fit_slope(ok), "largest_ok": largest,
                          "first_timeout_n": min(timeouts) if timeouts else None, "timeout_s": r["timeout_s"]})
    os.makedirs(OUT, exist_ok=True)
    json.dump({"rows": table}, open(os.path.join(OUT, "PERF.json"), "w"), indent=1)
    L = ["# Parser timing: slipguard vs built-in Gemma 4 parsers (same inputs, same process, one CPU core)", "",
         "Wall time of the largest size each target finished, and the least-squares log-log slope over all finished",
         "sizes (1 = linear, 2 = quadratic). Inputs: workstream C's scaling families (diff/scaling.py). Streaming =",
         "per-token deltas from the Gemma 4 tokenizer; built-in and plugin streaming include the server's own per-step",
         "string accumulation (O(n) per step in every runtime); gg.stream is the parser alone.", "",
         "| vLLM env | mode | family | target | sizes (n: ms) | slope | first timeout |", "|---|---|---|---|---|---|---|"]
    for t in table:
        pts = ", ".join(f"{n}: {ms:.0f}" if ms >= 10 else f"{n}: {ms:.1f}" for n, ms in t["points"])
        L.append(f"| {t['vllm_env']} | {t['mode']} | {t['family']} | `{t['target']}` | {pts} | {t['slope']} | "
                 f"{t['first_timeout_n'] or '-'} |")
    L += ["", "## Figure spec (paper)", "",
          "* Two panels, log-log axes: (a) `many_string_keys` (x = number of arguments, 125 to 16,000), (b) `long_string`",
          "  (x = string length in characters, 1e4 to 4e6); y = parse wall time in ms (non-streaming).",
          "* Series: vLLM 0.19.1 / 0.31.0 / 0.33.0 built-in `gemma4` server path (one colour family, three shades);",
          "  slipguard `parse_completion` and the slipguard plugin through vLLM 0.33's server objects (second colour).",
          "* Reference lines: slope 1 and slope 2 through the first slipguard / first vLLM 0.33 point (dashed, grey).",
          "* Timeouts drawn as an open marker at the timeout value with an upward arrow; annotate the vLLM 0.33",
          "  4,000-argument point with its wall time.",
          "* Inset or third panel: streaming (`many_string_keys`, per-token deltas), same series; caption notes that",
          "  server-side per-step string accumulation is included for the runtime paths.",
          "* Data: results/PERF.json (`points` per series)."]
    open(os.path.join(OUT, "PERF.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L[:60]))


if __name__ == "__main__":
    main()
