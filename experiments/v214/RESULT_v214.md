# PREREG_v2.14 result: Gemma-4-31B bf16 on TranscriptLab via the released CLI (registered; analysis once 10:21:35 UTC)
- **Files:** experiments/contagion/out/confirmatory/v214_bf16_analysis.json; run experiments/transcriptlab_cli/run_v214_bf16/.
- **Run:** TP2 on GPUs 4+5, 09:45–10:21; n = 300 states × 4 arms = 1,200 generations, 0 errors, 0 missing.

| | bf16 (this run) | C1 (4-bit QAT) | exploratory bf16 |
|---|---|---|---|
| copying RD(P1 − P0) | **+8.7 pp [5.7, 12.0]** (p = 1.5e-8, discordant 26 vs 0) | +18.3 [13.7, 23.4] | +9.0 |
| P1 | 8.7% [5.7, 12.0] | 19.7% | 9.0% |

- **(A) COPYING WITHOUT QUANTIZATION** (CI lower bound > 0).
- **(B) QAT AMPLIFIES COPYING:** bf16 P1 8.7% vs QAT 19.7% on the same 300 states: RD −11.0 pp [−15.1, −6.9]; McNemar discordant 37 (QAT only) vs 4 (bf16 only); one-sided p = 5.1e-8.
- **Descriptive:**
  - copying difference, bf16 − QAT: −9.7 pp [−14.0, −5.4];
  - imitation +5.0 pp [2.7, 7.5];
  - P0 0/300; P8a 0/300 (quarantine removal 100%);
  - agreement with the exploratory bf16 run: P1 8.7% vs 9.0%, discordant 2 vs 1, two-sided McNemar p = 1.0.
- **Predictions:** all met — copying ≈ +9 [5, 13]; P1 ≈ 9–10% (8.7%); p < 0.001; P0 ≈ 0; removal ≈ 100%.
- **Use:** the paper's Table 3 bf16 row now carries this registered run (exploratory dropped), and Fig. 2 v3 reads it.
