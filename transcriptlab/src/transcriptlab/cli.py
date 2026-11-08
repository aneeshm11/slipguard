"""transcriptlab — run the TranscriptLab benchmark on your model with one command, then read the report.

    transcriptlab run --base http://HOST:PORT/v1 --model NAME --pool A1 --arms P0,P1,P6,P8a --out runs/mymodel
    transcriptlab report runs/mymodel

    transcriptlab estimate --pool A1 --arms P0,P1,P6,P8a     # cost before you start (300 x 4 = 1,200 generations)
    transcriptlab verify [--format gemma4]                    # hashes of the frozen runner and analysis
    transcriptlab arms                                        # what each history arm does

This is a thin wrapper: it selects the public states (the first N of a pool, in rank order), writes the job list the
frozen runner reads, runs the frozen runner and the frozen analysis unchanged (as subprocesses, with their own
arguments) and prints the analysis. See backends.py for the exact files and hashes.

The endpoint must be an OpenAI-compatible /v1/completions server that accepts raw prompts with special tokens and
vLLM's sampling extras (seed, top_k, stop_token_ids, skip_special_tokens), e.g. `vllm serve` (the runners send the
rendered prompt; no server-side tool or reasoning parser is involved).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from . import backends as B

BOOT = r"""
import json, runpy, sys
frozen, script, reg = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
sys.path.insert(0, frozen)
import qwenproto as qp
if reg.get('entry'):
    qp.MODELS.setdefault(reg['mk'], reg['entry'])
if reg.get('dir'):
    qp.MODELS[reg['mk']] = {**qp.MODELS[reg['mk']], 'dir': reg['dir']}
if reg.get('entry') and script.endswith('run_ext.py'):
    # A new model (not in X's registry). X's runner was written for Qwen tokenizers: it stops on <|im_end|> and
    # <|endoftext|> and sends the rendered prompt (which already holds any BOS) with the server's default
    # add_special_tokens=true. For another tokenizer (e.g. a Llama-3.1 fine-tune in the hermes format) that sends a
    # null stop id (vLLM rejects the request), a second BOS, and no stop on the model's own end tokens. This adapter
    # fixes the request for new models only; registered models never take this path and the frozen runner is unchanged.
    import os
    import httpx
    _t = qp.hf_tok(reg['mk'])
    def _id(x):
        i = _t.convert_tokens_to_ids(x)
        return i if isinstance(i, int) and (i != _t.unk_token_id or x == _t.unk_token) else None
    _ends = {i for i in [_t.eos_token_id] + [_id(x) for x in ('<|im_end|>', '<|endoftext|>', '<|end_of_text|>', '<|eot_id|>')]
             if isinstance(i, int)}
    _gc = os.path.join(qp.MODELS[reg['mk']].get('dir') or '', 'generation_config.json')
    if os.path.isfile(_gc):
        _e = json.load(open(_gc)).get('eos_token_id')
        _ends |= set(_e if isinstance(_e, list) else [_e] if isinstance(_e, int) else [])
    _bos = _t.bos_token if (_t.bos_token and _t('', add_special_tokens=True)['input_ids'][:1] == [_t.bos_token_id]) else None
    print(f"transcriptlab: new model {reg['mk']}: stop on its end tokens {sorted(_ends)}"
          + (f"; prompts already start with {_bos}, so add_special_tokens=false" if _bos else ""), file=sys.stderr, flush=True)
    def _adapt(b):
        if not (isinstance(b, dict) and isinstance(b.get('prompt'), str)):
            return b
        b = dict(b)
        b['stop_token_ids'] = sorted({i for i in (b.get('stop_token_ids') or []) if isinstance(i, int)} | _ends)
        if _bos and b['prompt'].startswith(_bos):
            b['add_special_tokens'] = False
        return b
    _stream = httpx.AsyncClient.stream
    def _stream_adapted(self, method, url, *x, **k):
        if 'json' in k:
            k['json'] = _adapt(k['json'])
        return _stream(self, method, url, *x, **k)
    httpx.AsyncClient.stream = _stream_adapted
