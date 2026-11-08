# PREREG_E_audit: does slipguard's weight audit predict malformed calls in the agent loop?

Written by the PI on 2026-11-07, before any E_audit episode. The freeze time and sha256s are in PROGRESS.md. It follows the user's instruction "Maximize GPU usage, be thorough in your experimental coverage". Compute: GPUs 0, 1, 2 and 6 after PREREG_E_awq2's lanes, each under the user's gate.

## 1. Why, and what is already known (disclosed)
`slipguard audit-weights` measured, for each checkpoint, how much log-probability margin it loses for the true string delimiter versus bf16 (the median deficit, in nats):

| checkpoint | deficit (nats) | audit flag | file |
|---|---|---|---|
| QAT | 5.13 | flagged | sweep_report.json |
| unquantized QAT | 5.5 | flagged | sweep_report.json |
| cyankiwi AWQ of the QAT weights (QAT-AWQ) | 6.00 | flagged | audit_v210 |
| melcheikh NVFP4 of the QAT weights (QAT-NVFP4) | 7.41 | flagged | audit_v210 |
| cyankiwi AWQ of bf16 | 0.02 | not flagged | sweep_report.json |
| nvidia NVFP4 of bf16 | 1.36 | not flagged | audit_v210 |

- **Measured end to end so far:**
  - QAT base: 1.91 malformed calls per episode (10 replicates);
  - AWQ base: 0.41 (PREREG_E_awq, 2 replicates; 6 more are running in PREREG_E_awq2).
- **This study** measures four more checkpoints in the same agent loop: bf16 itself, nvidia NVFP4, QAT-AWQ and QAT-NVFP4. It tests whether the audit's flags predict which checkpoints break agents.

## 2. Design (PREREG_E's harness, proxy, tasks and arms; only the served weights differ)
- **Checkpoints:**
  - bf16: models/gemma-4-31b-it, tensor parallel 2.
  - nvidia NVFP4: rev 4135a98a.
  - QAT-AWQ: cyankiwi qat-AWQ-INT4, rev b0af25ee.
  - QAT-NVFP4: melcheikh qat-NVFP4-Blackwell, rev 4f01d2c4.
  - These are the PREREG_v2.10 revisions, re-downloaded (tools/dl_eaudit.sh).
- **Servers:** vLLM 0.19.1, `--max-num-seqs 64` with the gemma4 tool and reasoning parsers.
  - Community checkpoints: `--dtype bfloat16` and text-only `--hf-overrides`, as in PREREG_E_awq.
  - bf16: tensor parallel 2 on one GPU pair (tools/serve_vllm_tp2.sh), as in the TranscriptLab bf16 row.
  - Served name `gemma-4-31b`; proxy model directory = QAT-ct (byte-identical prompts).
- **Replicates k = 3, 4 (then 5 for the single-GPU checkpoints if time allows).** Each covers 113 tasks × {base, fullp} in the registered halves.
  - Launcher: PREREG_E's frozen run_population.sh, per-arm conc 3.
  - **Seed salt `pop31r<k>`:** the same per-request seeds as PREREG_E_ext's QAT replicate k. Each episode is therefore paired by (task, salt) with a registered QAT episode.
- **Orchestration** (orchestration only; frozen with this document and PREREG_E_comp):
  - ext/dispatch_q.sh with ext/queue_single.txt (single-GPU lanes, shared with PREREG_E_comp) and ext/queue_tp.txt (bf16).
  - Lanes are claimed in queue order. No lane starts after 2026-11-08 11:30 UTC.
- **Sandboxes:** rootless dockerd on cores 150–175, at most 4 lanes at once.
- **Blinding:** no resolve or malformed-call outcome is looked at before the analysis sets are final. Allowed: completion counts and infra errors.

## 3. Analysis sets and stopping rule
- For each checkpoint c, the analysis set is r3..rK_c, where K_c is the largest index such that every replicate r3..rK_c of c is complete. Both halves × both arms must have a per_task line for every task.
- It is evaluated once, at the earlier of:
  1. every queued lane finished;
  2. 2026-11-08 14:00 UTC.
- Lanes still running at the cutoff are stopped and not analysed.
- If a checkpoint cannot be served (its server is not up within 40 min), it is reported as NOT SERVABLE, and its tests are reported as not run.
- **The AWQ comparator** is the complete popAWQ replicates (r1, r2 and PREREG_E_awq2's) at the same time.

## 4. Endpoints (analysis/prereg_E_audit_analysis.py + prereg_cov_common.py, frozen now)
Y1 = delivered malformed calls per episode, from PREREG_E's frozen functions. Infra-error episodes are excluded. Task means are taken over replicates.

- **Primary family (Holm over the tests that could run; α = 0.05; each test needs the predicted direction and Holm-adjusted p_boot < 0.05):**

  | test | contrast | predicted direction | comparator pairing |
  |---|---|---|---|
  | T1 | bf16 base vs QAT base | lower | (task, salt), same replicates |
  | T2 | nvidia NVFP4 base vs QAT base | lower (no flag) | (task, salt), same replicates |
  | T3 | QAT-AWQ base vs AWQ base | higher (flag) | task-paired across runs |
  | T4 | QAT-NVFP4 base vs AWQ base | higher (flag) | task-paired across runs |

  - Each test uses the paired task bootstrap (boot_paired; seed 20261121 for T1/T2 and 20261124 for T3/T4).
  - **AUDIT PREDICTS END-TO-END MALFORMED CALLS** iff all four pass; **PARTLY** (k of 4) otherwise; **NOT SHOWN** if none pass; **INCOMPLETE** if fewer than four could run.
- **Secondary:**
  - per checkpoint: fullp vs base, ratio and difference (seed 20261122). Is slipguard needed on this checkpoint?
  - stuck and resolved counts per arm;
  - resolve of base vs QAT base (seed 20261123, descriptive).
- **Descriptive:** Spearman rank correlation between audit deficit and base Y1 over every checkpoint with end-to-end data (the four new checkpoints, QAT r1–r10, AWQ).

## 5. Predictions (before data)
| endpoint | prediction | basis |
|---|---|---|
| bf16 base Y1 | 0.3–0.7 | AWQ of bf16 0.41; TranscriptLab copying in bf16 +9.0 pp vs +18.3 |
| nvidia NVFP4 base Y1 | 0.4–1.0 | deficit 1.36 |
| QAT-AWQ base Y1 | 1.5–2.5 | deficit 6.00 (≈ QAT) |
| QAT-NVFP4 base Y1 | 1.5–3.0 | deficit 7.41 |
| T1 | pass, p ≈ 0.9 | |
| T2 | pass, p ≈ 0.8 | |
| T3 | pass, p ≈ 0.8 | |
| T4 | pass, p ≈ 0.8 | |
| Spearman | ≥ 0.7 | |
| fullp vs base | ratio ≤ 0.3 on flagged checkpoints; small or n.s. on unflagged ones | E_awq S-a |

## 6. What gets written
- **If AUDIT PREDICTS:** "End to end, the audit's flags sorted the six checkpoints: flagged ones delivered a–b malformed calls per episode, unflagged ones c–d (registered)."
- **Otherwise:** the k-of-4 result, plainly. Failures go to §6 / LIMITATIONS.

## 7. Deviations
Logged in experiments/endtoend/PREREG_DEVIATIONS.md under "E_audit".
