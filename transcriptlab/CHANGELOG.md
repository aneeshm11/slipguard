# Changelog

## 0.1.3 (2026-11-08)
* **`--corpus` accepts a directory.** It takes the PNC dataset root as downloaded (it finds
  `contexts/P-swebench-31b-S1-v1/manifest.json`), the S1 contexts directory, or the S1 `manifest.json`. Before, a directory
  crashed with `IsADirectoryError`, as a PI run hit on 2026-11-08 (PREREG_v2.11 deviation 1). Other paths now give a clear exit-2
  message. New test.
* **New hermes / qwen3_coder models whose tokenizer is not Qwen's now run correctly.** X's frozen runner was written
  for Qwen tokenizers:
  * it stops on `<|im_end|>` and `<|endoftext|>`;
  * it sends the rendered prompt, which already holds any BOS, with the server's default `add_special_tokens=true`.
  With Hermes-3-Llama-3.1-8B (a Llama-3.1 tokenizer), 0.1.2 sent a null stop id, so vLLM rejected all 1,200 requests
  (PREREG_v2.12 deviation 1). With that fixed, a live 3-state pilot showed two more problems: a second BOS token
  (ids 128000, 128000), and no stop on the model's `<|end_of_text|>`.
  For a new model only, the CLI's bootstrap now adapts each request:
  * the stop ids are the model's end tokens (eos, `<|im_end|>`, `<|endoftext|>`, `<|end_of_text|>`, `<|eot_id|>` where
    present, and `generation_config.json`'s eos ids);
  * when the prompt already starts with the tokenizer's BOS, it sends `add_special_tokens=false`.
  It prints what it did. The frozen runner is unchanged, and registered models never take this path; the golden tests
  still reproduce the registered runs. New test.

* README: the endpoint needs a context window of at least 32k tokens. An 8k model cannot be scored (PREREG_v2.13).

## 0.1.2 (2026-11-07)
Fixes from a clean-install review (R4 practitioner).
* **`report` honours `$TRANSCRIPTLAB_ROOT` and `--root`** (step 4.16). The root recorded in the run's
  `transcriptlab_run.json` used to override them, and every released run records `"."`, so `report` failed with
  "is not a TranscriptLab repository root" unless it ran from the repository root. Precedence now: `--root` >
  `$TRANSCRIPTLAB_ROOT` > the recorded root (only if absolute and still a repository) > the nearest parent of the run
  directory > the nearest parent of the cwd (`backends.resolve_root`). A missing `transcriptlab_run.json` is now a
  clear exit-2 message instead of a traceback. Regression tests.
* **Every command prints the root it uses** (`root: <path> (<how>)`; step 2.9): auto-discovery from the cwd is no
  longer silent.
* **Tests skip instead of failing without PNC** (step 3.4): the job-list, report and end-to-end tests need the PNC
  dataset because `run --dry-run` reads its manifest.
* README: the root order; the job list equals the registered plan except the `tier` label (step 4.15); TranscriptLab
  is a separate package; 19 tests.

## 0.1.1 (2026-11-06)
Fixes from a blind practitioner review.
* Outside the repository (the pip-only user) the CLI still exits with status 2, but the message now says what to do:
  run inside a clone of the repository or set `TRANSCRIPTLAB_ROOT` (or `--root`), and download the PNC dataset (about
  3 GB) to `<repository root>/data/pnc` or set `PNC_ROOT`. The README states this requirement up front. New test.
* README: `[run]` installs vLLM 0.19.1's CUDA build (torch and nvidia wheels), not a CPU wheel; the test count is
  16 (15 before this release's new test).
* Kept from 2026-11-06: `--python <venv>/bin/python` is made absolute without resolving the symlink, so the frozen
  scripts run with the venv's packages (`_interp`, with its test).

## 0.1.0 (2026-11-05)
First release: `run`, `report`, `estimate`, `verify`, `arms` over the frozen runners and analyses.
