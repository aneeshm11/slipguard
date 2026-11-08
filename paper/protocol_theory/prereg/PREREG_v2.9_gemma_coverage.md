# PREREG_v2.9 — TranscriptLab coverage of the Gemma 4 family: E2B (4-bit QAT) and E4B (bf16), via the released CLI

Written by the PI on 2026-11-06 (freeze time and sha256s in PROGRESS.md), before any v2.9 job. Compute: all free
GPUs for 48 h (user, ~17:45 UTC).

## 1. Question
slipguard targets Gemma 4. TranscriptLab's leaderboard (paper Table 3) covers four Gemma 4 configurations: 31B 4-bit
QAT, 31B bf16, E4B 4-bit QAT and 12B 4-bit QAT. This registration adds:
- the smallest model, **Gemma-4-E2B** (4-bit QAT-ct, the challenge's QAT format);
- **Gemma-4-E4B in bf16**, to see whether its effect depends on 4-bit weights as the 31B's partly did (31B bf16
  copying +9.0 vs 4-bit +18.3 pp).

Both runs go through the released CLI (`transcriptlab run` / `report`), so the coverage is produced exactly as a user
would produce it.

## 2. Runs (GPU6, then any free GPU; vLLM 0.19.1)
| run | model dir | served name | server arguments |
|---|---|---|---|
| RE2B | models/gemma-4-e2b-it-qat-w4a16-ct | gemma-4-e2b | tools/serve_vllm.sh defaults + `--max-num-seqs 64` + gemma4 tool/reasoning parsers (as C1) |
| RE4B16 | models/gemma-4-e4b-it | gemma-4-e4b-bf16 | the same; dtype from the checkpoint (bf16) |

Command for each: `transcriptlab run --base … --model <served> --tokenizer <model dir> --pool A1 --arms P0,P1,P6,P8a
--out experiments/transcriptlab_cli/<run> --python env_gemma`, plus one resume pass. Then `transcriptlab report <dir>
--python env_gemma`, which runs the frozen analyze_bf16_core.py (episode-cluster bootstrap, B = 2000) and writes
analysis.json.

## 3. Verdicts (experiments/contagion/scripts/analyze_v29_coverage.py reads each analysis.json; frozen with this file)
- **NEEDS A GUARD** iff the 95% CI of copying RD(P1 − P0) or of induction RD(P6 − P0) excludes 0 (lower bound > 0).
  This is the paper's Table 3 rule. Otherwise **NO GUARD NEEDED (not detected)**.
- **Quarantine removal** (P8a) is reported when copying's CI excludes 0.
- **E4B bf16 vs E4B 4-bit:** descriptive only. The registered E4B 4-bit copying is +4.7 pp [1.4, 8.0].

## 4. Predictions (before data)
| run | copying RD | induction RD | needs a guard |
|---|---|---|---|
| E2B | +3 pp [−1, 8] | +3 pp [0, 7] | likely: small models show induction (E4B +4.0, 12B +2.0) |
| E4B bf16 | +3 pp [0, 7] | +3 pp [0, 7] | uncertain; QAT damage at E4B is smaller than at 31B (audit deficit 3.13 vs 5.13 nats) |

## 5. What gets written
Two rows for the TranscriptLab leaderboard in RESULTS.md and the docs. In the paper only if the word budget allows,
e.g. as "(and E2B …)" in Table 3. A null is reported as a null.

## 6. Deviations
Logged in PREREG_DEVIATIONS.md, under a "v2.9" heading.
