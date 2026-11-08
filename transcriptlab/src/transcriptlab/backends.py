"""Where the frozen code and the public states live, which files are pinned, and the exact commands the CLI runs.

Nothing here re-implements a measurement. The CLI only:
  * picks the first N states of a public pool in rank order (the rule of the registered plans);
  * writes the job list / id list those frozen runners read;
  * runs the frozen runner and the frozen analysis as subprocesses, with their own arguments.

Two frozen pipelines are wrapped:
  gemma4   workstream A's runner (experiments/contagion/scripts/run_injection.py, PREREG_v2 hash list) and the
           core-arm analysis that produced the paper's bf16 row (analyze_bf16_core.py; P0/P1/P6/P8a; episode-cluster
           bootstrap; it also reports your model minus the registered Gemma-4-31B 4-bit run on the same states).
  hermes, qwen3_coder, harmony, mistral
           workstream X's format-general extension runner (experiments/crossfamily/scripts/ext_frozen/:
           prep_prompts_ext.py -> run_ext.py -> analyze.py; hashes in ext_frozen/SHA256SUMS).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

# ---- pinned files (sha256 at the freeze; A's list: experiments/contagion/out/confirmatory_script_hashes_v1.txt) ----
A_SCRIPTS = "experiments/contagion/scripts"
A_PINNED = {
    "run_injection.py": "1aadb39d5fe9013620e296b8ac213b19804f2cf3e4fb3457d99bcf42a707dde0",
    "variants.py": "b0044a723ac086e0194e2dc45dce74d0cd712327c3eb5798f23d2caf20079850",
    "gemma_protocol.py": "7cb2871b208be148087db21aff878e6f130851efece276257855e810e96f15cf",
    # not in A's PREREG_v2 list: the exploratory core-arm analysis, written before the bf16 outputs existed; it
    # reproduces experiments/contagion/out/confirmatory/bf16_core_all.json byte-for-byte from the bf16 run.
    "analyze_bf16_core.py": "7d3bf05bfe7a3956c9a4aa25229873a3280318b6405eb0ccd7970b21c9898b7b",
}
X_FROZEN = "experiments/crossfamily/scripts/ext_frozen"
POOLS = "experiments/contagion/data/confirmatory/pools"
META_S1 = "experiments/contagion/data/confirmatory/meta_S1.jsonl"
CORPUS_S1 = "data/pnc/contexts/P-swebench-31b-S1-v1"
REGISTERED_QAT_RUN = "experiments/contagion/out/main/rC31b_v2.jsonl"   # read by the gemma4 analysis (comparison row)

FORMATS = ("gemma4", "hermes", "qwen3_coder", "harmony", "mistral")
X_FMT = {"hermes": "hermes", "qwen3_coder": "xml", "harmony": "harmony", "mistral": "mistral"}   # X's internal names
GEMMA_ARMS = ("P0", "P1", "P6", "P8a")            # the core set the gemma4 analysis covers
X_ARMS = ("P0", "P1", "P1N", "P5", "P6", "P8a")   # X's battery arms (P1 = X's P1L, the same construction)
ARM_HELP = {
    "P0": "original history",
    "P1": "the latest valid edit replaced by its laundered form + the framework's missing-parameter error (copying)",
    "P1N": "a native single-closer slip in the model's own syntax (X formats only)",
    "P5": "the edit removed, with a note (X formats only)",
    "P6": "laundered edit + its original success response (induction)",
    "P8a": "laundered edit + error, then slipguard's frozen history quarantine",
}
MAX_NEW = 7168          # max new tokens per generation in both runners
THINK_BUDGET = 4096     # thinking budget; a longer thought costs one extra continuation request


class SetupError(RuntimeError):
    pass


TREE_HINT = ("The pip package contains only this CLI: the frozen runners, the public states and the analysis live in "
             "the TranscriptLab repository. Run the command inside a clone of the repository, or set "
             "TRANSCRIPTLAB_ROOT=<repository root> (or pass --root). `run` also needs the PNC dataset (about 3 GB, "
             "https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc) at <repository root>/data/pnc, or set PNC_ROOT to where it is.")


def _is_root(p: Path) -> bool:
    return (p / A_SCRIPTS / "run_injection.py").exists() or (p / X_FROZEN / "run_ext.py").exists()


def _nearest_root(start: Path) -> Path | None:
    p = Path(start).resolve()
    for q in (p, *p.parents):
        if (q / A_SCRIPTS / "run_injection.py").exists():
            return q
    return None


def resolve_root(explicit: str | None = None, *, recorded: str | None = None,
                 near: Path | None = None) -> tuple[Path, str]:
    """(root, how it was found). Precedence:
      1. --root (``explicit``);
      2. $TRANSCRIPTLAB_ROOT;
      3. ``recorded``: the root a run directory's transcriptlab_run.json records, only if it is absolute and still a
         TranscriptLab root (released runs record a relative "." that names no directory, so it is never used);
      4. the nearest parent of ``near`` (the run directory) that holds the frozen runners;
      5. the nearest parent of the cwd that holds them.
    An explicit --root or $TRANSCRIPTLAB_ROOT that is not a root is an error (never silently replaced)."""
    for value, how in ((explicit, "--root"), (os.environ.get("TRANSCRIPTLAB_ROOT"), "$TRANSCRIPTLAB_ROOT")):
        if value:
            p = Path(value).resolve()
            if _is_root(p):
                return p, how
            raise SetupError(f"{p} ({how}) is not a TranscriptLab repository root (it has neither "
                             f"{A_SCRIPTS}/run_injection.py nor {X_FROZEN}/run_ext.py). " + TREE_HINT)
    if recorded and Path(recorded).is_absolute() and _is_root(Path(recorded)):
        return Path(recorded).resolve(), "recorded in the run's transcriptlab_run.json"
    if near is not None:
        q = _nearest_root(near)
        if q is not None:
            return q, "nearest parent of the run directory"
    q = _nearest_root(Path.cwd())
    if q is not None:
        return q, "nearest parent of the cwd"
    raise SetupError(f"cannot find the TranscriptLab repository from {Path.cwd().resolve()}. " + TREE_HINT)


def find_root(explicit: str | None = None) -> Path:
    """--root, else $TRANSCRIPTLAB_ROOT, else the nearest parent of the cwd that holds the frozen runners."""
    return resolve_root(explicit)[0]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


EXPORT_PINS = "FROZEN_EXPORT_PINS.json"   # public tree: frozen sha256 -> exported sha256 of every rewritten file


def export_pins(root: Path) -> dict:
    """{tree path: {frozen_sha256, exported_sha256, ...}} from the public tree's FROZEN_EXPORT_PINS.json ({} in-project)."""
    f = root / EXPORT_PINS
    if not f.exists():
        return {}
    d = json.loads(f.read_text())
    return d.get("files", d)


