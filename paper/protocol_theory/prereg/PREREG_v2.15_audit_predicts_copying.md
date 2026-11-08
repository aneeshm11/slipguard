# PREREG_v2.15 — does the weight audit's deficit predict TranscriptLab copying out of sample? Seven 31B checkpoints

Written by the PI on 2026-11-08 ~10:00 UTC, before any v2.15 job and before the E_audit analysis (blind until 14:00).
Freeze time and sha256s are in PROGRESS.md. Compute: the user's grant ("You can keep using the 6 GPUs for the next 18 hours").

## 1. Why
- The audit (`slipguard audit-weights`) ranks checkpoints by the log-probability margin they lose on the true string closer (median deficit, nats, vs bf16).
- PREREG_v2.6 showed the ordering bf16 < AWQ < AutoRound < QAT on TranscriptLab P1 (ρ = 1.0, exact one-sided p = 0.042; descriptive) over four checkpoints that had all been audited beforehand.
- PREREG_v2.10 then audited three more 31B checkpoints, the most-downloaded unaudited ones, but none has TranscriptLab data:

  | checkpoint | deficit (nats) | flag |
  |---|---|---|
  | nvidia NVFP4 | 1.36 | not flagged |
  | QAT-AWQ (cyankiwi) | 6.00 | flagged |
  | QAT-NVFP4 (melcheikh) | 7.41 | flagged |

  Their deficits were measured before any of their behaviour, so they are an out-of-sample test of whether the audit predicts copying.

## 2. Runs (three new; released CLI 0.1.3, registered gemma4 path, as C1)
- **Command, for each checkpoint:**

  ```bash
  transcriptlab run --base … --model gemma-4-31b --tokenizer models/gemma-4-31b-it-qat-w4a16-ct --pool A1 \
      --arms P0,P1,P6,P8a --out experiments/transcriptlab_cli/run_v215_<ckpt> --python env_gemma
  ```

  - All tokenizers are identical (tokenizer.json sha cc8d3a0c). Prompts are rendered from the corpus template, as for C1.
  - Registered corpus and seeds. One resume pass; `report`.
- **Servers:** vLLM 0.19.1, one GPU each, exactly the E_audit lanes' arguments (ext/dispatch_q.sh start_srv): `--dtype bfloat16 --max-num-seqs 64 --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'` plus the gemma4 parsers. Ports 8385/8386.
- **Placement:** GPUs 4 and 5 after PREREG_v2.14 finishes. QAT-AWQ on GPU 4 and QAT-NVFP4 on GPU 5, then nvidia NVFP4 on whichever frees first. Each GPU passes the user's gate for 2 min.
- **Guard:** > 5% error records after the first pass → that checkpoint is NOT RUN (cause logged), and the panel drops it.

## 3. Analysis (experiments/v215/analyze_v215.py, frozen now; run once, after all three runs end)
Statistics block copied verbatim from analyze_v27_robustness.py (f68bc12d): judge indicator (malformed edit), task-cluster bootstrap B = 2000, exact McNemar.
- **Panel (7 checkpoints):**

  | checkpoint | deficit | data |
  |---|---|---|
  | bf16 | 0 | PREREG_v2.14's run if it produced an analysis; otherwise out/main/rCbf16_v2.jsonl |
  | AWQ (bf16-derived) | 0.02 | v2.6 out/main/rCawq_v26.jsonl |
  | AutoRound | 0.63 | v2.6 rCautoround_v26.jsonl |
  | nvidia NVFP4 | 1.36 | new |
  | QAT | 5.13 | C1 rC31b_v2.jsonl |
  | QAT-AWQ | 6.00 | new |
  | QAT-NVFP4 | 7.41 | new |

  Deficits come from the audit outputs that prereg_E_audit_analysis.py reads (sweep_report.json, audit_v210_*.json), plus v2.6's.
- **Primary:** Spearman ρ between deficit and P1 (malformed next edit after the laundered edit + error) over the panel. Exact one-sided permutation p over all orderings, with average ranks for ties. **AUDIT PREDICTS COPYING iff ρ > 0 and p < 0.05.** Otherwise NOT SHOWN.
- **Secondary, out of sample (the three new checkpoints only), each an exact one-sided McNemar on the same states, reported without adjustment:**
  - (S1) QAT-AWQ P1 > bf16 P1;
  - (S2) QAT-NVFP4 P1 > bf16 P1;
  - (S3) nvidia NVFP4 P1 < QAT P1.
- **Descriptive:**
  - copying RD per checkpoint;
  - ρ with copying RD instead of P1;
  - imitation;
  - quarantine removal per checkpoint.

## 4. Predictions
| endpoint | prediction |
|---|---|
| primary | AUDIT PREDICTS COPYING, ρ ≈ 0.8–0.95 |
| QAT-AWQ P1 | ≈ 18–22% |
| QAT-NVFP4 P1 | ≈ 18–25% |
| nvidia NVFP4 P1 | ≈ 9–13% |
| S1–S3 | all met |
| QAT-NVFP4 vs QAT-AWQ | not predicted (deficits close) |

## 5. What gets written
- Docs (RESULTS, LIMITATIONS §6).
- One clause in the paper's §4 Weight audit if the budget allows.
- A failure is reported as one.