sys.argv = [script] + sys.argv[4:]
runpy.run_path(script, run_name='__main__')
"""


def _say(msg: str = "") -> None:
    print(msg, flush=True)


def _root(a, **kw) -> Path:
    """the repository root (precedence in backends.resolve_root), announced on stdout so it is never silent."""
    root, how = B.resolve_root(getattr(a, "root", None), **kw)
    rec = kw.get("recorded")
    note = f"; the run recorded {rec}" if rec and how.startswith(("--root", "$")) and str(rec) != str(root) else ""
    _say(f"root: {root} ({how}{note})")
    return root


def _registered_x_models(root: Path) -> set[str]:
    """model keys of X's frozen registry (read from the source; nothing is imported)."""
    src = (root / B.X_FROZEN / "qwenproto.py").read_text()
    blk = src[src.index("MODELS = {"):]
    blk = blk[:blk.index("\n}\n")]
    return set(re.findall(r"^\s+'([^']+)':\s*\{", blk, flags=re.M))


def _local_or_id(x: str | None) -> str | None:
    """absolute path if x names a local file/dir (the frozen scripts run with the tree root as working directory), else
    unchanged (a Hugging Face id)."""
    return str(Path(x).resolve()) if x and Path(x).exists() else x


def _interp(x: str | None) -> str:
    """interpreter for the frozen scripts. Made absolute WITHOUT resolving symlinks: a virtualenv's bin/python is a
    symlink to the base interpreter, and resolving it silently drops the venv's packages (bug found 2026-11-06 by
    PREREG_v2.8's first run: `--python <venv>/bin/python` ran /usr/bin/python3.12 -> ModuleNotFoundError: httpx)."""
    if not x:
        return sys.executable
    return str(Path(x).absolute()) if Path(x).exists() else (shutil.which(x) or x)


def frozen_env(root: Path) -> dict:
    """environment of the frozen subprocesses: the tree root for the exported scripts' path lookups, unbuffered output,
    and no bytecode written into the tree."""
    return dict(os.environ, TRANSCRIPTLAB_ROOT=str(root), PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1")


def _x_registration(a, root: Path) -> tuple[str, dict]:
    known = _registered_x_models(root)
    if a.mk:
        if a.mk not in known:
            raise B.SetupError(f"--mk {a.mk!r} is not in X's registry ({', '.join(sorted(known))}); omit --mk and pass "
                               "--tokenizer to register a new hermes / qwen3_coder model for this run")
        return a.mk, ({"mk": a.mk, "dir": _local_or_id(a.tokenizer)} if a.tokenizer else {})
    if a.format not in ("hermes", "qwen3_coder"):
        raise B.SetupError(f"format {a.format}: pass --mk with one of the registered models of that format "
                           "(token-id rendering is model-specific)")
    if not a.tokenizer:
        raise B.SetupError("a new model needs --tokenizer <HF id or local dir> (its chat template renders the states)")
    mk = re.sub(r"[^A-Za-z0-9_.-]+", "-", a.model).strip("-").lower() or "model"
    entry = {"dir": _local_or_id(a.tokenizer), "fmt": B.X_FMT[a.format], "model_type": "qwen3", "thinking": not a.no_thinking}
    return mk, {"mk": mk, "entry": entry}


def _cmd_x(py: str, root: Path, script: str, reg: dict, args: list[str]) -> list[str]:
    path = str(root / B.X_FROZEN / script)
    if not reg:
        return [py, path, *args]
    return [py, "-c", BOOT, str(root / B.X_FROZEN), path, json.dumps(reg), *args]


def _run_logged(cmd: list[str], log: Path, env: dict | None = None, cwd: Path | None = None) -> int:
    with open(log, "a") as fo:
        shown = cmd if cmd[1] != "-c" else [cmd[0], "-c", "<bootstrap>", *cmd[3:]]
        fo.write(f"\n$ {shlex.join(shown)}\n")
        fo.flush()
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=cwd,
                              bufsize=1) as p:
            for line in p.stdout:
                sys.stdout.write(line)
                fo.write(line)
            return p.wait()


