"""Parser timing: slipguard vs the runtime's built-in Gemma 4 parser on the SAME inputs, in the same process.

    <env python> benchmarks/perf.py OUT.json --suite <C's conformance dir> --tokenizer <Gemma 4 dir> [--timeout 60]

Input families are workstream C's (diff/scaling.py; many arguments, long strings, code with commas, nested arrays,
many calls) with sizes extended upward. Non-streaming targets:
  vllmNNN.server        the runtime's built-in gemma4 parser, server path (C's harness, diff/worker.py)
  gg.completion         slipguard.parse.parse_completion
  gg.vllmNNN.server     the slipguard plugin through the runtime's own server-path objects
Streaming (per-token deltas, as in C's diff/scaling_stream.py):
  vllmNNN.stream        built-in parser
  gg.stream             slipguard StreamParser fed the deltas (the parser's own work only)
  gg.vllmNNN.stream     the plugin through the runtime's streaming objects (includes the server's own per-step
                        string accumulation, which is O(n) per step in every runtime)
Each point runs once under SIGALRM; a target stops growing once a point exceeds half the timeout. The log-log slope
between consecutive sizes estimates the complexity exponent (1 = linear, 2 = quadratic).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


SUITE = _arg("--suite")
sys.path.insert(0, os.path.join(SUITE, "diff"))
sys.path.insert(0, SUITE)
sys.path.insert(0, os.path.join(HERE, "..", "conformance"))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import scaling as C  # noqa: E402  (C's input families)
import worker  # noqa: E402

FAMILIES = {
    "many_int_keys": (C.many_int_keys, [125, 250, 500, 1000, 2000, 4000, 8000, 16000]),
    "many_string_keys": (C.many_string_keys, [125, 250, 500, 1000, 2000, 4000, 8000, 16000]),
    "code_with_commas": (C.code_with_commas, [250, 1000, 4000, 16000, 64000]),
    "long_string": (C.long_string, [10_000, 100_000, 1_000_000, 4_000_000]),
    "flat_array_strings": (C.flat_array_strings, [250, 1000, 4000, 16000]),
    "many_calls": (C.many_calls, [10, 100, 1000, 4000]),
    "deep_arrays": (C.deep_arrays, [50, 100, 200]),
}
STREAM_FAMILIES = {
    "many_string_keys": (C.many_string_keys, [62, 125, 250, 500, 1000, 2000]),
    "long_string": (C.long_string, [4000, 16000, 64000, 256000]),
    "code_with_commas": (C.code_with_commas, [100, 400, 1600, 6400]),
}


def main():
    out_path = sys.argv[1]
    timeout = float(_arg("--timeout", "60"))
    import logging
    logging.disable(logging.WARNING)
    import gg_targets
    gg = gg_targets.GGEnv()
    vt = getattr(gg, "vtag", None)
    targets = {"gg.completion": gg.t_completion}
    stream_targets = {}
    if "gg.stream" in gg.targets:
        stream_targets["gg.stream"] = gg.t_stream
    if vt:
        env = worker.Env()
        for k, f in env.targets.items():
            if k.endswith(".server"):
                targets[k] = f
            if k.endswith(".stream"):
                stream_targets[k] = f
        targets[f"gg.{vt}.server"] = gg.targets[f"gg.{vt}.server"]
        stream_targets[f"gg.{vt}.stream"] = gg.targets[f"gg.{vt}.stream"]
    res = {"vllm": vt, "timeout_s": timeout, "python": sys.version.split()[0], "rows": []}

    def sweep(fams, tg, mode):
        for fam, (fn, sizes) in fams.items():
            for tname, tfn in tg.items():
                prev = None
                for n in sizes:
                    text = fn(n)
                    case = {"id": f"{fam}-{n}", "text": text, "tools": C.TOOLS, "intended": None}
                    r = worker.run_target(tfn, case, timeout)
                    row = {"mode": mode, "family": fam, "n": n, "chars": len(text), "target": tname,
                           "status": r["status"], "ms": r["ms"], "n_calls": len(r.get("calls") or []),
                           "exc": (r.get("exc") or "")[:120] or None}
                    if prev and r["status"] == "ok" and prev["status"] == "ok" and prev["ms"] > 2:
                        row["slope"] = round(math.log(r["ms"] / prev["ms"]) / math.log(n / prev["n"]), 2)
                    res["rows"].append(row)
                    print(json.dumps(row), flush=True)
                    prev = row
                    if r["status"] != "ok" or r["ms"] > timeout * 1000 * 0.5:
                        break

    t0 = time.time()
    sweep(FAMILIES, targets, "non-streaming")
    sweep(STREAM_FAMILIES, stream_targets, "streaming")
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main()
