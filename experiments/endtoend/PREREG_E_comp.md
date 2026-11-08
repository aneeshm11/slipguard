# PREREG_E_comp: which slipguard component carries the end-to-end gain?

Written by the PI on 2026-11-07, before any E_comp episode. The freeze time and sha256s are in PROGRESS.md. Compute: shared queue with PREREG_E_audit, on GPUs 0, 1, 2 and 6 under the user's gate.

## 1. Why, and what is already known (disclosed)
- **The paper's claim, from the registered branch runs:** "Quarantine alone, without repair, does most of this." On 135 branches continued from a first slip, malformed calls after the slip went from 11.6 to 0.18 with quarantine alone, and to 0.11 with IPD alone.
- **What that does not measure:** whole episodes (population level), where slips occur at their natural rate and the slip call itself is still delivered under quarantine alone.
- **Already seen (PREREG_E_ext, r3..r10):** base 1.76, fullp 0.37. This study adds the two single-component arms, salt-paired with those episodes.

## 2. Design
- **Arms:**
  - `quar`: the proxy's quarantine-only config (proxy/configs.json: quarantine true, ipd false);
  - `ipd`: IPD-only (quarantine false, ipd true).
- **Server:** Gemma-4-31B QAT-ct with PREREG_E's server arguments. Tags compr<k>s<h>.
- **Launcher:** run_population_qi.sh. It is PREREG_E's frozen run_population.sh with only the arm list changed (base fullp → quar ipd). Per-arm conc 3, so a lane carries the same server load as PREREG_E_ext's lanes.
- **Seed salt `pop31r<k>`:** the same per-request seeds as PREREG_E_ext replicate k. Each quar/ipd episode is therefore paired by (task, salt) with that replicate's registered base and fullp episodes.
- **Replicates k = 3, 4, 5, 6 (then 7, 8 if time allows)**, in the shared queue (ext/queue_single.txt) with ext/dispatch_q.sh. No lane starts after 2026-11-08 11:30 UTC.
- **Blinding:** as in PREREG_E_audit. The base and fullp episodes are already analysed (disclosed); the quar and ipd outcomes are blind.

## 3. Analysis set and stopping rule
- The analysis set is r3..rK, where K is the largest index such that every comp replicate r3..rK is complete (both halves × both arms).
- It is evaluated once, at the earlier of:
  1. the queue being finished;
  2. 2026-11-08 14:00 UTC.
- Fewer than 2 complete replicates → **UNDERPOWERED**.

## 4. Endpoints (analysis/prereg_E_comp_analysis.py + prereg_cov_common.py, frozen now)
Y1 = delivered malformed calls per episode. Task means are taken over replicates, over (task, k) sets where all four arms have a non-infra episode.

- **Primary (Holm over 2; each test needs a negative difference and Holm-adjusted p_boot < 0.05):**
  - Q1: quar vs base, boot_paired seed 20261131 → **QUARANTINE ALONE REDUCES MALFORMED CALLS END TO END**.
  - Q2: ipd vs base, seed 20261132 → **IPD ALONE REDUCES MALFORMED CALLS END TO END**.
  - Ratios are reported for both (boot_ratio seed 1).
- **Secondary:**
  - fullp vs quar (does IPD add on top of quarantine?), seed 20261133;
  - fullp vs ipd (seed 20261134) and quar vs ipd (seed 20261135);
  - stuck counts per arm, with McNemar for quar and ipd vs base;
  - resolve, quar − base and ipd − base (seeds 20261136/7), with NI at −3 pp descriptive;
  - Y2 for quar and ipd vs base (seeds 20261138/9).

## 5. Predictions (before data)
| endpoint | prediction | basis |
|---|---|---|
| quar Y1 | 0.6–1.0 (ratio ≈ 0.35–0.55) | quarantine stops contagion, but the slip calls themselves are still delivered |
| ipd Y1 | 0.4–0.8 (ratio ≈ 0.25–0.45) | IPD repairs most slips; without quarantine, unrepaired calls stay in the history |
| Q1 | QUARANTINE ALONE REDUCES, p ≈ 0.9 | |
| Q2 | IPD ALONE REDUCES, p ≈ 0.9 | |
| fullp vs quar | fullp lower (IPD adds), CI excludes 0 with p ≈ 0.6 | |
| stuck | quar near 0; ipd above 0 | |

## 6. What gets written
- "End to end, quarantine alone cut malformed calls per episode from a to b, and IPD alone to c (registered); the full proxy reached d."
- If the paper's "quarantine alone does most of this" sentence is not supported at the population level, it is revised to match.

## 7. Deviations
Logged in experiments/endtoend/PREREG_DEVIATIONS.md under "E_comp".
