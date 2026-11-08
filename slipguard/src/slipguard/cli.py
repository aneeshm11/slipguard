"""Command line: slipguard <command> ...

  parse            parse model output from stdin or a file (strict; --per-call for runtime semantics) -> JSON
  check            exit 1 if the text is not a strictly valid Gemma 4 completion (CI / log scanning)
  proxy            workstream E's IPD proxy (see `slipguard proxy -h`)
  audit            scan transcripts (OpenAI message lists) for laundered calls, raw calls, control text
  audit-weights    string-end protocol fidelity of a served checkpoint (workstream F's frozen audit; [weights] extra)
  verify           check the guarantees on this installation (frozen identity, conformance, optional P1)
  plugin-path      path of the vLLM plugin file (for --tool-parser-plugin / --reasoning-parser-plugin); slipguard
                   itself must be installed in vLLM's Python environment (the plugin imports slipguard.parse)
  template-path    path of the patched chat template (for vllm serve --chat-template)
  bench            parser benchmarks (CPU) / TranscriptLab delegate
"""
from __future__ import annotations

import argparse
import json
import sys

from ._name import DIST_NAME, TAGLINE
from ._version import __version__

PLUGIN_ENV_NOTE = (
    "note: the plugin file imports slipguard, so slipguard must be installed in the SAME Python environment as vLLM "
    "(the one that runs `vllm serve`, e.g. its venv or container): `<vLLM's python> -m pip install slipguard` (core "
    "package, no extras; from a checkout: `<vLLM's python> -m pip install ./slipguard`). Otherwise vLLM logs "
    "\"No module named 'slipguard'\" and the gemma4_strict parsers are not registered. This path is in {prefix}.")


def _read(path: str | None) -> str:
    if path in (None, "-"):
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def cmd_parse(a) -> int:
    from .parse import ParseError, extract, parse_completion
    text = _read(a.file)
    if a.per_call:
        d = extract(text, parse_thought=True, in_thought=a.in_thought).to_dict()
        print(json.dumps(d, ensure_ascii=False, indent=1, default=str))
        return 1 if d.get("errors") else 0      # same contract as without --per-call: 1 = a protocol error was found
    try:
        pc = parse_completion(text, in_thought=a.in_thought)
    except ParseError as e:
        print(json.dumps({"error": e.to_dict()}, ensure_ascii=False, indent=1, default=str))
        return 1
    print(json.dumps(pc.to_dict(), ensure_ascii=False, indent=1, default=str))
    return 0