def _print_estimate(root: Path, n: int, arms: list[str], ids: set[str]) -> dict:
    est = B.estimate(n, arms)
    _say(f"cost: {est['states']} states x {est['arms']} arms = {est['generations']:,} generations "
         f"(<= {B.MAX_NEW:,} new tokens each; {est['note']})")
    ref = B.reference_usage(root, arms, ids)
    if ref:
        _say(f"      reference, registered Gemma-4-31B 4-bit run on the same jobs: mean prompt "
             f"{ref['mean_prompt_tokens']:,} tokens, mean generated {ref['mean_generated_tokens']:,} tokens per job "
             f"-> about {ref['mean_prompt_tokens'] * est['generations'] / 1e6:.1f} M prompt tokens and "
             f"{ref['mean_generated_tokens'] * est['generations'] / 1e6:.2f} M generated tokens in total")
        est["reference_usage"] = ref
    return est


def cmd_estimate(a) -> int:
    root = _root(a)
    arms = B.parse_arms(a.arms, a.format)
    states = B.pool_states(root, a.pool, a.n_states)
    _print_estimate(root, len(states), arms, {s["context_id"] for s in states})
    return 0


def cmd_arms(a) -> int:
    for k, v in B.ARM_HELP.items():
        _say(f"{k:4s} {v}")
    _say(f"gemma4 analysis covers {','.join(B.GEMMA_ARMS)}; other formats accept {','.join(B.X_ARMS)}")
    return 0


def cmd_verify(a) -> int:
    root = _root(a)
    rows = B.check_pinned(root, a.format)
    for r in rows:
        _say(f"{r['status']:8s} {r['file']}  {(r['actual'] or '-')[:16]}")
    bad = [r for r in rows if not r["ok"]]
    nx = sum(r["status"] == "exported" for r in rows)
    _say(f"{len(rows) - len(bad)}/{len(rows)} frozen files match their pinned sha256"
         + (f" ({nx} as the path-rewritten export recorded in {B.EXPORT_PINS})" if nx else ""))
    return 1 if bad else 0


