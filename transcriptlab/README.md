# transcriptlab (CLI)

This is the **benchmark**, not the library. It measures a model; it does not protect an agent (for that, use
slipguard, `../slipguard/`). TranscriptLab works on any model, Gemma or not.

Run the TranscriptLab benchmark on your own model with one command. The benchmark edits one past action of a real
agent state from the public PNC corpus, then measures how often the model's next call is a malformed edit.

**Requirements.** The pip package contains only this CLI. The frozen runners, the public states and the analysis live
in this repository (https://github.com/aneeshm11/slipguard, which also holds slipguard), so every command except `arms` must run inside a clone of the repository, or with
`TRANSCRIPTLAB_ROOT` set to its root (or `--root`). Outside it, the CLI exits with status 2 and says so. `run` also
needs the PNC dataset (about 3 GB, https://www.kaggle.com/datasets/cassinicraft/slipguard-pnc) at `<repository root>/data/pnc`; set `PNC_ROOT` if it is
elsewhere. TranscriptLab is its own package: installing slipguard does not install it.

**Which root is used.** Every command prints `root: <path> (<how it was found>)` first. The order is `--root`, then
`$TRANSCRIPTLAB_ROOT`, then (for `report`) the root recorded in the run's `transcriptlab_run.json` if it is an
absolute path that still holds the repository, then the nearest parent of the run directory, then the nearest parent
of the current directory. The released runs record the root as `.`, which is never used; for them, set
`TRANSCRIPTLAB_ROOT` (or `--root`) or keep the run inside the repository.

```bash
pip install "./transcriptlab[run]"         # CLI itself is stdlib-only; [run] = httpx, numpy, transformers, vLLM 0.19.1
export TRANSCRIPTLAB_ROOT=/path/to/the/repository

transcriptlab run --base http://HOST:PORT/v1 --model gemma-4-31b --tokenizer google/gemma-4-31b-it \
                  --pool A1 --arms P0,P1,P6,P8a --out runs/my-gemma
transcriptlab report runs/my-gemma
```

`vllm==0.19.1` from PyPI is vLLM's CUDA build: `[run]` pulls torch 2.10, triton, flashinfer and about 20
`nvidia-*-cu12` wheels (several GB), although the runner only uses vLLM's parsers and judge on the CPU.

**Cost.** `run` prints the cost before it starts. The registered battery is 300 states × 4 arms = **1,200
generations**. Each generation has at most 7,168 new tokens. A thought longer than 4,096 tokens costs one extra
continuation request. On the same jobs, the registered Gemma-4-31B 4-bit run averaged about 16.2k prompt tokens and
360 generated tokens per job. Check the cost first with `transcriptlab estimate`, or try a pilot with
`--limit-states 10`.

**The endpoint.** Any OpenAI-compatible `/v1/completions` server works if it accepts the following, as `vllm serve`
does:
- raw prompts with special tokens;
- vLLM's sampling extras (`seed`, `top_k`, `stop_token_ids`, `skip_special_tokens`).
- **a context window of at least 32k tokens** (24k of history plus up to 7,168 new tokens). The A1 states run to
  about 18k prompt tokens with a Llama-3 tokenizer and 24k with Gemma's. A model limited to 8k, e.g. Hermes-2-Pro-Llama-3-8B,
  cannot be scored (PREREG_v2.13: not run).

No server-side tool or reasoning parser is used, because the frozen runner parses offline.

## What it runs (no new measurement code)

| format | runner and analysis (frozen; sha256 checked by `transcriptlab verify`) |
|---|---|
| `gemma4` (default) | Workstream A's `experiments/contagion/scripts/run_injection.py` (PREREG_v2 hash list) and `analyze_bf16_core.py`. The analysis covers arms P0/P1/P6/P8a with episode-cluster bootstrap CIs (B = 2,000). It reproduces the paper's bf16 row byte-for-byte. |
| `hermes`, `qwen3_coder`, `harmony`, `mistral` | Workstream X's `experiments/crossfamily/scripts/ext_frozen/`: `prep_prompts_ext.py`, then `run_ext.py`, then `analyze.py` (`SHA256SUMS`). |

The CLI does three things:
1. It picks the first N states of the pool in rank order. This is the rule of the registered plans: the job list for
   the default call equals `plan_bf16_core_full.jsonl` except the `tier` label of each job (`transcriptlab` instead
   of `A1bf16`; the runner does not read it), and the id list equals X's `ids_A1.txt`.
2. It writes the job list.
3. It runs the frozen scripts unchanged, as subprocesses.

**New models.** For a new `hermes` or `qwen3_coder` model, pass `--tokenizer`. The model is added to X's registry for
that run only, through a bootstrap that then executes the frozen script unchanged. For `harmony` and `mistral`, pass
one of the registered `--mk` keys, because their token-id rendering is model-specific.

## Arms

| arm | history |
|---|---|
| P0 | original |
| P1 | the latest valid edit is replaced by its laundered form, plus the framework's missing-parameter error (copying) |
| P6 | the laundered edit plus its original success response (induction) |
| P8a | as P1, then slipguard's frozen history quarantine |

X's formats also accept P1N (a native slip) and P5 (the edit removed, with a note).

## Output (`--out DIR`)

| file | contents |
|---|---|
| `transcriptlab_run.json` | config, commands, sha256 of every frozen file, corpus and pool hashes |
| `plan.jsonl` / `ids.txt` | the job list |
| `gen.jsonl` | one judged generation per job |
| `run.log` | runner log |
| `analysis.json` | the frozen analysis |
| `report.txt` | the printed table: per-arm rates, copying RD(P1 − P0), induction RD(P6 − P0) and quarantine removal, with CIs. For `gemma4` it also gives your model minus the registered Gemma-4-31B 4-bit run on the same states. |

The report prints estimates only. The registered verdict rules (thresholds, Holm) are in the preregistrations.

## Tests (CPU)

```bash
TRANSCRIPTLAB_ROOT=/path/to/repo python -B -m unittest discover -s transcriptlab/tests -v
```

Test outputs go to a fresh directory under the system temp dir (`$TMPDIR`) and are deleted at the end.
`-B` (or `PYTHONDONTWRITEBYTECODE=1`) keeps bytecode out of the tree; the frozen scripts the CLI starts never write
any. With pytest, use `python -B -m pytest -p no:cacheprovider transcriptlab/tests`.

In the public tree, the frozen scripts have their host paths rewritten to environment lookups. `verify` accepts such a
file only when `FROZEN_EXPORT_PINS.json` records exactly that export of exactly the pinned frozen file; any other
change fails. The state metadata's repo-relative paths resolve against `TRANSCRIPTLAB_ROOT`, with the dataset at
`<repo>/data/pnc`. If the dataset is mounted elsewhere, set `PNC_ROOT` or pass `--corpus`; `run` then writes a copy
of the metadata pointing there.

**A new model with a non-Qwen tokenizer** (e.g. a Llama-3.1 fine-tune in the hermes format) works since 0.1.3. X's frozen
runner was written for Qwen tokenizers, so for a new model the CLI adapts each request:
- it stops on the model's own end tokens;
- it sends `add_special_tokens=false` when the rendered prompt already starts with the tokenizer's BOS.
It prints what it changed. Registered models are untouched (see CHANGELOG 0.1.3).

There are 21 tests:
- **Unit tests:** arm rules, cost, job-list shape, report formatting, the interpreter of a virtualenv is kept as given
  (`--python`), the error message outside the repository, and the root precedence (`--root` and
  `$TRANSCRIPTLAB_ROOT` win over a run's recorded root; `report` on a run that records `.`)),
  `--corpus` given as a directory, and the request adapter for new models (below).
- **Tree tests:** `estimate`, pinned hashes, `verify` on a changed file, every command printing the root it uses.
- **Golden tests:** the job list equals the registered plan except the `tier` label (seeds depend only on the state id); `report` reproduces the paper's bf16 row and X's
  Qwen3-Coder-30B row from the released generations.
- **End-to-end tests against a mock `/v1/completions` server** (`tests/mock_backend.py`): a 3-state Gemma 4 pilot (12
  generations) through `run` and `report`, and a new hermes model through the registration path. In both, the frozen
  judge flags exactly the slipped calls the mock emitted.

A test skips itself, with the reason, when its inputs (states, the PNC dataset, tokenizer, vLLM wheel) are absent:
without PNC (`<root>/data/pnc` or `PNC_ROOT`) the job-list, report and end-to-end tests skip instead of failing.