def cmd_check(a) -> int:
    from .parse import ParseError, parse_completion
    try:
        parse_completion(_read(a.file), in_thought=a.in_thought)
    except ParseError as e:
        print(f"INVALID {e}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def cmd_verify(a) -> int:
    from . import verify as V
    if a.model_dir:                         # the P1 test builds the proxy: check its engine's packages first
        from .repair.proxy import EngineDependencyError, require_engine
        try:
            require_engine(a.engine, prog="slipguard verify --model-dir")
        except EngineDependencyError as e:
            print(e, file=sys.stderr)
            return 2
    out = {"frozen": V.check_frozen(), "conformance": V.check_conformance()}
    if a.model_dir:
        from .repair.proxy import EngineDependencyError
        try:
            out["p1"] = V.check_p1(a.model_dir, data=a.data, engine=a.engine, limit=a.limit)
        except EngineDependencyError as e:
            print(str(e).replace("slipguard.repair:", "slipguard verify --model-dir:", 1)
                  .replace('pass engine="lite"', "pass --engine lite"), file=sys.stderr)
            return 2
    ok = all(v["ok"] for v in out.values())
    out["ok"] = ok
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print(("VERIFY PASS" if ok else "VERIFY FAIL") + ": " + ", ".join(f"{k}={'ok' if v['ok'] else 'FAIL'}"
                                                                  for k, v in out.items() if isinstance(v, dict)),
          file=sys.stderr)
    return 0 if ok else 1


def cmd_plugin_path(a) -> int:
    from .integrations import plugin_path
    print(plugin_path(a.kind))                              # stdout: the path only (for P=$(slipguard plugin-path))
    if not a.quiet:
        print(PLUGIN_ENV_NOTE.format(prefix=sys.prefix), file=sys.stderr)
    return 0


def cmd_template_path(a) -> int:
    from .template import path
    print(path(a.which))
    return 0


def cmd_bench(a) -> int:
    from .bench import main as bench_main
    return bench_main(a.rest)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["proxy"]:
        from .repair.proxy import main as proxy_main
        return proxy_main(argv[1:])
    if argv[:1] == ["audit"]:
        from .audit import main as audit_main
        return audit_main(argv[1:])
    if argv[:1] in (["repair-weights"], ["verify-certificate"]):
        print(f"slipguard {argv[0]}: not shipped. Weight repair is not part of slipguard: no repair candidate passed its "
              "registered gate (see the weight-audit results of the TranscriptLab release, experiments/quant_margins/"
              "wsa/RESULTS.md). The weight AUDIT ships as `slipguard audit-weights`.", file=sys.stderr)
        return 2
    if argv[:1] == ["audit-weights"]:
        from .weights import cli as weights_cli          # workstream F's frozen audit (see slipguard.weights)
        return weights_cli(argv[0], argv[1:])
    ap = argparse.ArgumentParser(prog=DIST_NAME, description=TAGLINE,
                                 epilog="No GPU? `slipguard audit transcripts.jsonl --tools tools.json` scans your own "
                                        "agent logs for laundered calls on the CPU (core install, stdlib only).")
    ap.add_argument("--version", action="version", version=f"{DIST_NAME} {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("parse", help="parse a completion (JSON out)",
                       epilog="exit status: 0 = strictly valid (or, with --per-call, no protocol error); 1 = a protocol "
                              "error (the JSON says where; with --per-call the calls before it are still listed); "
                              "2 = usage error")
    p.add_argument("file", nargs="?", help="file with the raw completion text (default: stdin)")
    p.add_argument("--per-call", action="store_true",
                   help="runtime semantics: the calls up to the first protocol error, the rest as content")
    p.add_argument("--in-thought", action="store_true", help="the prompt ended inside a thought")
    p.set_defaults(fn=cmd_parse)
    p = sub.add_parser("check", help="exit 1 unless the completion is strictly valid")
    p.add_argument("file", nargs="?")
    p.add_argument("--in-thought", action="store_true")
    p.set_defaults(fn=cmd_check)
    sub.add_parser("proxy", help="IPD proxy (see `slipguard proxy -h`)")
    sub.add_parser("audit", help="scan transcripts for protocol hazards (see `slipguard audit -h`)")
    sub.add_parser("audit-weights", help="weight audit: string-end margins of a served checkpoint (see -h)")
    p = sub.add_parser("verify", help="check the guarantees on this installation")
    p.add_argument("--model-dir", help="Gemma 4 model dir: also run the P1 byte-identity test through the proxy "
                                       "(needs slipguard[proxy-frozen], or slipguard[proxy] with --engine lite)")
    p.add_argument("--data", help="QuoteStorm payloads.jsonl: release/package/v1.0/quotestorm/payloads.jsonl of the "
                                  "release dataset (default: built-in synthetic payloads)")
    p.add_argument("--engine", choices=["frozen", "lite"], default="frozen",
                   help="proxy engine for the P1 test: frozen (evaluated; vLLM 0.19.1) or lite (derived; no vLLM)")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("plugin-path", help="path of the vLLM plugin file (slipguard must be installed in vLLM's env)")
    p.add_argument("kind", nargs="?", default="vllm", choices=["vllm"])
    p.add_argument("-q", "--quiet", action="store_true", help="do not print the environment note to stderr")
    p.set_defaults(fn=cmd_plugin_path)
    p = sub.add_parser("template-path", help="path of the patched (or official) chat template")
    p.add_argument("which", nargs="?", default="guarded", choices=["guarded", "official"])
    p.set_defaults(fn=cmd_template_path)
    p = sub.add_parser("bench", help="benchmarks (`slipguard bench -h`)")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_bench)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
