# PREREG_E_awq2: is slipguard still useful on the audit's pick? Six fresh AWQ replicates

Written by the PI on 2026-11-07, after the PREREG_E_awq and PREREG_E_ext analyses (06:51 UTC) and before any E_awq2 episode. The freeze time and sha256s are in PROGRESS.md. Compute: GPUs 0, 1, 2 and 6 (user, "all GPUs for 48 h"; the user's gate applies to each one).

## 1. Why, and what is already known (disclosed)
- **PREREG_E_awq (2 AWQ replicates):** serving the audit's pick (cyankiwi AWQ, bf16) cut malformed calls per episode from 1.91 (QAT, 10 replicates) to 0.41. That is AUDIT PICK REDUCES, ratio 0.22 [0.11, 0.39].
- **Proxy on top (S-a, secondary):** 0.41 → 0.32, ratio 0.77 [0.44, 1.47], diff −0.09 [−0.39, +0.11]. Not significant; the prediction (ratio ≤ 0.3) failed.
- **The practical question:** on a good checkpoint, does slipguard's proxy still cut malformed calls end to end? Two replicates cannot answer it.
- **Blinding:** this test uses only fresh AWQ replicates (r3–r8). The r1–r2 numbers above have been seen and informed the predictions, and are not part of the primary test.

## 2. Design (PREREG_E_awq's harness, proxy, tasks, arms and server; only the replicate salts are new)
- **Weights and server:** models/community/cyankiwi_gemma-4-31B-it-AWQ-4bit (rev a6b1af08) on vLLM 0.19.1, with PREREG_E_awq's arguments:
  - `--dtype bfloat16 --max-num-seqs 64 --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4`;
  - served name `gemma-4-31b`;
  - proxy model directory = the QAT-ct directory (byte-identical prompts, as in E_awq).
- **Replicates popAWQr3 … popAWQr8 (6 fresh).** Each covers the 113 eligible tasks × {base, fullp} in the registered halves.
  - Lanes are popAWQr{k}s{h}, with CRN salt `popAWQr{k}`.
  - Launcher: PREREG_E's frozen run_population.sh (per-arm conc 3), unchanged.
  - Lanes start in replicate order on whichever GPU passes the gate.
  - Orchestration only: ext/dispatch_awq2.sh, frozen with this document. Proxy ports 8530+i; server port 8300+G; GPU6's server pinned to cores 112–115.
- **Sandboxes:** rootless dockerd on cores 150–175, as in E_ext; at most 4 lanes at once.
- **Blinding:** no resolve or malformed-call outcome is looked at before the analysis set is final. Allowed: completion counts, 5xx / tracebacks, infra errors.

## 3. Analysis set and stopping rule
- Replicate k is complete when both halves × both arms have a per_task line for every task of that half.
- **Analysis set r3 … rK:** K is the largest index such that every replicate r3..rK is complete. It is evaluated at the earlier of:
  1. all 6 complete;
  2. 2026-11-08 14:00 UTC.
- If K < 5 (fewer than 3 fresh replicates), the primary is reported as **UNDERPOWERED**.
- The analysis runs **once**. Lanes still running at the cutoff are stopped, and their partial data are not analysed.

## 4. Endpoints (analysis/prereg_E_awq2_analysis.py, frozen now)
It uses PREREG_E's frozen prereg_analysis.py functions unchanged, with explicit integer seeds. Episodes are paired by (task, replicate), and infra-error pairs are excluded, as in PREREG_E_ext.
- **Primary (P2):**
  - Statistic: Y1 (delivered malformed calls per episode), AWQ-fullp vs AWQ-base. Task means over the fresh replicates, paired over tasks.
  - Ratio fullp/base with boot_ratio (seed 1); difference with boot_paired (seed 20261114).
  - **SLIPGUARD STILL REDUCES MALFORMED CALLS ON THE AUDIT'S PICK** iff the difference CI upper bound is < 0; otherwise **NOT SHOWN**.
- **Secondary:**
  - S1: Y2 (wasted calls), same statistics, seed 20261115.
  - S2: stuck episodes, base vs fullp counts, with exact McNemar on paired episodes.
  - S3: resolve, fullp − base task-mean difference (boot_paired, seed 20261116). Descriptive, with NI at −3 pp reported but not claimed (6 replicates; no power analysis).
  - S4: replication of PREREG_E_awq's primary with fresh AWQ episodes only. AWQ-base (r3..rK) vs QAT-base (pop31 r1..r10), task means; boot_ratio seed 1, boot_paired seed 20261117. **REPLICATES** iff the diff CI upper bound is < 0.
- **Descriptive (sequential, labelled):** P2's statistic over all AWQ replicates (r1..rK), seed 20261118.

## 5. Predictions (before data)
| endpoint | prediction | basis |
|---|---|---|
| P2 | ratio ≈ 0.75; diff ≈ −0.1; SLIPGUARD STILL REDUCES with probability ≈ 0.4 | r1–r2: 0.77, −0.09 [−0.39, 0.11]; CI half-width ≈ 0.12–0.15 with 6 replicates |
| S2 | base ≈ 0.5% stuck, fullp ≈ 0 | r1–r2: 1/226 vs 0/226 |
| S3 | ≈ 0 pp | E_ext |
| S4 | REPLICATES, ratio ≈ 0.2–0.3 | E_awq |

## 6. What gets written
- **If P2 holds:** "On the audit's pick, slipguard's proxy still cuts malformed calls per episode, a → b (ratio r [CI], registered)."
- **If NOT SHOWN:** "On the audit's pick, the proxy's further cut was not shown (a → b, diff d [CI])." This goes in §6 / LIMITATIONS as the practical answer: on a good checkpoint, the proxy's end-to-end gain is small.
- Either way, the RESULTS and LIMITATIONS rows are written.

## 7. Deviations
Logged in experiments/endtoend/PREREG_DEVIATIONS.md under "E_awq2", with the UTC time and before/after-data status.