def cmd_run(a) -> int:
    root = _root(a)
    arms = B.parse_arms(a.arms, a.format)
    states = B.pool_states(root, a.pool, a.n_states)
    if a.limit_states:
        states = states[:a.limit_states]
    ids = [s["context_id"] for s in states]
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    _say(f"transcriptlab {__version__}: {a.format} | model {a.model} @ {a.base} | pool {a.pool}, {len(states)} states | "
         f"arms {','.join(arms)} -> {out}")
    est = _print_estimate(root, len(states), arms, set(ids))
    pinned = B.check_pinned(root, a.format)
    diff = [r["file"] for r in pinned if not r["ok"]]
    if diff:
        msg = (f"{len(diff)} frozen file(s) match neither their pinned sha256 nor a recorded export "
               f"({B.EXPORT_PINS}): {', '.join(diff)}")
        if a.require_frozen:
            raise B.SetupError(msg)
        _say("WARNING: " + msg)
    else:
        nx = sum(r["status"] == "exported" for r in pinned)
        _say(f"frozen code: {len(pinned)}/{len(pinned)} files match their pinned sha256"
             + (f" ({nx} as recorded path-rewritten exports)" if nx else ""))
    manifest = B.corpus_manifest(root, a.corpus)
    (out / "ids.txt").write_text("\n".join(ids) + "\n")
    py = _interp(a.python)
    env = frozen_env(root)
    cmds: list[list[str]] = []
    run = {"transcriptlab": __version__, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "format": a.format, "model": a.model, "base": a.base, "pool": a.pool, "n_states": len(states),
           "arms": arms, "corpus_manifest": str(manifest), "corpus_manifest_sha256": B.sha256(manifest),
           "pool_file_sha256": B.sha256(root / B.POOLS / f"S1_{a.pool}.jsonl"), "frozen_files": pinned,
           "estimate": est, "root": str(root)}
    if a.format == "gemma4":
        plan = B.gemma_plan(states, arms)
        with open(out / "plan.jsonl", "w") as f:
            for j in plan:
                f.write(json.dumps(j) + "\n")
        tok = _local_or_id(a.tokenizer or a.model)
        meta, localized = B.localized_meta(root, manifest, out, Path(a.meta).resolve() if a.meta else None)
        cmds.append([py, str(root / B.A_SCRIPTS / "run_injection.py"), "--manifest", str(manifest),
                     "--meta", str(meta), "--plan", str(out / "plan.jsonl"), "--out", str(out / "gen.jsonl"),
                     "--template", str(manifest.parent / "chat_template.jinja"), "--blind", "--conc", str(a.conc),
                     "--base", a.base, "--model", a.model, "--tok", tok, "--max_model_len", str(a.max_model_len or 32768)])
        run.update(tokenizer=tok, meta=str(meta), meta_localized=localized,
                   meta_source_sha256=B.sha256(Path(a.meta).resolve() if a.meta else root / B.META_S1))
    else:
        mk, reg = _x_registration(a, root)
        x_arms = ",".join(B.x_arm(x) for x in arms)
        cmds.append(_cmd_x(py, root, "prep_prompts_ext.py", reg,
                           ["--manifest", str(manifest), "--mk", mk, "--out", str(out / "prompts.jsonl"),
                            "--ids", str(out / "ids.txt"), "--arms", x_arms, "--set", "battery",
                            "--workers", str(a.workers)]))
        run_args = ["--prompts", str(out / "prompts.jsonl"), "--out", str(out / "gen.jsonl"), "--mk", mk,
                    "--base", a.base, "--served", a.model, "--sets", "battery", "--conc", str(a.conc)]
        if a.max_model_len:
            run_args += ["--max_model_len", str(a.max_model_len)]
        cmds.append(_cmd_x(py, root, "run_ext.py", reg, run_args))
        run.update(mk=mk, registration=reg, x_arms=x_arms.split(","))
    run["commands"] = [c if c[1] != "-c" else [c[0], "-c", "<transcriptlab bootstrap: registers the model key, then "
                                                           "runs the frozen script unchanged>", *c[3:]] for c in cmds]
    (out / "transcriptlab_run.json").write_text(json.dumps(run, indent=1) + "\n")
    if a.dry_run:
        for c in run["commands"]:
            _say("$ " + shlex.join(c))
        _say(f"dry run: nothing executed; config in {out / 'transcriptlab_run.json'}")
        return 0
    log = out / "run.log"
    for c in cmds:
        rc = _run_logged(c, log, env, cwd=root)   # relative paths in the tree's meta resolve against the root
        if rc != 0:
            _say(f"frozen step failed (exit {rc}); see {log}")
            return rc
    n = len((out / "gen.jsonl").read_text().splitlines()) if (out / "gen.jsonl").exists() else 0
    _say(f"done: {n} generation records in {out / 'gen.jsonl'}; next: transcriptlab report {out}")
    return 0


def _fmt_rate(x) -> str:
    return f"{100 * x[0]:5.1f}% [{100 * x[1]:.1f}, {100 * x[2]:.1f}]"


def _fmt_rd(rd, ci) -> str:
    return f"{100 * rd:+5.1f} pp [{100 * ci[0]:+.1f}, {100 * ci[1]:+.1f}]"


