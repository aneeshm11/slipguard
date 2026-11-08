# PREREG_E_awq — does serving the audit's pick reduce malformed calls end to end?

Written by the PI on 2026-11-06 (freeze time and sha256s in PROGRESS.md), before any E_awq episode. It extends
PREREG_E: the harness, proxy, sub, tasks and arms are unchanged, and only the served weights differ. Compute: GPU6
(user, "all GPUs for 48 h").

## 1. Why
- `slipguard audit-weights` flags Google's QAT checkpoint (deficit 5.13 nats) and recommends the cyankiwi AWQ checkpoint
  (0.02).
- On TranscriptLab states, the AWQ checkpoint cuts post-slip contagion: 19.7% → 10.3% (PREREG_v2.6), and 12.0% when
  served in bf16 (PREREG_v2.7 D1).
- Nothing yet shows that the pick matters in the agent loop. This run tests it end to end.

## 2. Design
- **Weights:** models/community/cyankiwi_gemma-4-31B-it-AWQ-4bit (rev a6b1af08, as in v2.6).
- **Server:** vLLM 0.19.1 on GPU6, port 8306.
  - `--dtype bfloat16`, matched to QAT, as in v2.7 D1.
  - Text-only `--hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'`.
  - `--max-num-seqs 64` and the gemma4 tool/reasoning parsers.
  - Served name `gemma-4-31b`, identical to the QAT runs.
- **Proxy model directory:** the QAT-ct directory (models/gemma-4-31b-it-qat-w4a16-ct), for the tokenizer and chat
  template. The prompts are therefore byte-identical to the QAT runs' rendering, and only the weights behind the
  backend differ.
- **Two replicates** of the 113 eligible tasks × {base, fullp}, as four half-lanes run in sequence on GPU6. Launches
  use PREREG_E's frozen run_population.sh, then run_chain.sh, per-arm conc 3:
  - `popAWQr1s0` (proxy :8520) and `popAWQr1s1` (:8521), CRN salt `popAWQr1`;
  - `popAWQr2s0` (:8522) and `popAWQr2s1` (:8523), salt `popAWQr2`.
  - Two, not one, because the smoke test on QAT r1 vs r2 showed base Y1 varies 2.94 vs 2.01 between replicates
    (runaway loops are rare and heavy-tailed). Decided before any AWQ episode.
- **QAT comparator:** QAT `base` episodes from the registered and fresh 31B replicates, pooled.
  - Analysed: r1, r2 and PREREG_E_ext's final analysis set (r3..rK). They run in the same harness, with the same tasks
    and arms.
  - This is a task-paired comparison of different runs. It is not CRN-paired, because different weights give different
    generations regardless.

## 3. Endpoints (analysis/prereg_E_awq_analysis.py, frozen now; PREREG_E's frozen functions; fixed seeds)
- **Primary (P-awq).**
  - Statistic: Y1 (delivered malformed calls per episode), AWQ-base vs QAT-base. Task means over the replicates;
    paired over the 113 tasks.
  - Ratio with boot_ratio (seed 1); difference with boot_paired (seed 20261111).
  - **AUDIT PICK REDUCES MALFORMED CALLS END TO END** iff the difference CI upper bound is < 0.
  - Otherwise **NOT SHOWN**. The ratio is reported either way.
- **Secondary:**
  - S-a: AWQ-fullp vs AWQ-base Y1, with ratio and difference (seed 20261112). Is slipguard still useful on the good
    checkpoint?
  - S-b: AWQ-fullp vs QAT-fullp Y1 (seed 20261113), descriptive.
  - S-c: stuck episodes per arm.
  - S-d: resolve per arm, descriptive. With two AWQ replicates there is no NI claim.
- The analysis runs **once**: after all four AWQ half-lanes complete and PREREG_E_ext's analysis set is final (§4 there). If
  E_ext does not finish, the comparator is r1–r2 plus the E_ext replicates complete at Nov 8 14:00 UTC.

## 4. Predictions (before data)
| endpoint | prediction | basis |
|---|---|---|
| AWQ-base Y1 | ≈ 1.2–1.8 (QAT-base 2.47; ratio ≈ 0.5–0.7) | contagion is about halved on states |
| P-awq | REDUCES, probability ≈ 0.5 | runaway loops are rare and heavy-tailed; two AWQ replicates may not show it |
| S-a | fullp still cuts AWQ-base strongly (ratio ≤ 0.3) | |
| S-b | AWQ-fullp ≈ QAT-fullp (≈ 0.2–0.3) | |

## 5. What gets written
- If REDUCES: "End to end, serving the audit's pick lowers malformed calls per episode from 2.47 to X (ratio [CI])."
  Paper §4, word budget permitting; always in RESULTS and docs.
- If NOT SHOWN: the numbers go into LIMITATIONS as an honest null.

## 6. Deviations
Logged in experiments/endtoend/PREREG_DEVIATIONS.md under "E_awq".
