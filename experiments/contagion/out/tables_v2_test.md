## Decision rules (UPGRADE_PLAN §P0-A1, verbatim; PREREG_v1)

- **format_induction**: pending held-out (gate half meets the criterion) — rule: claimed iff RD(P6-P0) >= +5 pp with CI_lo > 0 on both the gate and held-out halves (unconditional)
- **copying**: confirmed — rule: >= 80% of P1 malformed edits are verbatim copies AND P7 slips carry '"' well above P0 (operationalised: P7 share Wilson CI_lo > P0 share point estimate)
- **shipped_quarantine**: pending (P8a requires E's frozen renderer) — rule: works iff P8a and P4' each remove >= 70% of the P1 excess (unconditional) with CI_lo >= 50%
- **july_template**: does not fix the loop — rule: "does not fix the loop" iff NT P1/P0 >= 3x with CI_lo > 1 (unconditional)
  - induction, gate half: RD(P6−P0) = +21.3 pp [+16.5, +26.4] (300 contexts); new-content only: +19.3 pp [+14.6, +24.2]
  - copying: verbatim share of P1 malformed 85.4% [78.0, 90.5] (n=123); '"' closer share among malformed: P7 62.9% [51.1, 73.2] (n=70) vs P0 0.0% [0.0, 27.8] (n=10)
  - July template (150 gate contexts): RD(P1−P0) = +33.3 pp [+25.5, +41.6], ratio 17.667 [7.5, inf]; P4 removes 0.96 [0.867, 1.065], P5 removes 0.98 [0.877, 1.093]
  - removal of the P1 excess by P4 (unconditional): 1.057 [0.991, 1.135] (300 contexts)
  - removal of the P1 excess by P5 (unconditional): 1.075 [1.0, 1.161] (300 contexts)

## k = 1 pathways, 31B gate set (300 random contexts / 256 attempts; paired attempt-cluster bootstrap)

| arm | RD vs P0 (unconditional) | ratio (unconditional) | P(malformed edit) uncond | P(malformed \| edit) |
|---|---|---|---|---|
| P1 corrupted re-render + ADK error | +35.3 pp [+29.4, +41.1] | 8.067 [5.238, 14.778] | 40.3% | 46.2% |
| P7 = P1 with a double-quote closer | +18.3 pp [+13.1, +23.6] | 4.667 [2.87, 9.0] | 23.3% | 26.9% |
| P3 raw slip text + harness nudge | +34.0 pp [+28.2, +39.7] | 7.8 [5.045, 14.0] | 39.0% | 48.5% |
| P6 corrupted re-render + success (no retry motive) | +21.3 pp [+16.1, +26.4] | 5.267 [3.421, 9.625] | 26.3% | 32.5% |
| P2 error message only | -4.0 pp [-6.5, -1.7] | 0.2 [0.0, 0.5] | 1.0% | 1.3% |
| P4 canonical old-first re-render + true result | -2.0 pp [-4.4, +0.4] | 0.6 [0.263, 1.125] | 3.0% | 3.4% |
| P5 removed + note | -2.7 pp [-5.5, +0.0] | 0.467 [0.158, 1.0] | 2.3% | 3.4% |
| P0 original history (reference) | — | — | 5.0% | 5.7% |

## Pre-registered analyses (PREREG_v1; computed only on complete arm-sets)

- dose tier: incomplete (145/2135 jobs) - not analysed (PREREG: no interim looks)
- r_dose: incomplete (0/600) - not analysed
- lag2: incomplete (302/948) - not analysed
- P6k: incomplete (37/915) - not analysed
- A2: incomplete (0/600) - not analysed
- P7 injected-quote share: {"share_with_quote_closer": [0.6286, 0.5115, 0.7323, 70], "prediction": "M1/M2 >= 0.80; M3 0.3-0.7; D point 0.55 (80% PI 0.40-0.70)"}

## Replications at k = 1 (12B, E4B; histories are 31B trajectories, i.e. off-policy) and the observational layer

- 12b_old (600 contexts): P0k0 uncond 1.5% [0.8, 2.8] (n=600); P1k1 uncond 6.5% [4.8, 8.8] (n=600); P2k1 uncond 1.0% [0.5, 2.2] (n=600); P3k1 uncond 2.7% [1.7, 4.3] (n=600); P4k1 uncond 1.0% [0.5, 2.2] (n=600); P5k1 uncond 1.2% [0.6, 2.4] (n=600)
- e4b_old (406 contexts): P0k0 uncond 2.7% [1.5, 4.8] (n=404); P1k1 uncond 5.7% [3.8, 8.4] (n=404); P2k1 uncond 0.7% [0.2, 2.2] (n=404); P3k1 uncond 9.4% [6.9, 12.6] (n=405); P4k1 uncond 3.0% [1.7, 5.1] (n=405); P5k1 uncond 2.5% [1.4, 4.5] (n=404)
- observational (plain base 31B, 9077 edits / 2564 attempts): malformed 35.1% [34.1, 36.1]; first edit 17.6% [16.2, 19.1] (n=2564); later clean history 4.4% [3.8, 5.2] (n=3097); after 1/2/3/≥4 prior malformed 57.0% [53.5, 60.4] (n=784) / 69.7% [65.5, 73.5] (n=501) / 76.7% [72.3, 80.6] (n=399) / 86.3% [84.6, 87.8] (n=1732)
