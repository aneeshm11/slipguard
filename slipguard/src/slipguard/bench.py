"""`slipguard bench`: parser timing (CPU, self-contained) and a thin delegate to the TranscriptLab benchmark.

  slipguard bench parse [--max-args 16000] [--max-string 4000000]
      times slipguard's parser on growing inputs (one-shot and streamed in 4-character deltas) and prints the
      log-log slope per family (1 = linear). For the comparison against vLLM's parsers on the same inputs see
      benchmarks/perf.py in the source tree (it needs C's conformance suite and each vLLM version).

  slipguard bench transcripts -- <transcriptlab arguments>
      runs the TranscriptLab benchmark (model-agnostic; Gemma 4 format via workstream A's runner) through the
      `transcriptlab` CLI of the public repository, unchanged. slipguard adds nothing to the runner: to measure a
      slipguard configuration, point TranscriptLab at the proxy (`--server http://HOST:PORT/<cfg>/v1`) or apply
      slipguard.history.HistoryGuard as an arm transform (see the README).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time


def _bench_parse(max_args: int, max_string: int) -> dict:
    from ._vendor.gemmaproto import render_call
    from .parse import StreamParser, parse_completion
    fams = {
        "many_string_args": (lambda k: render_call("f", {f"k{i}": f"v{i}" for i in range(k)}),
                             [k for k in (500, 1000, 2000, 4000, 8000, 16000, 32000) if k <= max_args]),
        "long_string": (lambda n: render_call("write_file", {"content": ("x = {'a': [1, 2]}  # `ok`\n" * (n // 26 + 1))[:n],
                                                             "filepath": "a.py"}),
                        [n for n in (10_000, 100_000, 1_000_000, 4_000_000, 16_000_000) if n <= max_string]),
    }
    out = {"python": sys.version.split()[0], "rows": []}
    for fam, (mk, sizes) in fams.items():
        prev = {}
        for n in sizes:
            text = mk(n)
            t0 = time.perf_counter()
            parse_completion(text)
            one = time.perf_counter() - t0
            sp = StreamParser(mode="per_call")
            t0 = time.perf_counter()
            for i in range(0, len(text), 4):
                sp.feed(text[i:i + 4])
            sp.finish()
            st = time.perf_counter() - t0
            row = {"family": fam, "n": n, "chars": len(text), "oneshot_s": round(one, 5), "stream4_s": round(st, 5)}
            for k, v in (("oneshot", one), ("stream4", st)):
                if k in prev and prev[k][1] > 1e-3:
                    row[f"{k}_slope"] = round(math.log(v / prev[k][1]) / math.log(n / prev[k][0]), 2)
                prev[k] = (n, v)
            out["rows"].append(row)
            print(json.dumps(row), flush=True)
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or [])
    if argv[:1] == ["transcripts"]:
        rest = argv[1:]
        if rest[:1] == ["--"]:
            rest = rest[1:]
        exe = shutil.which("transcriptlab")
        if exe is None:
            print("The TranscriptLab CLI is not installed. Install the public repository's package (pip install "
                  "transcriptlab, or `pip install -e .` in the repository) and re-run; slipguard only delegates.",
                  file=sys.stderr)
            return 2
        return subprocess.call([exe, *rest])
    ap = argparse.ArgumentParser(prog="slipguard bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse")
    p.add_argument("--max-args", type=int, default=16000)
    p.add_argument("--max-string", type=int, default=4_000_000)
    p.add_argument("--out")
    a = ap.parse_args(argv)
    res = _bench_parse(a.max_args, a.max_string)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(res, f, indent=1)
    return 0
