# PREREG_v2.8 — does the released TranscriptLab CLI reproduce the registered benchmark result?

Written 2026-11-06 ~17:45 UTC by the PI, before any v2.8 job. The user offered GPU6 at ~17:25. Frozen when its
sha256 and the analysis script's sha256 are written to PROGRESS.md.

## 1. Question and why
A practitioner who installs TranscriptLab runs `transcriptlab run` on Gemma-4-31B 4-bit and expects the paper's number.
- The test-retest runs of PREREG_v2.7 (RSA/RSB) call the frozen runner directly, with **new** seeds.
- This run goes through the **released CLI wrapper** (release/transcriptlab, version 0.1.0), with its default arguments
  and therefore the registered per-state seeds.

It checks the whole user path: state selection, job-list writing, the frozen runner as a subprocess, and the report.

Pre-checks (CPU, done before freezing):
- `transcriptlab run --dry-run` writes 1,200 jobs. They are identical, job for job and in order, to
  plan_bf16_core_full.jsonl (C1's plan) except the `tier` label ("transcriptlab" vs "A1bf16").
- The frozen runner's seed is md5(context id) + seed_offset. The tier label does not enter the seed; it only groups
  execution order.
- `transcriptlab verify`: 4/4 frozen files match.

## 2. Run (R-CLI)
- **Server.** vLLM 0.19.1 on GPU6, port 8376. Gemma-4-31B QAT-ct (models/gemma-4-31b-it-qat-w4a16-ct) with C1's server
  arguments: tools/serve_vllm.sh defaults (max-model-len 32768, gpu-mem 0.90, prefix caching, max-logprobs 20) plus
  `--max-num-seqs 64 --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4`.
- **Command, from release/transcriptlab:**

  ```bash
  TRANSCRIPTLAB_ROOT=. python -m transcriptlab run --base http://127.0.0.1:8376/v1 \
      --model gemma-4-31b --tokenizer <QAT-ct dir> --pool A1 --arms P0,P1,P6,P8a \
      --out experiments/transcriptlab_cli/run_v28 --python /opt/envs/env_gemma/bin/python
  ```

  Then `transcriptlab report experiments/transcriptlab_cli/run_v28`. Everything else is a CLI default: conc 20 and the
  default --max-model-len.
- **One resume pass** if any job has a transient error, as in C1 (the runner skips jobs already done).

## 3. Comparator
C1 = PREREG_v2 confirmatory 31B run (experiments/contagion/out/main/rC31b_v2.jsonl). Registered values:
- P0 1.33%, P1 19.67%;
- copying RD(P1 − P0) +18.33 pp [13.61, 23.16];
- removal by quarantine 0.98.

## 4. Analysis (experiments/contagion/scripts/analyze_v28_cli.py, frozen with this document)
- **Statistics.** The functions of analyze_v27_robustness.py (frozen f68bc12d), copied verbatim: the judge indicator
  y(), task-cluster multinomial bootstrap (B = 2000, seed 20261106), exact McNemar, rate/flip/removal/induction.
- **Computed:** CLI rates per arm, copying, induction and removal.
- **Agreement with C1:**
  - P1 contrast CLI − C1 with a two-sided exact McNemar p;
  - share of jobs with the same judged outcome;
  - share of jobs whose generated text (s1_text + s2_text) is byte-identical. Descriptive: vLLM sampling is not
    bit-reproducible across batch compositions.
- **Verdict.**
  - **CLI REPRODUCES** iff all three hold:
    - (a) the CLI copying RD point estimate lies inside C1's registered 95% CI [0.1361, 0.2316];
    - (b) the CLI removal point estimate is ≥ 0.90;
    - (c) the two-sided exact McNemar for P1 (CLI vs C1) has p ≥ 0.05.
  - Otherwise **DOES NOT REPRODUCE**, with the failing condition(s) named.
- **Predictions:** CLI P1 ≈ 19.7% [14, 25]; copying RD ≈ +18 pp; removal ≈ 1.0; identical texts 20–90% (wide, because
  vLLM batch effects are unknown).

## 5. What gets written
- If REPRODUCES:
  - REPRODUCE.md and RESULTS.md: "Running the released CLI on Gemma-4-31B 4-bit gives copying RD X [CI] (registered
    +18.3 [13.6, 23.2]); quarantine removes Y."
  - The paper only if the word budget allows.
- If not, the failing numbers go into LIMITATIONS.md, with the job-level agreement.

## 6. Deviations
Logged in PREREG_DEVIATIONS.md (v2.8 section) with UTC time and before/after-data status.