def summarize(run: dict, ana: dict) -> list[str]:
    """the table printed by `report` (read-only view of the frozen analysis output)."""
    L = [f"TranscriptLab report: {run['model']} ({run['format']}), pool {run['pool']}, {run['n_states']} states",
         "outcome: P(next call is a malformed edit), unconditional; 95% CIs from the frozen analysis", ""]
    if run["format"] == "gemma4":
        u = ana["uncond"]
        L.append(f"complete states analysed: {ana['complete_states']} ({ana['episodes']} episodes; missing jobs "
                 f"{ana['missing']})")
        for arm in B.GEMMA_ARMS:
            L.append(f"  {arm:4s} {_fmt_rate(u[arm])}   {B.ARM_HELP[arm]}")
        L.append("")
        L.append(f"  copying    RD(P1 - P0)  {_fmt_rd(u['RD_P1_P0'][0], u['RD_P1_P0'][1:3])}")
        L.append(f"  induction  RD(P6 - P0)  {_fmt_rd(u['RD_P6_P0'][0], u['RD_P6_P0'][1:3])}")
        rem = u["P8a_removal"]
        L.append("  quarantine removal of the P1 excess: " + (f"{100 * rem[0]:.0f}% [{100 * rem[1]:.0f}, {100 * rem[2]:.0f}]"
                                                          if rem[0] is not None else "undefined (no P1 excess)"))
        cmp_ = u.get("bf16_minus_QAT_same_states") or {}
        if cmp_.get("n_states"):
            L.append("")
            L.append(f"  your model minus the registered Gemma-4-31B 4-bit run, same {cmp_['n_states']} states:")
            L.append("    " + "   ".join(f"{arm} {100 * cmp_[arm][0]:+.1f} pp [{100 * cmp_[arm][1]:+.1f}, {100 * cmp_[arm][2]:+.1f}]"
                                         for arm in B.GEMMA_ARMS))
            L.append("    (the analysis labels this block 'bf16_minus_QAT_same_states': it was written for the bf16 row)")
    else:
        L.append(f"records: {ana['n_records']}; errors: {ana.get('errors')}")
        for arm in run["x_arms"]:
            r = ana["arms"].get(arm)
            if r:
                L.append(f"  {arm:4s} {_fmt_rate(r['P_malformed_edit_uncond'])}   n = {r['n']}")
        L.append("")
        for arm, lab in (("P1L", "copying    RD(P1 - P0)"), ("P6", "induction  RD(P6 - P0)"), ("P1N", "native     RD(P1N - P0)")):
            p = (ana.get("paired_vs_P0") or {}).get(arm)
            if p:
                L.append(f"  {lab}  {_fmt_rd(p['uncond']['RD'], p['uncond']['RD_CI'])}")
        q = (ana.get("removal") or {}).get("P8a")
        if q:
            u = q["uncond"]
            L.append(f"  quarantine removal of the P1 excess: {u['fraction_removed']:.2f} [{u['CI'][0]}, {u['CI'][1]}]"
                     " (unstable when the P1 excess is small)")
    L.append("")
    L.append("The registered verdict rules (thresholds, Holm) live in the preregistrations; this report prints estimates only.")
    return L


