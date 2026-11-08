# PREREG_v2.12 result: TranscriptLab on a Llama-family model (NousResearch/Hermes-3-Llama-3.1-8B, rev 896ea440)
Run 2026-11-08 05:28–05:36 UTC on GPU 4 (bf16, vLLM 0.19.1) with transcriptlab 0.1.3. See deviation 1: 0.1.2 failed on
this tokenizer; it was fixed by a request adapter for new models only.
- Report and analysis: X's frozen analyze.py via `transcriptlab report`, then experiments/v212/analyze_v212.py, run once at 05:36:02.
- Files: experiments/contagion/out/confirmatory/v212_llama.json; experiments/transcriptlab_cli/run_v212_hermes3/{analysis.json, report.txt, gen.jsonl}.

## Registered verdict (Table 3 rule): **HISTORY-SENSITIVE**
n = 300 A1 states × 4 arms = 1,200 generations, 0 errors.

| | RD | 95% CI | p (one-sided) |
|---|---|---|---|
| copying RD(P1L − P0) | +6.0 pp | [2.6, 9.6] | 0.0005 |
| imitation RD(P6 − P0) | +5.3 pp | [2.3, 8.7] | |

Copying events: 28 vs 10, discordant 25 vs 7.

Arm rates (malformed edit, unconditional):

| arm | rate | 95% CI |
|---|---|---|
| P0 | 3.3% | [1.8, 6.0] |
| P1L | 9.3% | [6.5, 13.2] |
| P6 | 8.7% | [6.0, 12.4] |
| P8a | 5.7% | [3.6, 8.9] |

- Quarantine removal (reported, not gated): 0.61 [−0.13, 1.15]. It is unstable because the P1 excess is small.
- **Prediction (PREREG §5): copying ≈ 0 [−2, +3] — FAILED.** The imitation prediction (+2 [−1, +6]) was close: +5.3. The verdict was given p ≈ 0.4 of HISTORY-SENSITIVE.

## Exploratory (after the verdict, from the frozen analysis's own copy_check; does not change the verdict)
- **The P1 effect here is not copying of the laundered call:** 0 of 28 malformed P1L edits are verbatim copies.
  - 26 of the 28 are `<tool_call>` blocks that do not parse (prose or broken JSON inside the block); 1 misses a key.
  - The error message roughly doubles edit attempts: P_edit 26% (P0) → 55% (P1L); 47 of 166 P1L edits are clean retries.
  - The malformed share among edits rises less: 12.8% → 16.9%.
- In Gemma-4-31B the excess consists of copies of the laundered call (the paper's mechanism). In Hermes-3 the same arm raises malformed edits mainly by making the model retry the edit, and its retries are often unparseable.
- **Imitation (P6):** 0 of 26 malformed edits are copies either; P_malformed|edit is 33.8% vs 12.8% (P0).
- **So:**
  - "History-sensitive" holds for a Llama-family model.
  - The "copying" column measures the P1 contrast. For this model that contrast is not copying.
  - Report both, with the copy share.

## Where it goes
- Leaderboard (RESULTS, transcriptlab README): one row, "Hermes-3-Llama-3.1-8B, bf16 (JSON), CLI 0.1.3", with a footnote that 0 of 28 malformed edits copy the laundered call.
- LIMITATIONS §5: "Where it does not appear" is revised. A non-Gemma model now passes the P1 rule, but by retries, not copies.
- Paper Table 3 and Fig. 2 (c, d) at the v2.4 fill, if the budget allows (≈ 30 tokens). Otherwise the docs only, and the paper's Table 3 caption says "13 configurations at submission".
