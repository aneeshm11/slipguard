# PREREG_v2.16 — does copying follow the QAT weights rather than the 4-bit format? (TranscriptLab on the unquantized QAT weights, plus three bf16-derived exports)

Written by the PI on 2026-11-08 ~11:30 UTC, before any v2.16 job, before PREREG_v2.15's analysis and before the E_audit
analysis (blind until 14:00). Freeze time and sha256s are in PROGRESS.md. Compute: the user's 18-hour grant of GPUs 0–5.

## 1. Why
- The paper says "the loss follows the QAT weights, not the 4-bit format". Its support is weight-audit deficits: Google's unquantized QAT release loses 5.51 nats, about as much as the 4-bit QAT-ct (5.13), while bf16 exports lose 0.02–1.9.
- PREREG_v2.14 showed bf16 copies half as often as QAT-ct (P1 8.7% vs 19.7%).
- The behavioural test of "follows the QAT weights" is whether the unquantized QAT weights, served at bf16 precision with no quantization, copy like QAT-ct and more than bf16.
- Three bf16-derived exports already audited in the sweep, with no TranscriptLab data, extend PREREG_v2.15's panel (descriptively):

  | export | deficit (nats) |
  |---|---|
  | RedHat FP8-dynamic | 0.03 |
  | RedHat NVFP4 | 0.79 |
  | QuantTrio AWQ | 1.91 |

## 2. Runs (released CLI 0.1.3, registered gemma4 path; command, tokenizer and seeds as PREREG_v2.15)
- **Weights:** re-downloaded at the sweep's pinned revisions (DELETIONS.md):

  | checkpoint | revision |
  |---|---|
  | google/gemma-4-31b-it-qat-q4_0-unquantized | 1e4d8bee |
  | RedHatAI/gemma-4-31B-it-FP8-dynamic | d4ab4f57 |
  | RedHatAI/gemma-4-31B-it-NVFP4 | 5df75cca |
  | QuantTrio/gemma-4-31B-it-AWQ | 37cf6a07 |

- **qatunq:** TP2, served exactly as PREREG_v2.14's bf16 run (serve_vllm_tp2.sh, `--max-num-seqs 64`, gemma4 parsers, 32k).
- **The three exports:** one GPU each, served as PREREG_v2.15 (serve_vllm.sh, `--dtype bfloat16 --max-num-seqs 64 --hf-overrides` Gemma4ForCausalLM, gemma4 parsers, 32k).
- **Placement:**
  - GPU 4: FP8, then NVFP4-RedHat;
  - GPU 5: QuantTrio, after PREREG_v2.15's driver ends;
  - GPUs 0+1: qatunq, after the E_audit/E_comp single dispatcher reports done.
  - Every GPU passes the user's gate for 2 min.
- **Guards:** > 5% error records after the first pass, or a server not up within 40 min → that checkpoint is NOT RUN (cause logged).

## 3. Analysis (experiments/v216/analyze_v216.py, frozen now; run once, after all four runs end)
Statistics block copied verbatim from analyze_v27_robustness.py (f68bc12d).
- **Primary (H1):** COPYING FOLLOWS THE QAT WEIGHTS iff qatunq P1 > bf16 P1 (PREREG_v2.14's run) on the same states, exact one-sided McNemar p < 0.05. Otherwise NOT SHOWN.
- **Secondary (H2, descriptive with a pre-set reading):**
  - qatunq P1 − QAT-ct P1, with the bootstrap CI and the two-sided McNemar;
  - "THE 4-BIT FORMAT ADDS LITTLE" if that 95% CI lies inside [−6, +6] pp; "THE FORMAT MATTERS" if it excludes 0; otherwise INCONCLUSIVE.
- **Descriptive:**
  - the extended panel (every checkpoint with TranscriptLab data at these settings: PREREG_v2.15's 7 + these 4);
  - Spearman ρ(deficit, P1) with the exact permutation p (or 200,000 random permutations if the panel exceeds 9);
  - copying RD, imitation and removal for the four new runs.

## 4. Predictions
| endpoint | prediction |
|---|---|
| H1 | met; qatunq P1 ≈ 17–22% |
| H2 | the 4-bit format adds little (qatunq ≈ QAT-ct) |
| FP8-RedHat P1 | ≈ 8–11% |
| NVFP4-RedHat P1 | ≈ 9–13% |
| QuantTrio P1 | ≈ 10–15% |
| extended-panel ρ | ≥ 0.8 |

## 5. What gets written
- §4 Weight audit (if the budget allows): one clause.
- Docs: RESULTS, LIMITATIONS §6.
- Failures are reported as failures.
