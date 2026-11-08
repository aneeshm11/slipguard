"""Weight audit: ``slipguard audit-weights`` -- string-end protocol fidelity of a served Gemma 4 checkpoint.

The measurement code is workstream F's frozen package ``wsaudit`` (wsa-1.0), shipped byte-identical and sha-checked in
``slipguard/_frozen/wsa/`` together with its two points packs. This module only re-exports it and composes a report;
it adds no logic of its own. Weight *repair* is not part of slipguard (the candidates did not pass their registered
gate).

What is measured: at decision points of real Gemma 4 agent turns (the public PNC corpus; the shipped pack lists episode,
turn and positions, and the prompts are re-rendered from a PNC directory you pass), the server is asked for the next
token by teacher forcing in generation mode (token-id prompt = rendered prompt + logged completion up to the decision;
max_tokens 1, temperature 0, logprobs 20). At each string end the margin is m = log P(<|"|>) - log P(best look-alike
closer) from the top-20 log-probabilities. When the true closer or every look-alike is outside the top-20, the margin
is CENSORED and only a lower bound lp(<|"|>) - lp_20 is known: the report gives the censored fraction, and the median
and 10th percentile are lower bounds.

Report: margin median / p10 (lower bounds), P(m < ln 19), E_slip (look-alike probability under the shipped sampler
T=1, top-k 64, top-p 0.95, rebuilt from the top-20), onset per-call slip probability; with a reference run, the paired
median margin deficit with an episode-cluster bootstrap CI. Pre-registered flag rule (F's SWEEP_PLAN): FLAG if
P(m < ln 19) >= 0.5% or the median deficit vs the SAME-FAMILY bf16 reference >= 3 nats; SEVERE if P(m < ln 19) >= 2%
or E_slip >= 1%. Without a same-family bf16 reference the report is descriptive only (no verdict).

Needs ``pip install "slipguard[weights]"`` (numpy; httpx and transformers for a live audit) and an OpenAI-compatible
completions endpoint that accepts token-id prompts and returns top-20 logprobs (vLLM). Keep ``conc`` low (1 on servers
whose KV cache holds about one 17k-token context) so prefixes stay cached.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Iterable

SCHEMA = "slipguard.weights.audit/v1"
PACKS = ("audit16k", "core")      # audit16k: 235 held-out items <= 16.4k tokens (the sweep pack); core: 951 items


def _w():
    from .._frozen import load_wsa
    return load_wsa()


def pack_path(pack: str = "audit16k") -> str:
    """A shipped pack by name ('audit16k', 'core') or a path to your own pack."""
    from .._frozen import paths
    return paths().wsa_packs.get(pack, pack)


def audit_endpoint(base_url: str, served_name: str, *, pnc_dir: str, tokenizer_dir: str, pack: str = "audit16k",
                   split: str = "heldout", kinds: Iterable[str] = ("close", "slip"), conc: int = 2,
                   max_total: int | None = None, records_out: str | None = None) -> list[dict]:
    """Per-position records from a live server (F's ``audit_endpoint``; ``pack`` may be a shipped pack name)."""
    return _w().audit_endpoint(base_url, served_name, pnc_dir=pnc_dir, tokenizer_dir=tokenizer_dir,
                               pack=pack_path(pack), split=split, kinds=tuple(kinds), conc=conc, max_total=max_total,
                               records_out=records_out)


def summarize(records: list[dict]) -> dict:
    return _w().summarize(records)


def compare(records: list[dict], reference: list[dict]) -> dict:
    return _w().compare(records, reference)


def flag(summary: dict, paired: dict | None = None) -> tuple[bool, bool]:
    return _w().flag(summary, paired)


def load_records(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def report(records: list[dict], reference: list[dict] | None = None, *, pack: str | None = None) -> dict:
    """summary (+ paired deficit vs ``reference``) + the pre-registered verdict. ``reference`` must be the SAME-FAMILY
    bf16 checkpoint's records on the same pack; without it the report is descriptive only (FLAG/SEVERE = None)."""
    from .. import __version__
    w = _w()
    summary = w.summarize(records)
    paired = w.compare(records, reference) if reference is not None else None
    fl, sev = w.flag(summary, paired) if paired is not None else (None, None)
    out: dict[str, Any] = {"schema": SCHEMA, "tool": {"slipguard": __version__, "wsaudit": w.__version__},
                           "summary": summary, "paired_vs_reference": paired, "FLAG": fl, "SEVERE": sev,
                           "descriptive_only": paired is None,
                           "flag_rule": "FLAG: P(m < ln 19) >= 0.5% or median deficit vs same-family bf16 >= 3 nats; "
                                        "SEVERE: P(m < ln 19) >= 2% or E_slip >= 1%",
                           "censoring": "margins are top-20 lower bounds where censored (summary.censored_frac)"}
    if pack is not None:
        p = pack_path(pack)
        out["pack"] = {"name": pack if pack in PACKS else os.path.basename(p), "sha256": _sha(p)}
    return out


def cli(command: str, argv: list[str]) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog=f"slipguard {command}",
                                 description="String-end protocol fidelity of a served Gemma 4 checkpoint (top-20 "
                                             "teacher forcing on PNC decision points); see slipguard.weights.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--endpoint", help="OpenAI-compatible base URL (vLLM) with top-20 logprobs, e.g. http://host:8000/v1")
    src.add_argument("--from-records", help="re-score saved per-position records (CPU only, no server)")
    ap.add_argument("--served-name", help="served model name (with --endpoint)")
    ap.add_argument("--pnc", help="PNC corpus directory (prompts are re-rendered from it; with --endpoint)")
    ap.add_argument("--tokenizer", help="Gemma 4 tokenizer directory (with --endpoint)")
    ap.add_argument("--pack", default="audit16k", help="audit16k (default) | core | path to a pack .jsonl(.gz)")
    ap.add_argument("--split", default="heldout")
    ap.add_argument("--conc", type=int, default=2, help="concurrent items (1 if the KV cache holds ~one 17k context)")
    ap.add_argument("--max-total", type=int, help="skip probes longer than this many tokens")
    ap.add_argument("--records", help="write the per-position records here (JSONL; with --endpoint)")
    ap.add_argument("--reference", help="records of the SAME-FAMILY bf16 checkpoint (enables the verdict)")
    ap.add_argument("--out", help="report JSON (default: stdout)")
    a = ap.parse_args(argv)
    if a.endpoint:
        miss = [f for f in ("served_name", "pnc", "tokenizer") if not getattr(a, f)]
        if miss:
            ap.error("--endpoint needs " + ", ".join("--" + m.replace("_", "-") for m in miss))
    try:
        if a.endpoint:
            recs = audit_endpoint(a.endpoint, a.served_name, pnc_dir=a.pnc, tokenizer_dir=a.tokenizer, pack=a.pack,
                                  split=a.split, conc=a.conc, max_total=a.max_total, records_out=a.records)
        else:
            recs = load_records(a.from_records)
        ref = load_records(a.reference) if a.reference else None
        rep = report(recs, ref, pack=a.pack if a.endpoint else None)
    except ImportError as e:
        print(f"slipguard {command}: missing optional dependency ({e.name}); pip install 'slipguard[weights]'",
              file=sys.stderr)
        return 2
    text = json.dumps(rep, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"slipguard {command}: wrote {a.out}: {_verdict_line(rep)}", file=sys.stderr)
    else:
        print(text)
    return 0


def _verdict_line(rep: dict) -> str:
    """one-line summary of a report (printed when the report goes to --out; the report itself is unchanged)."""
    s = rep.get("summary") or {}
    parts = []
    if rep.get("descriptive_only"):
        parts.append("descriptive only (no --reference: no FLAG verdict)")
    else:
        parts.append(f"FLAG {rep.get('FLAG')}, SEVERE {rep.get('SEVERE')}")
        md = (rep.get("paired_vs_reference") or {}).get("median_deficit")
        if isinstance(md, (list, tuple)) and len(md) == 3 and all(isinstance(x, (int, float)) for x in md):
            parts.append(f"median deficit vs reference {md[0]:.2f} [{md[1]:.2f}, {md[2]:.2f}] nats")
    cf = s.get("censored_frac")
    if isinstance(cf, (int, float)):
        parts.append(f"censored {100 * cf:.0f}% (margins are lower bounds there)")
    return "; ".join(parts)
