# PREREG_v2.10 — weight audit of the most-downloaded Gemma-4-31B 4-bit checkpoints, with the shipped `slipguard audit-weights`

Written by the PI on 2026-11-06 (freeze time and sha256s in PROGRESS.md), before any v2.10 audit number. The downloads
started earlier; they carry no outcome data. Compute: all free GPUs for 48 h (user, ~17:45 UTC).

## 1. Questions
- **Q1 (practitioner, descriptive).** The sweep (SWEEP_PLAN) audited 12 checkpoints. Here the *shipped* CLI audits the
  five most-used vLLM-servable 31B checkpoints not yet covered (Hugging Face downloads at writing):

  | checkpoint | downloads | revision |
  |---|---|---|
  | nvidia/Gemma-4-31B-IT-NVFP4 | 1.14M | 4135a98a |
  | melcheikh/gemma-4-31B-it-qat-NVFP4-Blackwell | 0.76M | 4f01d2c4 |
  | unsloth/gemma-4-31B-it-unsloth-bnb-4bit | 21k | 8e256fc6 |
  | unsloth/gemma-4-31B-it-NVFP4 | 23k | 373c00b5 |
  | cyankiwi/gemma-4-31B-it-qat-AWQ-INT4 | 12k | b0af25ee |

- **Q2 (mechanism, registered hypothesis H-QAT).** Google's unquantized QAT weights already show the largest deficit
  (6.00 nats uncensored; 31b_qatunq). If the QAT damage lives in the trained weights rather than in 4-bit storage, a
  checkpoint re-quantized FROM the QAT weights should be damaged too, whatever the quantizer. Two checkpoints are
  derived from QAT weights: cyankiwi's AWQ of them (cyankiwi's AWQ of the bf16 weights showed none, 0.02) and
  melcheikh's NVFP4 of them.
  - **H-QAT SUPPORTED** iff cyankiwi QAT-AWQ's median deficit is ≥ 3 nats (the audit's FLAG threshold).
  - **NOT SUPPORTED** iff it is < 3 nats with the CI upper bound < 3.
  - Otherwise **INCONCLUSIVE**.
  - melcheikh QAT-NVFP4 is reported as a second, descriptive instance.

## 2. Method (identical to the sweep; shipped code)
- **Server.** vLLM 0.19.1 on one H100, text-only (`--hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'`),
  tools/serve_vllm.sh defaults (max-model-len 32768, gpu-mem 0.90, prefix caching, max-logprobs 20), `--max-num-seqs
  32`, quantization auto-detected from the checkpoint. If a checkpoint does not load or serve on H100 with vLLM 0.19.1,
  it is recorded as **NOT SERVABLE** with the error. Nothing is patched (the sweep's rule).
- **Audit.** `slipguard audit-weights --endpoint … --served-name … --pnc data/pnc --tokenizer models/gemma-4-31b-it
  --records … --reference experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out … --conc 2`.
  - Defaults: pack audit16k, split heldout (235 items, 454 string ends): the sweep's inputs and the 31B bf16 reference
    records.
  - The shipped code reproduces F's sweep (L's check).
- **Reported per checkpoint:** median paired deficit vs bf16 [CI], P(m < ln 19), E_slip, the censored fraction, and
  the shipped FLAG / SEVERE rule.

## 3. Predictions (before data)
| checkpoint | deficit (nats) | flag | basis |
|---|---|---|---|
| nvidia NVFP4 | ≈ 0.5–1.0 | no | RedHat NVFP4 0.74 |
| unsloth NVFP4 | ≈ 0.5–1.0 | no | |
| unsloth bnb-4bit (NF4) | ≈ 1–2 | no | a PTQ-like grid: PTQ Q4_0 2.70, QuantTrio 1.88 |
| cyankiwi QAT-AWQ | ≥ 3 | FLAG | H-QAT |
| melcheikh QAT-NVFP4 | ≥ 3 | FLAG | descriptive |

## 4. What gets written
- Rows in the audit table in RESULTS.md and the slipguard README.
- One clause in the paper only if the word budget allows, e.g. "…including the most-downloaded NVFP4 export (X nats)",
  or the H-QAT outcome.
- A failed prediction is reported as failed.

## 5. Deviations
Logged in PREREG_DEVIATIONS.md, under a "v2.10" heading.
