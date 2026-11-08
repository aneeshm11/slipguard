# EXPLORATORY distributions (review items B3/B9/B10) — 2026-11-06 13:13 UTC, PI
Not pre-registered. Script analysis/EXPLORATORY_distributions.py (reuses the frozen prereg_analysis.py and the corrected-fidelity wrapper unchanged); output analysis/EXPLORATORY_distributions.json. Same episodes and branch points as the registered outputs (31B means reproduce: 2.4735 / 0.2743; 135 branch points).

## B3 — E2E population: is the 2.47 → 0.27 drop driven by a few runaway episodes? YES, mostly (31B)
| 31B, 226 episode pairs (113 tasks × 2 reps) | base | fullp |
|---|---|---|
| mean delivered-malformed / episode (registered Y1) | 2.47 | 0.27 |
| episodes with ≥1 delivered-malformed call | 69/226 (30.5%) | 49/226 (21.7%) |
| median / p90 / max | 0 / 4 / 82 | 0 / 1 / 3 |
| share of all malformed calls in the top 5% of episodes | 74% | 39% |
- The share-with-any falls by −8.9 pp [−15.5, −2.2] (task-cluster bootstrap, p 0.008): a 29% relative drop, against 89% for the mean.
- The 14 base-stuck pairs (≥5 consecutive malformed; 6% of episodes) hold ~78% of base malformed calls (14 × 31.3 of 559).
- **Excluding the base-stuck pairs (212):** 0.57 → 0.27 (0.48×), share 55/212 → 47/212.
- **Reading:** slipguard does not prevent first slips (the onset is the model's). Its 31B end-to-end gain is mainly that it ends runaway imitation loops (stuck 14 → 0). Outside loops it halves malformed deliveries. This is the claimed mechanism, but the paper's "9× fewer" must not be read as "9× fewer episodes with a slip".
- **E4B** (113 pairs; no stuck episodes): 0.23 → 0.04, share 18/113 → 2/113 (−14.2 pp [−21.2, −7.1]). At E4B the gain is not loop-driven.

## B3 — branch-at-onset 31B (135 branches): robust to the distribution
| arm | mean | ≥1 post-onset malformed | median | p90 | max |
|---|---|---|---|---|---|
| base | 11.62 | 87/135 (64%) | 3 | 53 | 92 |
| quar | 0.18 | 13/135 (9.6%) | 0 | 0 | 9 |
| ipd | 0.11 | 5/135 (3.7%) | 0 | 0 | 5 |
| fullp | 0.05 | 5/135 (3.7%) | 0 | 0 | 2 |
- **Excluding the 54 base-stuck branches (81 left):** base 1.01 → quar 0.23 / ipd 0.14 / fullp 0.05, still a 4–20× cut.

## B9 — natural vs injected onsets (31B branches, descriptive)
| onset | n | base mean (≥1) | quar | ipd | fullp | resolved base/quar/ipd/fullp |
|---|---|---|---|---|---|---|
| natural | 13 | 24.3 (10/13) | 0.15 (2/13) | 0 (0/13) | 0 (0/13) | 7/8/7/9 |
| injected | 122 | 10.3 (77/122) | 0.18 (11/122) | 0.12 (5/122) | 0.06 (5/122) | 45/49/50/49 |
- Natural onsets show the same pattern (if anything, a stronger base loop).

## B10 — why does resolve not move? (31B, the 14 base-stuck episode pairs)
| | base | fullp |
|---|---|---|
| resolved | 5/14 | 6/14 |
| stuck | 14 | 0 |
| tool calls / episode | 65.9 | 36.4 |
| generated tokens / episode | 57,027 | 8,335 |
- The proxy rescues stuck episodes from the loop (7× fewer generated tokens, 45% fewer calls) but they are hard tasks: resolve 5 → 6.
- Stuck episodes are only 6% of episodes, so resolve power is tiny. The saving is cost, not resolve.
