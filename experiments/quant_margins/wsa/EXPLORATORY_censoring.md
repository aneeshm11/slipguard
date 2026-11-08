# EXPLORATORY: top-20 censoring sensitivity of the audit-weights deficit (review B13) — PI, 2026-11-06 13:14 UTC
Not pre-registered. Script EXPLORATORY_censoring.py reads the frozen sweep records read-only; output out/EXPLORATORY_censoring.json.

## What is censored
- **All censoring is the benign kind:** no look-alike token in the top-20 at that string end. The margin is then a LOWER bound, and these are the healthiest positions.
- `<|"|>` itself was never outside the top-20 (0 upper-bound cases at 454 string ends × 12 checkpoints).
- So the registered deficits, computed from lower bounds, are conservative: uncensored-only deficits are equal or larger for the damaged checkpoints.

## Deficit vs same-family bf16 (identical positions; episode-cluster bootstrap 95% CI, B = 2,000)
| checkpoint | registered (lower bounds) | both-uncensored median [CI] | both-uncensored mean paired [CI] | Gehan-type score [CI] |
|---|---|---|---|---|
| Google QAT-unquantized 31B | 5.51 | 6.00 [5.59, 6.44] | 5.74 [5.40, 6.10] | 0.58 [0.53, 0.63] |
| Google QAT-ct 31B | 5.13 | 5.67 [4.94, 6.07] | 5.41 [4.99, 5.81] | 0.43 [0.39, 0.48] |
| Google QAT-ct E4B (vs E4B bf16) | 3.12 | 3.13 [2.81, 3.38] | 3.16 [2.97, 3.35] | 0.93 [0.91, 0.96] |
| PTQ Q4_0 31B | 2.60 | 2.70 [2.33, 3.16] | 2.70 [2.42, 2.99] | 0.70 [0.65, 0.75] |
| QuantTrio AWQ 31B | 1.91 | 1.88 [1.58, 2.34] | 1.95 [1.70, 2.20] | 0.67 [0.62, 0.73] |
| RedHat NVFP4 31B | 0.79 | 0.74 [0.38, 1.12] | 0.84 [0.60, 1.08] | 0.24 [0.17, 0.32] |
| Intel AutoRound 31B | 0.63 | 0.75 [0.34, 1.45] | 1.19 [0.86, 1.52] | 0.17 [0.09, 0.24] |
| RedHat FP8 31B | 0.03 | −0.36 [−0.54, 0.01] | −0.12 [−0.21, −0.02] | −0.09 [−0.16, −0.02] |
| cyankiwi AWQ 31B (audit pick) | 0.02 | −0.47 [−0.81, −0.18] | −0.46 [−0.62, −0.31] | −0.16 [−0.24, −0.09] |
- **The magnitude ranking is unchanged** by the uncensored-only median or mean.
- Google QAT is still the most damaged 31B checkpoint, with a larger deficit (5.4–6.0) when censoring is removed.
- The audit pick (cyankiwi AWQ) is not damaged at all: its uncensored margins are slightly *higher* than bf16's.
- The Gehan-type score (a censoring-robust "share of positions certainly worse minus certainly better") agrees in sign everywhere. Its ordering differs among damaged checkpoints because heavily censored checkpoints (QAT-ct 55%) have fewer decidable pairs; it measures how often a checkpoint is worse, not by how much.
- **Censored fractions** (look-alike absent from top-20):

  | checkpoint | censored |
  |---|---|
  | 31B QAT-ct | 251/454 |
  | 31B QAT-unq | 187/454 |
  | E4B QAT-ct | 9/454 |
  | E4B bf16 | 76/454 |

  The rest are as in RESULTS.md.
