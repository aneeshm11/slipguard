# Evaluation of D's predictions (E_PREDICTIONS_v1.md §4) against the E2E results
Evaluated by the PI on 2026-11-06, once. Inputs: prereg_pop31.json / prereg_pop12B_sec6conforming.json / prereg_popE4B.json (s_post),
and prereg_br31.json / prereg_br12.json / prereg_brE4B.json (branch arms).
Approximation, stated: g_Q and g_I use the branch endpoint actually computed (post-onset delivered-MALFORMED calls per branch)
in place of post-onset WASTED calls. In the population data the two differ by under 5% (Y1 2.47 vs Y2 2.52 per episode at 31B).

## P-b (31B: ipd ≈ full′; difference ≤ 0.15 calls and relative cuts within 10 pp): HOLDS
- Post-onset malformed per branch: ipd 0.111, fullp 0.052, so the difference is 0.059 calls (≤ 0.15).
- Relative cut vs base (11.622): ipd 99.0%, fullp 99.6%, so they differ by 0.5 pp (≤ 10 pp).
- The "emitted slip at the first post-onset edit" sub-claim was not computed by the frozen analysis: not evaluated.

## P-a (lever crossover with model size): 31B part HOLDS; small-model part FAILS
- **31B:** s_post = 0.88, inside the predicted 0.80 [0.65, 0.90].
  - Quarantine removal of total waste ≈ s_post·g_Q = 0.88 × 0.985 = 0.87 (predicted ≥ 0.60).
  - IPD ≥ (1 − 0.88)·0.9 + 0.88 × 0.990 = 0.98 (predicted ≥ 0.85).
- **12B:** s_post = 0.79, far outside the predicted 0.25 [0.10, 0.40]. **E4B:** s_post = 0.31, inside.
- **Crossover:** the predicted crossover (IPD ≫ quarantine for small models) is NOT observed.
  - At the 12B and E4B branch points, base shows no post-onset loop (0.07 malformed per branch), and quar, ipd and fullp do not differ (n.s.).

## P-c (F's probes): see experiments/quant_margins/wsa/RESULTS.md
- Not an E quantity.
- F's calib slip-state pLA was QAT 0.25 vs bf16 0.24, consistent with R_post ∈ [0.8, 1.25].