def cmd_report(a) -> int:
    out = Path(a.dir).resolve()
    cfg = out / "transcriptlab_run.json"
    if not cfg.exists():
        raise B.SetupError(f"{cfg} missing: {out} is not a run directory of `transcriptlab run`")
    run = json.loads(cfg.read_text())
    # --root > $TRANSCRIPTLAB_ROOT > the recorded root (if absolute and still a root) > parents of the run dir / cwd
    root = _root(a, recorded=run.get("root"), near=out)
    py = _interp(a.python)
    gen = out / "gen.jsonl"
    if not gen.exists():
        raise B.SetupError(f"{gen} missing: run `transcriptlab run` first")
    ana_path = out / "analysis.json"
    if run["format"] == "gemma4":
        cmd = [py, str(root / B.A_SCRIPTS / "analyze_bf16_core.py"), "--res", str(gen), "--log", str(out / "run.log"),
               "--out", str(ana_path), "--B", str(a.B or 2000)]
        if a.allow_incomplete:
            cmd.append("--force_incomplete")
    else:
        reg = run.get("registration") or {}
        cmd = _cmd_x(py, root, "analyze.py", reg, ["--mk", run["mk"], "--gen", str(gen), "--manifest", run["corpus_manifest"],
                                                   "--ids", str(out / "ids.txt"), "--out", str(ana_path), "--B", str(a.B or 10000)])
    if not a.quiet:
        rc = _run_logged(cmd, out / "report.log", frozen_env(root), cwd=root)
    else:
        with open(out / "report.log", "a") as fo:
            rc = subprocess.call(cmd, stdout=fo, stderr=subprocess.STDOUT, env=frozen_env(root), cwd=root)
    if rc != 0 or not ana_path.exists():
        _say(f"frozen analysis failed (exit {rc}); see {out / 'report.log'}")
        return rc or 1
    lines = summarize(run, json.loads(ana_path.read_text()))
    (out / "report.txt").write_text("\n".join(lines) + "\n")
    _say("\n".join(lines))
    _say(f"\nfull analysis: {ana_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="transcriptlab", description=__doc__.split("\n\n")[0])
    ap.add_argument("--version", action="version", version=f"transcriptlab {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, report=False):
        p.add_argument("--root", help="TranscriptLab repository root (default: $TRANSCRIPTLAB_ROOT, "
                                      + ("else the root recorded in the run if it exists, else a parent of the run "
                                         "directory or of the cwd" if report else "else a parent of the cwd")
                                      + "); the root used is printed first")

    def sel(p):
        p.add_argument("--format", choices=B.FORMATS, default="gemma4", help="tool-call format of the model")
        p.add_argument("--pool", default="A1", help="public state pool (A1 = the registered 300-state battery)")
        p.add_argument("--arms", default="P0,P1,P6,P8a", help="history arms (see `transcriptlab arms`)")
        p.add_argument("--n-states", type=int, default=300, help="first N states of the pool, in rank order")

    p = sub.add_parser("run", help="render the states, generate, judge (frozen runner)")
    common(p); sel(p)
    p.add_argument("--base", required=True, help="OpenAI-compatible base URL ending in /v1 (vLLM recommended)")
    p.add_argument("--model", required=True, help="served model name")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--tokenizer", help="HF id or local dir of the model's tokenizer (default: --model)")
    p.add_argument("--mk", help="registered model key of X's runner (non-gemma4 formats)")
    p.add_argument("--no-thinking", action="store_true", help="new hermes/qwen3_coder model without a thinking mode")
    p.add_argument("--corpus", help="the PNC dataset root, its S1 contexts directory, or the S1 manifest.json (default: data/pnc/contexts/P-swebench-31b-S1-v1/)")
    p.add_argument("--meta", help="gemma4: state metadata (default: experiments/contagion/data/confirmatory/meta_S1.jsonl)")
    p.add_argument("--limit-states", type=int, default=0, help="pilot: only the first K of the N states")
    p.add_argument("--conc", type=int, default=20, help="concurrent requests")
    p.add_argument("--workers", type=int, default=8, help="render workers (non-gemma4 formats)")
    p.add_argument("--max-model-len", type=int, default=0, help="context length (gemma4 default 32768; others: from /v1/models)")
    p.add_argument("--python", help="interpreter for the frozen scripts (default: this one)")
    p.add_argument("--require-frozen", action="store_true", help="refuse to run if a frozen file's sha256 differs")
    p.add_argument("--dry-run", action="store_true", help="write the job list and config, print the commands, stop")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("report", help="frozen analysis of a run directory + a short table")
    common(p, report=True)
    p.add_argument("dir")
    p.add_argument("--B", type=int, default=0, help="bootstrap replicates (default = registered: 2000 gemma4, 10000 others)")
    p.add_argument("--allow-incomplete", action="store_true", help="gemma4: analyse even if the runner did not finish")
    p.add_argument("--python")
    p.add_argument("--quiet", action="store_true", help="do not echo the analysis output")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("estimate", help="number of generations and token budget")
    common(p); sel(p)
    p.set_defaults(fn=cmd_estimate)

    p = sub.add_parser("verify", help="sha256 of the frozen runner/analysis against the pinned values")
    common(p)
    p.add_argument("--format", choices=B.FORMATS, default="gemma4")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("arms", help="what each history arm does")
    p.set_defaults(fn=cmd_arms)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except B.SetupError as e:
        print(f"transcriptlab: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