def pin_status(rel: str, expected: str, actual: str | None, pins: dict) -> str:
    """'frozen' = the file is byte-identical to the freeze; 'exported' = the public tree's path-rewritten export of exactly
    that frozen file (the export record names the same frozen sha256 and the file has the recorded exported sha256);
    'MISSING' / 'DIFF' otherwise. Any other change fails."""
    if actual is None:
        return "MISSING"
    if actual == expected:
        return "frozen"
    e = pins.get(rel)
    if e and e.get("frozen_sha256") == expected and e.get("exported_sha256") == actual:
        return "exported"
    return "DIFF"


def check_pinned(root: Path, fmt: str) -> list[dict]:
    """[{file, expected, actual, status, ok}] for every frozen file the chosen pipeline executes."""
    pins = export_pins(root)
    if fmt == "gemma4":
        todo = [(f"{A_SCRIPTS}/{name}", exp) for name, exp in A_PINNED.items()]
    else:
        todo = []
        for line in (root / X_FROZEN / "SHA256SUMS").read_text().splitlines():
            if line.strip():
                exp, name = line.split(None, 1)
                todo.append((f"{X_FROZEN}/{name.strip()}", exp))
    rows = []
    for rel, exp in todo:
        p = root / rel
        act = sha256(p) if p.exists() else None
        st = pin_status(rel, exp, act, pins)
        rows.append({"file": rel, "expected": exp, "actual": act, "status": st, "ok": st in ("frozen", "exported")})
    return rows


def pool_states(root: Path, pool: str, n: int) -> list[dict]:
    """first n states of pool S1_<pool> in rank order (the rule of ext_prepare.py and the registered plans)."""
    f = root / POOLS / f"S1_{pool}.jsonl"
    if not f.exists():
        raise SetupError(f"pool file missing: {f}")
    with open(f) as fh:
        rows = [json.loads(line) for line in fh]
    if [r["rank"] for r in rows] != list(range(1, len(rows) + 1)):
        raise SetupError(f"{f}: not in rank order")
    if n > len(rows):
        raise SetupError(f"pool {pool} has {len(rows)} states, asked for {n}")
    return rows[:n]


