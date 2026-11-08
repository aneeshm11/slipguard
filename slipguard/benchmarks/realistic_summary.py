"""Summarize benchmarks/realistic.py outputs into results/PERF_REALISTIC.{md,json}.

    python benchmarks/realistic_summary.py <dir with <env>__<impl>.jsonl files>
"""
from __future__ import annotations

import glob
import json
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
VER = {"env_gemma": "0.19.1", "env_vllm31": "0.31.0", "env_vllm31_vllm-0.32.0": "0.32.0", "env_vllm31_vllm-0.33.0": "0.33.0"}


def q(a, p):
    if not a:
        return None
    a = sorted(a)
    return a[min(len(a) - 1, int(round(p * (len(a) - 1))))]


def main():
    d = sys.argv[1]
    res = {}
    for f in sorted(glob.glob(os.path.join(d, "*__*.jsonl"))):
        env, impl = os.path.basename(f)[:-6].rsplit("__", 1)
        rows = [json.loads(l) for l in open(f)]
        ok = [r for r in rows if r.get("status") == "ok"]
        ns = [r["ns_ms"] for r in ok]
        st = [r["st_ms"] for r in ok]
        stmax = [r["st_max_ms"] for r in ok]
        llm_ms = sum((r.get("llm_s") or 0) * 1000 for r in ok)
        tok_ms = sum((r.get("gen_tokens") or 0) * 30 for r in ok)
        n = len(ok)
        res[(env, impl)] = {
            "vllm": VER.get(env, env), "impl": impl, "turns": len(rows), "ok": n,
            "timeouts": sum(r.get("status") == "timeout" for r in rows),
            "exceptions": sum(str(r.get("status", "")).startswith("exception") for r in rows),
            "calls_delivered": sum(r.get("n_calls", 0) for r in ok), "calls_logged": sum(r["logged_calls"] for r in ok),
            "ns_total_ms_per_1000": round(sum(ns) / n * 1000, 1) if n else None,
            "ns_p50_ms": q(ns, .5), "ns_p99_ms": q(ns, .99), "ns_max_ms": max(ns) if ns else None,
            "st_total_ms_per_1000": round(sum(st) / n * 1000, 1) if n else None,
            "st_p50_ms": q(st, .5), "st_p99_ms": q(st, .99), "st_max_ms": max(st) if st else None,
            "worst_stall_ms": max(max(ns or [0]), max(stmax or [0])),
            "turns_stall_ge_100ms": sum(max(r["ns_ms"], r["st_max_ms"]) >= 100 for r in ok),
            "turns_stall_ge_1s": sum(max(r["ns_ms"], r["st_max_ms"]) >= 1000 for r in ok),
            "ns_pct_of_llm_time": round(100 * sum(ns) / llm_ms, 5) if llm_ms else None,
            "st_pct_of_llm_time": round(100 * sum(st) / llm_ms, 5) if llm_ms else None,
            "ns_pct_of_tokens_x30ms": round(100 * sum(ns) / tok_ms, 5) if tok_ms else None,
            "st_pct_of_tokens_x30ms": round(100 * sum(st) / tok_ms, 5) if tok_ms else None,
        }
        # tail drivers: the 1% slowest turns (streaming total) and what their calls looked like
        tail = sorted(ok, key=lambda r: -r["st_ms"])[:max(1, n // 100)]
        calls = [c for r in tail for c in r["calls"]]
        res[(env, impl)]["tail_1pct"] = {
            "turns": len(tail), "chars_p50": q([r["chars"] for r in tail], .5), "chars_max": max(r["chars"] for r in tail),
            "tokens_p50": q([r["tokens"] for r in tail], .5),
            "call_arg_chars_p50": q([c["chars"] for c in calls], .5), "call_arg_chars_max": max((c["chars"] for c in calls), default=0),
            "max_string_value_p50": q([c["max_value"] for c in calls], .5),
            "tools": {t: sum(c["name"] == t for c in calls) for t in sorted({c["name"] for c in calls if c["name"]})},
            "all_turns_chars_p50": q([r["chars"] for r in ok], .5)}
    os.makedirs(OUT, exist_ok=True)
    json.dump({f"{k[0]}|{k[1]}": v for k, v in res.items()}, open(os.path.join(OUT, "PERF_REALISTIC.json"), "w"), indent=1)
    keys = sorted(res, key=lambda k: (res[k]["vllm"], k[1]))

    def f(x, nd=2):
        return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))
    L = ["# Parser cost on realistic agent traffic (PNC corpus: every model turn of the natural Gemma 4 trajectories)", "",
         "One process per (vLLM version, parser), each pinned to its own CPU core; built-in = the runtime's gemma4 reasoning",
         "+ tool parsers, slipguard = the plugin, both inside that runtime's own server-path objects; token ids and",
         "per-token deltas are computed outside the timers. Generation time = the turn's logged LLM wall time.", "",
         "| vLLM | parser | turns | non-streaming per 1,000 turns | p50 / p99 / max per turn | streaming per 1,000 turns | p50 / p99 / max per turn | worst stall | turns with a stall >= 100 ms / >= 1 s | parse time as % of generation time (non-stream / stream) | calls delivered / logged |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in keys:
        r = res[k]
        L.append(f"| {r['vllm']} | {r['impl']} | {r['ok']}/{r['turns']} | {f(r['ns_total_ms_per_1000'], 0)} ms | "
                 f"{f(r['ns_p50_ms'])} / {f(r['ns_p99_ms'])} / {f(r['ns_max_ms'], 1)} ms | {f(r['st_total_ms_per_1000'], 0)} ms | "
                 f"{f(r['st_p50_ms'])} / {f(r['st_p99_ms'])} / {f(r['st_max_ms'], 1)} ms | {f(r['worst_stall_ms'], 1)} ms | "
                 f"{r['turns_stall_ge_100ms']} / {r['turns_stall_ge_1s']} | {f(r['ns_pct_of_llm_time'], 4)}% / "
                 f"{f(r['st_pct_of_llm_time'], 4)}% | {r['calls_delivered']} / {r['calls_logged']} |")
    L += ["", "Tail drivers (the 1% slowest turns by streaming parse time):", ""]
    for k in keys:
        t = res[k]["tail_1pct"]
        L.append(f"* vLLM {res[k]['vllm']} {k[1]}: {t['turns']} turns; output chars p50 {t['chars_p50']} (all turns: "
                 f"{t['all_turns_chars_p50']}), max {t['chars_max']}; tokens p50 {t['tokens_p50']}; call argument JSON chars "
                 f"p50 {t['call_arg_chars_p50']}, max {t['call_arg_chars_max']}; tools {t['tools']}")
    open(os.path.join(OUT, "PERF_REALISTIC.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
