# PREREG_v2.14 — Gemma-4-31B bf16 on TranscriptLab via the released CLI: copying without quantization, and less of it than 4-bit QAT?

Written by the PI on 2026-11-08 ~09:35 UTC, before any v2.14 job. Freeze time and sha256s are in PROGRESS.md.
The user made GPU 5 available ("You can use GPU 5 as well, I see GPU 4 is idle").

## 1. Why
- Table 3's bf16 row (+9.0 pp [5.7, 12.5]) is exploratory: experiments/contagion/out/confirmatory/bf16_core_all.json, from out/main/rCbf16_v2.jsonl, labelled "EXPLORATORY benchmark precision row".
- The weight audit's story is that the 4-bit QAT weights lose margin and the damage follows those weights. bf16 copying below QAT copying on the same states is that story's TranscriptLab-level prediction. It has never been registered.
- E_audit's T1 tests the end-to-end analogue (blind until 14:00); this run is independent of it.

## 2. Run (R-BF16)
- **Server:** vLLM 0.19.1, tensor parallel 2 on GPUs 4+5 (tools/serve_vllm_tp2.sh, as the exploratory bf16 row and E_audit's bf16 lanes). Model models/gemma-4-31b-it (bf16), served name gemma-4-31b, port 8384. C1's server arguments: `--max-num-seqs 64 --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4`, max-model-len 32768.
- **Gate:** the user's rule (< 2 GB and 0 compute apps) on both GPUs for 2 min.
- **Command:**

  ```bash
  transcriptlab run --base … --model gemma-4-31b --tokenizer models/gemma-4-31b-it --pool A1 --arms P0,P1,P6,P8a \
      --out experiments/transcriptlab_cli/run_v214_bf16 --python env_gemma
  ```

  - Registered corpus (unmasked PNC v1.0, as C1); registered per-state seeds; CLI 0.1.3. On this registered gemma4 path the CLI's commands are those of 0.1.2.
  - One resume pass, then `transcriptlab report`.
- **Guard:** if > 5% of the first pass's records are errors, stop before report/analysis (NOT RUN, cause logged).

## 3. Analysis (experiments/v214/analyze_v214_bf16.py, frozen with this document; run once)
Statistics block copied verbatim from analyze_v27_robustness.py (f68bc12d), via analyze_v211_masked.py: judge indicator (malformed edit), task-cluster bootstrap B = 2000 (seed 20261106), exact McNemar.
- **(A) Copying without quantization:** COPYING WITHOUT QUANTIZATION iff the 95% CI lower bound of the bf16 copying RD(P1 − P0) is above 0 (the Table 3 rule). Otherwise NOT DETECTED.
- **(B) Quantization amplifies copying:** QAT AMPLIFIES COPYING iff, on the states complete in both runs, bf16 P1 is below C1's (QAT, out/main/rC31b_v2.jsonl) P1 with exact one-sided McNemar p < 0.05. Otherwise NOT SHOWN.
- (A) and (B) are reported separately, each with its own rule; no family claim and no adjustment.
- **Descriptive:**
  - bf16 rates of P0/P1/P6/P8a;
  - imitation RD;
  - quarantine removal (not gated);
  - agreement with the exploratory bf16 run (P1 rate; two-sided McNemar);
  - the copying-RD difference bf16 − QAT, with a bootstrap CI.

## 4. Predictions
| endpoint | prediction | basis |
|---|---|---|
| (A) | COPYING WITHOUT QUANTIZATION, copying ≈ +9 pp [5, 13] | exploratory row |
| (B) | QAT AMPLIFIES COPYING: bf16 P1 ≈ 9–10% vs QAT 19.7%, p < 0.001 | |
| bf16 P0 | ≈ 0–1% | |
| removal | ≈ 100%, unstable with few events | |

## 5. What gets written
- Table 3: the bf16 row becomes this registered run (its numbers replace the exploratory ones; "exploratory" is dropped), and the exploratory run is kept in docs.
- A null is reported as a null, and (B) failing is reported in §6.