def corpus_manifest(root: Path, explicit: str | None = None) -> Path:
    """--corpus, else $PNC_ROOT/contexts/..., else <root>/data/pnc/contexts/..., else POOLS_MANIFEST's record (a relative
    path there is resolved against the root)."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if p.is_dir():   # the dataset root (as downloaded) or its S1 contexts directory
            for c in (p / "manifest.json", p / "contexts" / Path(CORPUS_S1).name / "manifest.json"):
                if c.is_file():
                    return c
            raise SetupError(f"--corpus {p} is a directory without manifest.json or contexts/{Path(CORPUS_S1).name}/"
                             "manifest.json; pass the PNC dataset root, its S1 contexts directory, or the S1 manifest.json")
        if not p.is_file():
            raise SetupError(f"--corpus {p} does not exist")
        return p
    cands = []
    if os.environ.get("PNC_ROOT"):
        cands.append(Path(os.environ["PNC_ROOT"]) / "contexts" / Path(CORPUS_S1).name / "manifest.json")
    cands.append(root / CORPUS_S1 / "manifest.json")
    pm = json.loads((root / POOLS / "POOLS_MANIFEST.json").read_text())
    q = Path(pm["S1"]["corpus_manifest"])
    cands.append(q if q.is_absolute() else root / q)
    for c in cands:
        if c.exists():
            return c.resolve()
    raise SetupError(f"PNC S1 manifest not found (looked at {', '.join(map(str, cands))}); pass --corpus "
                     "<.../manifest.json> or set PNC_ROOT to the dataset directory")


def parse_arms(spec: str, fmt: str) -> list[str]:
    arms = [a.strip() for a in spec.split(",") if a.strip()]
    allowed = GEMMA_ARMS if fmt == "gemma4" else X_ARMS
    bad = [a for a in arms if a not in allowed]
    if bad:
        raise SetupError(f"arms {bad} are not available for format {fmt}; allowed: {','.join(allowed)}")
    if "P0" not in arms:
        raise SetupError("P0 (original history) is the reference of every contrast; include it")
    if fmt == "gemma4" and sorted(arms) != sorted(GEMMA_ARMS):
        raise SetupError("the gemma4 analysis covers exactly the core set P0,P1,P6,P8a (pass --arms P0,P1,P6,P8a); "
                         "other arm sets run through the registered PREREG_v2 pipeline (experiments/contagion/README.md)")
    return arms


def gemma_plan(states: list[dict], arms: list[str]) -> list[dict]:
    """job lines read by run_injection.py: k = 0 for the original history, 1 for one edited past action."""
    return [{"id": s["context_id"], "pathway": a, "k": 0 if a == "P0" else 1, "tier": "transcriptlab",
             "rank": s["rank"], "half": s.get("half")} for s in states for a in arms]


def x_arm(a: str) -> str:
    return "P1L" if a == "P1" else a


def estimate(n_states: int, arms: list[str]) -> dict:
    n = n_states * len(arms)
    return {"states": n_states, "arms": len(arms), "generations": n,
            "max_new_tokens_per_generation": MAX_NEW, "upper_bound_new_tokens": n * MAX_NEW,
            "note": (f"one generation per (state, arm); a thought longer than {THINK_BUDGET} tokens is cut and "
                     "continued with one extra request (as the registered runs did)")}


def reference_usage(root: Path, arms: list[str], ids: set[str]) -> dict | None:
    """mean prompt / generated tokens of the registered Gemma-4-31B 4-bit run on the same states and arms (for the
    cost line only; never used by any analysis)."""
    f = root / REGISTERED_QAT_RUN
    if not f.exists():
        return None
    npr, ngen, n = 0, 0, 0
    want = {(a, 0 if a == "P0" else 1) for a in arms}
    with open(f) as fh:
        for line in fh:
            d = json.loads(line)
            if d.get("error") or d["id"] not in ids or (d["pathway"], d["k"]) not in want:
                continue
            npr += d.get("n_prompt") or 0
            ngen += d.get("s1_tokens") or 0
            n += 1
    if not n:
        return None
    return {"jobs": n, "mean_prompt_tokens": round(npr / n), "mean_generated_tokens": round(ngen / n),
            "source": REGISTERED_QAT_RUN}


def _resolve(root: Path, p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else root / q


def localized_meta(root: Path, manifest: Path, out_dir: Path, meta: Path | None = None) -> tuple[Path, bool]:
    """The runner opens two paths from every meta record (contexts_file, template_path): absolute in-project,
    repo-relative in the public tree. If they resolve (relative ones against the root, which is the runner's working
    directory), the meta file is used as is (no copy). Otherwise (dataset mounted elsewhere) write
    <out_dir>/meta_local.jsonl with only those two fields re-pointed into the corpus directory; every other field of
    each record is unchanged."""
    meta = meta or (root / META_S1)
    with open(meta) as f:
        first = json.loads(f.readline())
    if _resolve(root, first["contexts_file"]).exists() and _resolve(root, first["template_path"]).exists():
        return meta, False
    cdir = manifest.parent
    dst = out_dir / "meta_local.jsonl"
    with open(meta) as f, open(dst, "w") as fo:
        for line in f:
            d = json.loads(line)
            d["contexts_file"] = str(cdir / Path(d["contexts_file"]).name)
            d["template_path"] = str(cdir / Path(d["template_path"]).name)
            fo.write(json.dumps(d, ensure_ascii=False) + "\n")
    return dst, True
