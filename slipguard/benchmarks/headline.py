"""Headline table (README / paper): wall time at fixed sizes and log-log slope, built-in vs slipguard, per vLLM.

    python benchmarks/headline.py results/PERF.json
"""
from __future__ import annotations

import json
import sys

POINTS = [("non-streaming", "many_int_keys", 4000, "arguments"), ("non-streaming", "many_string_keys", 4000, "arguments"),
          ("non-streaming", "code_with_commas", 16000, "code lines"), ("non-streaming", "long_string", 4000000, "chars"),
          ("streaming", "many_string_keys", 2000, "arguments"), ("streaming", "code_with_commas", 6400, "code lines")]


def fmt_ms(ms):
    if ms is None:
        return "-"
    return f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms:.0f} ms" if ms >= 10 else f"{ms:.1f} ms"


def main():
    rows = json.load(open(sys.argv[1]))["rows"]
    by = {(r["vllm_env"], r["mode"], r["family"], r["target"]): r for r in rows}
    envs = sorted({r["vllm_env"] for r in rows if r["vllm_env"] != "none"})
    L = ["| input | vLLM | built-in parser | slipguard plugin (same server objects) | slipguard API |", "|---|---|---|---|---|"]
    J = []
    for mode, fam, n, unit in POINTS:
        for v in envs:
            tgt_b = f"{v}.server" if mode == "non-streaming" else f"{v}.stream"
            tgt_p = f"gg.{v}.server" if mode == "non-streaming" else f"gg.{v}.stream"
            tgt_a = "gg.completion" if mode == "non-streaming" else "gg.stream"

            def raw(t):
                r = by.get((v, mode, fam, t))
                if r is None:
                    return None
                ms = dict(map(tuple, r["points"])).get(n)
                to = ms is None and r["first_timeout_n"] is not None and r["first_timeout_n"] <= n
                return {"target": t, "ms": ms, "timeout": bool(to), "timeout_s": r["timeout_s"] if to else None,
                        "slope": r["slope"]}

            def cell(t):
                x = raw(t)
                if x is None:
                    return "-"
                if x["timeout"]:
                    return f"> {x['timeout_s']:.0f} s (timeout), slope {x['slope']}"
                return f"{fmt_ms(x['ms'])}, slope {x['slope']}"
            J.append({"mode": mode, "family": fam, "n": n, "unit": unit, "vllm": v.replace("vllm0", "0."),
                      "builtin": raw(tgt_b), "slipguard_plugin": raw(tgt_p), "slipguard_api": raw(tgt_a)})
            L.append(f"| {fam} ({mode}), {n:,} {unit} | {v.replace('vllm0', '0.')} | {cell(tgt_b)} | {cell(tgt_p)} | {cell(tgt_a)} |")
    print("\n".join(L))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
            json.dump({"source": "benchmarks/run_perf.sh -> results/PERF.json (same inputs, same process, one core)",
                       "rows": J}, f, indent=1)


if __name__ == "__main__":
    main()
