## Decision rules (UPGRADE_PLAN §P0-A1, verbatim; PREREG_v1)

- **format_induction**: claimed — rule: claimed iff RD(P6-P0) >= +5 pp with CI_lo > 0 on both the gate and held-out halves (unconditional)
- **copying**: confirmed — rule: >= 80% of P1 malformed edits are verbatim copies AND P7 slips carry '"' well above P0 (operationalised: P7 share Wilson CI_lo > P0 share point estimate)
- **shipped_quarantine**: works — rule: works iff P8a and P4' each remove >= 70% of the P1 excess (unconditional) with CI_lo >= 50%
- **july_template**: does not fix the loop — rule: "does not fix the loop" iff NT P1/P0 >= 3x with CI_lo > 1 (unconditional)
  - induction, gate half: RD(P6−P0) = +21.3 pp [+16.5, +26.4] (300 contexts); new-content only: +19.3 pp [+14.6, +24.2]
  - induction, held-out half: RD(P6−P0) = +26.5 pp [+21.7, +31.4] (294 contexts)
  - copying: verbatim share of P1 malformed 85.4% [78.0, 90.5] (n=123); '"' closer share among malformed: P7 62.9% [51.1, 73.2] (n=70) vs P0 0.0% [0.0, 27.8] (n=10)
  - July template (150 gate contexts): RD(P1−P0) = +33.3 pp [+25.3, +41.8], ratio 17.667 [7.571, inf]; P4 removes 0.96 [0.868, 1.056], P5 removes 0.98 [0.878, 1.089]
  - removal of the P1 excess by P8a (unconditional): 1.132 [1.069, 1.217] (300 contexts)
  - removal of the P1 excess by P8b (unconditional): 1.123 [1.058, 1.208] (300 contexts)
  - removal of the P1 excess by P4P (unconditional): 1.009 [1.0, 1.032] (300 contexts)
  - removal of the P1 excess by P4 (unconditional): 1.057 [0.988, 1.137] (300 contexts)
  - removal of the P1 excess by P5 (unconditional): 1.075 [1.0, 1.167] (300 contexts)

## k = 1 pathways, 31B gate set (300 random contexts / 256 attempts; paired attempt-cluster bootstrap)

| arm | RD vs P0 (unconditional) | ratio (unconditional) | P(malformed edit) uncond | P(malformed \| edit) |
|---|---|---|---|---|
| P1 corrupted re-render + ADK error | +35.3 pp [+29.5, +41.4] | 8.067 [5.333, 14.875] | 40.3% | 46.2% |
| P7 = P1 with a double-quote closer | +18.3 pp [+13.0, +24.0] | 4.667 [2.913, 8.875] | 23.3% | 26.9% |
| P3 raw slip text + harness nudge | +34.0 pp [+27.8, +39.4] | 7.8 [5.13, 14.429] | 39.0% | 48.5% |
| P6 corrupted re-render + success (no retry motive) | +21.3 pp [+16.6, +26.3] | 5.267 [3.429, 9.333] | 26.3% | 32.5% |
| P2 error message only | -4.0 pp [-6.6, -1.7] | 0.2 [0.0, 0.5] | 1.0% | 1.3% |
| P9 = P1 + informative error | +30.7 pp [+24.9, +36.4] | 7.133 [4.696, 13.0] | 35.7% | 43.0% |
| P4 canonical old-first re-render + true result | -2.0 pp [-4.4, +0.3] | 0.6 [0.278, 1.071] | 3.0% | 3.4% |
| P4' own-order canonical re-render (= P0 in 297/300) | -0.3 pp [-1.1, +0.0] | 0.933 [0.769, 1.0] | 4.7% | 5.3% |
| P8a shipped quarantine, recovered (E renderer) | -4.7 pp [-7.2, -2.4] | 0.067 [0.0, 0.222] | 0.3% | 0.4% |
| P8b shipped quarantine, sanitized (E renderer) | -4.3 pp [-6.8, -2.0] | 0.133 [0.0, 0.375] | 0.7% | 0.8% |
| P5 removed + note | -2.7 pp [-5.4, +0.0] | 0.467 [0.16, 1.0] | 2.3% | 3.4% |
| P0 original history (reference) | — | — | 5.0% | 5.7% |

## Pre-registered analyses (PREREG_v1; computed only on complete arm-sets)

- dose tier (cond), 305 contexts: P1(k=1) 0.248, P1(k=2) 0.316, P1(k=4) 0.631, p0 0.026; Δ2 = 0.3338 [0.0646, 0.6261], Δ4 = 1.6429 [1.2905, 2.0515], Δ4−2Δ2 = 0.9753 [0.4621, 1.5271]
- dose tier (uncond), 305 contexts: P1(k=1) 0.233, P1(k=2) 0.253, P1(k=4) 0.459, p0 0.023; Δ2 = 0.1071 [-0.2047, 0.3947], Δ4 = 1.0283 [0.6923, 1.3897], Δ4−2Δ2 = 0.8141 [0.3148, 1.3667]
- **rule D-M (primary, conditional): not discriminated between M1 and M2 (Delta2 CI straddles a boundary); none of M1-M3: the shapes contradict every mechanism -> fit the free curve** (regions {'M1|M2': 0.3639, 'M2|M3': 1.6287, 'measured_D1': 2.5296}); unconditional: not discriminated between M1 and M2 (Delta2 CI straddles a boundary); none of M1-M3: the shapes contradict every mechanism -> fit the free curve
- P4(k) removal fraction: {'k=1:uncond': 1.0625, 'k=1:cond': 1.0647, 'k=2:uncond': 1.0714, 'k=2:cond': 1.0631, 'k=4:uncond': 1.0376, 'k=4:cond': 1.0305}; old-first share of next edits under P4(k): k=1 32.2% [26.9, 38.0] (n=267); k=2 69.8% [64.1, 75.0] (n=272); k=4 93.5% [90.0, 95.9] (n=279)
- edit classes under P1(k): k=1: clean_rewrite n=151 mal 0.0% [0.0, 2.5] (n=151), new_content n=53 mal 5.7% [1.9, 15.4] (n=53), copy_most_recent n=66 mal 100.0% [94.5, 100.0] (n=66), same_content_variant n=16 mal 12.5% [3.5, 36.0] (n=16); k=2: clean_rewrite n=111 mal 0.0% [0.0, 3.4] (n=111), new_content n=43 mal 14.0% [6.6, 27.3] (n=43), copy_most_recent n=28 mal 100.0% [87.9, 100.0] (n=28), same_content_variant n=25 mal 24.0% [11.5, 43.4] (n=25), copy_earlier n=37 mal 100.0% [90.6, 100.0] (n=37); k=4: clean_rewrite n=48 mal 0.0% [0.0, 7.4] (n=48), new_content n=77 mal 71.4% [60.5, 80.3] (n=77), copy_earlier n=50 mal 100.0% [92.9, 100.0] (n=50), same_content_variant n=26 mal 53.8% [35.5, 71.2] (n=26), copy_most_recent n=21 mal 100.0% [84.5, 100.0] (n=21)
- r_dose: {"jobs_present": "600/600", "cond": {"n_contexts": 300, "Delta_r2": [0.1287, [-0.0247, 0.2891]], "Delta_r4": [0.0273, [-0.1799, 0.22]], "P(r=1)": 0.4618, "P(r=2)": 0.4939, "P(r=4)": 0.4686}, "uncond": {"n_contexts": 300, "Delta_r2": [0.0138, [-0.1296, 0.1649]], "Delta_r4": [-0.1263, [-0.3216, 0.0617]], "P(r=1)": 0.4033, "P(r=2)": 0.4067, "P(r=4)": 0.3733}}
- lag2: {"jobs_present": "948/948", "uncond": {"n_contexts": 250, "lag2_excess_share": [0.4559, [0.2917, 0.6401]], "p0": 0.028, "p1": 0.3, "p_lag2": 0.152}, "cond": {"n_contexts": 250, "lag2_excess_share": [0.479, [0.3096, 0.675]], "p0": 0.0308, "p1": 0.3304, "p_lag2": 0.1743}, "prediction": "M1 < 0.25 (~0); M2/M3 >= 0.5"}
- P6k: {"jobs_present": "915/915", "cond": {"n_contexts": 305, "n_attempts": 137, "kind": "cond", "Delta_2": {"est": 1.8276, "CI": [1.4502, 2.2604]}, "Delta_4": {"est": 3.6919, "CI": [3.2367, 4.2917]}, "D1_logit_p1_minus_logit_p0": {"est": 1.6138, "CI": [0.9435, 2.5896]}, "P(P6,k=1)": {"est": 0.1167, "CI": [0.0805, 0.1597]}, "P(P6,k=2)": {"est": 0.4511, "CI": [0.3885, 0.5079]}, "P(P6,k=4)": {"est": 0.8413, "CI": [0.7872, 0.8903]}, "p0": {"est": 0.0256, "CI": [0.0104, 0.0456]}, "Delta_4_minus_2Delta_2": {"est": 0.0366, "CI": [-0.5373, 0.6508]}, "free_curve_logit_linear_in_k": {"slope_per_extra_exemplar (Delta4/3)": {"est": 1.2306, "CI": [1.0789, 1.4306]}, "linearity_check Delta2 - Delta4/3 (0 if logit-linear in k)": {"est": 0.597, "CI": [0.2916, 0.9215]}, "first_exemplar_step D1": 1.6138}}, "uncond": {"n_contexts": 305, "n_attempts": 137, "kind": "uncond", "Delta_2": {"est": 1.7827, "CI": [1.4272, 2.1896]}, "Delta_4": {"est": 3.3011, "CI": [2.9266, 3.7719]}, "D1_logit_p1_minus_logit_p0": {"est": 1.5356, "CI": [0.8307, 2.5657]}, "P(P6,k=1)": {"est": 0.0984, "CI": [0.066, 0.1331]}, "P(P6,k=2)": {"est": 0.3934, "CI": [0.3355, 0.4471]}, "P(P6,k=4)": {"est": 0.7475, "CI": [0.6943, 0.8]},
- A2: {"jobs_present": "900/900", "h_by_arm (unconditional, h = 1 - q(arm)/q(L))": {"P5": {"n_states": 300, "h": [0.5494, [0.4766, 0.6203]], "q(L)": 0.7767, "q(P5)": 0.35}, "Q8b": {"n_states": 300, "h": [0.8841, [0.8412, 0.9241]], "q(L)": 0.7767, "q(Q8b)": 0.09}}, "rule": "h >= 0.7: quarantine is the dominant lever for 31B; h <= 0.4: content stickiness dominates (IPD-first)"}
- P7 injected-quote share: {"share_with_quote_closer": [0.6286, 0.5115, 0.7323, 70], "prediction": "M1/M2 >= 0.80; M3 0.3-0.7; D point 0.55 (80% PI 0.40-0.70)"}

## A2 with B's MAP repairs (:8303; L re-run on the same server; unconditional h = 1 − q(arm)/q(L))

| arm | ITT, all 300 (abstained → Q8b) | repaired 282 |
|---|---|---|
| P8a-MAP (E's renderer recovering B's call + MalformedToolCall) | h 0.932 [0.897, 0.962]; q(arm) 0.053, q(L) 0.780 | h 0.991 [0.977, 1.000]; q(arm) 0.007, q(L) 0.791 |
| P4′-MAP (repaired call, new-first, + success) | h 0.897 [0.858, 0.936]; q(arm) 0.080, q(L) 0.780 | h 0.955 [0.925, 0.979]; q(arm) 0.035, q(L) 0.791 |

- server check: L on :8300 77.7% [72.6, 82.0] (n=300) vs :8303 78.0% [73.0, 82.3] (n=300); Q8b on the 18 abstained: 77.8% [54.8, 91.0] (n=18) / 77.8% [54.8, 91.0] (n=18)
- retry split (repaired 282): P0: malformed among retries 82.3% [77.2, 86.5] (n=255), among new 65.0% [43.3, 81.9] (n=20), no edit 7; Q4M: malformed among retries 0.0% [0.0, 32.4] (n=8), among new 14.9% [8.3, 25.3] (n=67), no edit 207; Q8M: malformed among retries 0.6% [0.1, 3.2] (n=174), among new 1.8% [0.3, 9.3] (n=57), no edit 51
- rule: h >= 0.7: quarantine is the dominant lever for 31B; h <= 0.4: content stickiness dominates (IPD-first)

## Test–retest (100 gate contexts × {P0, P1})

- same_seed P0k0: malformed agreement 98.0% [93.0, 99.5] (n=100), κ = 0.7403, next-tool agreement 91.0% [83.8, 95.2] (n=100), byte-identical 72.0% [62.5, 79.9] (n=100); rate original 3.0% [1.0, 8.5] (n=100) vs retest 5.0% [2.1, 11.2] (n=100)
- same_seed P1k1: malformed agreement 97.0% [91.5, 99.0] (n=100), κ = 0.9316, next-tool agreement 95.0% [88.8, 97.9] (n=100), byte-identical 75.0% [65.7, 82.5] (n=100); rate original 33.0% [24.6, 42.7] (n=100) vs retest 32.0% [23.7, 41.7] (n=100)
- new_seed P0k0: malformed agreement 96.0% [90.2, 98.4] (n=100), κ = 0.5825, next-tool agreement 85.0% [76.7, 90.7] (n=100), byte-identical 29.0% [21.0, 38.5] (n=100); rate original 3.0% [1.0, 8.5] (n=100) vs retest 7.0% [3.4, 13.8] (n=100)
- new_seed P1k1: malformed agreement 91.0% [83.8, 95.2] (n=100), κ = 0.8011, next-tool agreement 85.0% [76.7, 90.7] (n=100), byte-identical 13.0% [7.8, 21.0] (n=100); rate original 33.0% [24.6, 42.7] (n=100) vs retest 36.0% [27.3, 45.8] (n=100)

## Replications at k = 1 (12B, E4B; histories are 31B trajectories, i.e. off-policy) and the observational layer

- 12b_old (600 contexts): P0k0 uncond 1.5% [0.8, 2.8] (n=600); P1k1 uncond 6.5% [4.8, 8.8] (n=600); P2k1 uncond 1.0% [0.5, 2.2] (n=600); P3k1 uncond 2.7% [1.7, 4.3] (n=600); P4k1 uncond 1.0% [0.5, 2.2] (n=600); P5k1 uncond 1.2% [0.6, 2.4] (n=600); P6k1 uncond 8.8% [6.8, 11.4] (n=600); P7k1 uncond 9.0% [6.3, 12.8] (n=300); P8ak1 uncond 0.3% [0.1, 1.9] (n=300); P8bk1 uncond 0.3% [0.1, 1.9] (n=300); P9k1 uncond 6.7% [4.4, 10.1] (n=300)
- e4b_old (600 contexts): P0k0 uncond 2.5% [1.5, 4.1] (n=600); P1k1 uncond 5.7% [4.1, 7.8] (n=600); P2k1 uncond 0.7% [0.3, 1.7] (n=600); P3k1 uncond 8.8% [6.8, 11.4] (n=600); P4k1 uncond 2.5% [1.5, 4.1] (n=600); P5k1 uncond 2.3% [1.4, 3.9] (n=600); P6k1 uncond 11.0% [8.7, 13.8] (n=600)
- observational (plain base 31B, 9077 edits / 2564 attempts): malformed 35.1% [34.1, 36.1]; first edit 17.6% [16.2, 19.1] (n=2564); later clean history 4.4% [3.8, 5.2] (n=3097); after 1/2/3/≥4 prior malformed 57.0% [53.5, 60.4] (n=784) / 69.7% [65.5, 73.5] (n=501) / 76.7% [72.3, 80.6] (n=399) / 86.3% [84.6, 87.8] (n=1732)
## Thinking batteries on the 300 discovery gate contexts (PREREG_v2.1, PREREG_v2.2)

### PREREG_v2.1: the shipped thinking-OFF flag (enable_thinking=false; the model still thinks, see the manipulation check)

PREREG_v2.1_thinkingOFF.md sha256 bb3696da3772d0c7ac67eae9f7f76162dbff11ca357161c34e3c5ca53fb44839. Contexts: 300 complete-case (300 gate contexts); missing jobs per arm {'P0': 0, 'P1': 0, 'P5': 0, 'P6': 0, 'P8a': 0}; server(s) ['http://127.0.0.1:8300/v1', 'http://127.0.0.1:8302/v1']; ON comparison runs on ['null', 'http://127.0.0.1:8300/v1']. Unconditional ITT primary; attempt-cluster bootstrap B = 2000.

| claim | contrast | ON (discovery, same contexts) | condition estimate [95% CI] | Holm p (one-sided) | D 80% PI | verdict |
|---|---|---|---|---|---|---|
| T1 | RD(P1 - P0) | +35.3 pp [29.6, 41.0] | +33.3 pp [27.2, 39.4] (arm 39.7% vs P0 6.3%) | 0.002 | +38 pp [+22, +52] | **REPLICATES** |
| T2 | RD(P6 - P0) | +21.3 pp [16.3, 26.2] | +22.0 pp [17.2, 27.0] (arm 28.3% vs P0 6.3%) | 0.002 | +22 pp [+8, +38] | **REPLICATES** |
| T3 | removal of the P1 excess by P8a; Holm test RD(P1 - P8a) > 0 | 113% [107, 121] | removal 117% [109, 128]; RD(P1 − P8a) +39.0 pp [33.0, 44.7] | 0.002 | 1.05 [0.85, 1.20] | **REPLICATES** |
| T4 | removal of the P1 excess by P5; Holm test RD(P1 - P5) > 0 | 108% [100, 116] | removal 109% [99, 120]; RD(P1 − P5) +36.3 pp [30.5, 42.0] | 0.002 | 1.00 [0.80, 1.15] | **REPLICATES (mixed condition)** |

| arm | condition: P(malformed edit), uncond [95% CI] | conditional | P(edit) | D 80% PI (level) | condition − ON, uncond RD [95% CI] | condition − ON, P(edit) |
|---|---|---|---|---|---|---|
| P0 | 6.3% [3.8, 9.2] | 7.2% [4.4, 10.4] | 87.3% [83.1, 90.6] | [3.0, 12.0] | +1.3 pp [-0.7, 3.5] (ON 5.0%) | -0.7 pp [-4.3, 2.7] |
| P1 | 39.7% [33.9, 45.2] | 47.0% [40.8, 53.3] | 84.3% [79.8, 88.0] | [28.0, 60.0] | -0.7 pp [-3.9, 2.4] (ON 40.3%) | -3.0 pp [-5.8, -0.6] |
| P5 | 3.3% [1.6, 5.6] | 4.2% [2.0, 7.0] | 79.3% [74.4, 83.5] | — | +1.0 pp [-1.3, 3.4] (ON 2.3%) | +10.3 pp [5.6, 15.5] |
| P6 | 28.3% [23.2, 33.3] | 34.4% [28.6, 40.2] | 82.3% [77.6, 86.2] | [14.0, 45.0] | +2.0 pp [-1.4, 5.5] (ON 26.3%) | +1.3 pp [-2.0, 4.9] |
| P8a | 0.7% [0.0, 1.7] | 0.8% [0.0, 2.0] | 84.3% [79.8, 88.0] | — | +0.3 pp [0.0, 1.0] (ON 0.3%) | -1.0 pp [-5.1, 3.0] |

Registered secondary predictions: OFF - ON: P1 +5 pp [-5, +15]; P0 +1.5 pp [-2, +6]; P(edit) within +-10 pp in every arm.
P5 / P8a minus P0 (prediction ≤ +1 pp): P5 -3.0 pp, P8a -5.7 pp.

| manipulation check | P0 | P1 | P5 | P6 | P8a | pooled | P5_template_closed | P5_not_template_closed |
|---|---|---|---|---|---|---|---|---|
| thought opened (condition) | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | 37.3% [32.0, 42.9] | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | 87.5% [85.7, 89.0] | 0.0% [0.0, 2.0] | 100.0% [96.7, 100.0] |
| median thought chars (condition) | 73.5 | 76.0 | 373.5 | 172.0 | 117.0 | 117.5 | — | — |
| thought opened (ON, same contexts) | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | — | — | — |
| median thought chars (ON) | 80.0 | 79.0 | 593.0 | 228.0 | 187.5 | 185.0 | — | — |

Prediction: opened >= 0.95 (point 0.99); median 680 chars [450, 900].

Labelled verdicts on thought subsets (descriptive):
| claim:subset | n | estimate | verdict |
|---|---|---|---|
| T4:thought_opened | 112 | removal 142% [90, 350] | REPLICATES |
| T4:thought_not_opened | 0 | too few contexts | NOT EVALUABLE |

| copy classes (P1 / P6 edits) | condition | ON, same contexts |
|---|---|---|
| P1: byte-exact copies among malformed edits | 87.4% [80.2, 92.2] | 85.1% [77.7, 90.4] |
| P1: clean rewrites of the same edit among edits | 29.2% [24.0, 35.1] | 29.8% [24.6, 35.6] |
| P6: byte-exact copies among malformed edits | 3.5% [1.2, 9.9] | 0.0% [0.0, 4.6] |
| P6: clean rewrites of the same edit among edits | 1.6% [0.6, 4.1] | 2.1% [0.9, 4.7] |

Prediction: byte-exact copies >= 80% of malformed P1 edits (ON 85.4%).

### PREREG_v2.2 arm set S: thought suppressed (flag off + the template's closed empty thought prefilled)

PREREG_v2.2_thoughtSuppressed.md sha256 ec9164ffa833f351618c3eb7ec69aa2e471e096307de7f5fd61e6c72e07f09d3. Contexts: 300 complete-case (300 gate contexts); missing jobs per arm {'P0': 0, 'P1': 0, 'P6': 0, 'P8a': 0}; server(s) ['http://127.0.0.1:8302/v1']; ON comparison runs on ['null', 'http://127.0.0.1:8300/v1']. Unconditional ITT primary; attempt-cluster bootstrap B = 2000.

| claim | contrast | ON (discovery, same contexts) | condition estimate [95% CI] | Holm p (one-sided) | D 80% PI | verdict |
|---|---|---|---|---|---|---|
| S1 | RD(P1 - P0) | +35.3 pp [29.6, 41.0] | +38.3 pp [32.8, 44.2] (arm 40.7% vs P0 2.3%) | 0.0015 | +38 pp [+22, +55] | **REPLICATES** |
| S2 | RD(P6 - P0) | +21.3 pp [16.3, 26.2] | +27.0 pp [22.1, 32.4] (arm 29.3% vs P0 2.3%) | 0.0015 | +24 pp [+8, +40] | **REPLICATES** |
| S3 | removal of the P1 excess by P8a; Holm test RD(P1 - P8a) > 0 | 113% [107, 121] | removal 105% [101, 110]; RD(P1 − P8a) +40.3 pp [34.7, 46.2] | 0.0015 | 1.05 [0.80, 1.20] | **REPLICATES** |

| arm | condition: P(malformed edit), uncond [95% CI] | conditional | P(edit) | D 80% PI (level) | condition − ON, uncond RD [95% CI] | condition − ON, P(edit) |
|---|---|---|---|---|---|---|
| P0 | 2.3% [0.7, 4.1] | 3.0% [0.9, 5.2] | 78.7% [73.7, 82.9] | [3.0, 13.0] | -2.7 pp [-5.3, -0.3] (ON 5.0%) | -9.3 pp [-13.9, -4.7] |
| P1 | 40.7% [35.1, 46.5] | 46.7% [40.8, 52.7] | 87.0% [82.7, 90.3] | [28.0, 63.0] | +0.3 pp [-3.9, 5.1] (ON 40.3%) | -0.3 pp [-4.3, 3.9] |
| P6 | 29.3% [24.4, 34.6] | 36.8% [31.2, 42.8] | 79.7% [74.8, 83.8] | — | +3.0 pp [-1.7, 7.9] (ON 26.3%) | -1.3 pp [-6.4, 3.4] |
| P8a | 0.3% [0.0, 1.0] | 0.4% [0.0, 1.2] | 87.3% [83.1, 90.6] | — | +0.0 pp [-1.0, 1.0] (ON 0.3%) | +2.0 pp [-2.6, 6.6] |

Registered secondary predictions: S - ON: P1 +5 pp [-5, +18].

| manipulation check | P0 | P1 | P6 | P8a | pooled |
|---|---|---|---|---|---|
| thought opened (condition) | 0.0% [0.0, 1.3] | 0.0% [0.0, 1.3] | 0.0% [0.0, 1.3] | 0.0% [0.0, 1.3] | 0.0% [0.0, 0.3] |
| median thought chars (condition) | None | None | None | None | None |
| thought opened (ON, same contexts) | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | — |
| median thought chars (ON) | 80.0 | 79.0 | 228.0 | 187.5 | 120.0 |

Prediction: re-opened <= 0.05; > 0.10 -> label thought-prefilled and report on non-reopened contexts.

| copy classes (P1 / P6 edits) | condition | ON, same contexts |
|---|---|---|
| P1: byte-exact copies among malformed edits | 86.1% [78.8, 91.1] | 85.1% [77.7, 90.4] |
| P1: clean rewrites of the same edit among edits | 30.3% [25.0, 36.1] | 29.8% [24.6, 35.6] |
| P6: byte-exact copies among malformed edits | 5.7% [2.5, 12.6] | 0.0% [0.0, 4.6] |
| P6: clean rewrites of the same edit among edits | 1.7% [0.7, 4.2] | 2.1% [0.9, 4.7] |

Prediction: clean rewrites under P1 lower than ON (ON 30%, 80/266): S 15% [5, 30]; byte-exact copies >= 80%.

### PREREG_v2.2 arm set H: all prior reasoning stripped from the history (thinking on)

PREREG_v2.2_thoughtSuppressed.md sha256 ec9164ffa833f351618c3eb7ec69aa2e471e096307de7f5fd61e6c72e07f09d3 (§3). Contexts: 300 complete-case (300 gate contexts); missing jobs per arm {'P0': 0, 'P1': 0}; server(s) ['http://127.0.0.1:8302/v1']; ON comparison runs on ['null', 'http://127.0.0.1:8300/v1']. Unconditional ITT primary; attempt-cluster bootstrap B = 2000.

| claim | contrast | ON (discovery, same contexts) | condition estimate [95% CI] | Holm p (one-sided) | D 80% PI | verdict |
|---|---|---|---|---|---|---|
| H1 | RD(P1 - P0) | +35.3 pp [29.6, 41.0] | +26.0 pp [20.6, 31.6] (arm 29.7% vs P0 3.7%) | 0.0005 | +33 pp [+16, +50] | **REPLICATES** |

| arm | condition: P(malformed edit), uncond [95% CI] | conditional | P(edit) | D 80% PI (level) | condition − ON, uncond RD [95% CI] | condition − ON, P(edit) |
|---|---|---|---|---|---|---|
| P0 | 3.7% [1.7, 5.8] | 5.3% [2.5, 8.3] | 69.0% [63.5, 74.0] | [2.0, 11.0] | -1.3 pp [-4.3, 1.4] (ON 5.0%) | -19.0 pp [-24.6, -14.1] |
| P1 | 29.7% [24.7, 34.9] | 40.3% [34.1, 46.5] | 73.7% [68.4, 78.3] | — | -10.7 pp [-16.1, -5.5] (ON 40.3%) | -13.7 pp [-18.5, -9.1] |

| manipulation check | P0 | P1 | pooled |
|---|---|---|---|
| thought opened (condition) | 30.0% [25.1, 35.4] | 65.7% [60.1, 70.8] | 47.8% [43.9, 51.8] |
| median thought chars (condition) | 626.0 | 0 | 0 |
| thought opened (ON, same contexts) | 100.0% [98.7, 100.0] | 100.0% [98.7, 100.0] | — |
| median thought chars (ON) | 80.0 | 79.0 | 80.0 |

| copy classes (P1 / P6 edits) | condition | ON, same contexts |
|---|---|---|
| P1: byte-exact copies among malformed edits | 82.0% [72.8, 88.6] | 85.1% [77.7, 90.4] |
| P1: clean rewrites of the same edit among edits | 39.8% [33.6, 46.4] | 29.8% [24.6, 35.6] |

Prediction: none registered.

### Side by side (same contexts; unconditional)

| condition | P0 | RD(P1 − P0) | RD(P6 − P0) | P8a removal |
|---|---|---|---|---|
| ON (discovery) | 5.0% | +35.3 pp [29.6, 41.0] | (see sections) | (see sections) |
| OFF (v2.1) | 6.3% | +33.3 pp [27.2, 39.4] — REPLICATES | +22.0 pp [17.2, 27.0] — REPLICATES | 117% [109, 128] — REPLICATES |
| S | 2.3% | +38.3 pp [32.8, 44.2] — REPLICATES | +27.0 pp [22.1, 32.4] — REPLICATES | 105% [101, 110] — REPLICATES |
| H | 3.7% | +26.0 pp [20.6, 31.6] — REPLICATES | — | — |
## PREREG_v2 confirmatory replication on workstream P's public SWE-bench corpus (31B QAT-ct, S1)

### Full corpus (primary)

Pools: {'A1': 300, 'A2': 216, 'A1k2': 0}; 31B jobs present 2100/2100; episode-cluster bootstrap B = 2000. Unconditional ITT primary.

| claim | estimate [95% CI] | Holm F1c p | D 80% PI | verdict |
|---|---|---|---|---|
| C1 | +18.3 pp [13.6, 23.2] (19.7% vs 1.3%); cond +25.1 pp | 0 | RD +27 pp [+11, +45] | **REPLICATES** |
| C2 | +7.7 pp [4.1, 11.5] (9.0% vs 1.3%); cond +12.8 pp | 0 | +15 pp [+5, +30] | **ATTENUATED** |
| C4 | removal 94% [82, 107]; cond 94% | 0 | 1.00 [0.80, 1.15] | **REPLICATES** |
| C5 | removal 98% [88, 110]; cond 97% | 0 | 1.05 [0.85, 1.20] | **REPLICATES** |
| C6 | removal 98% [88, 110]; cond 98% | — | 1.00 [0.75, 1.20] | **REPLICATES** |
| C7 | RD(P9 − P0) +14.0 pp [9.7, 18.6]; retention 0.76 [0.58, 0.96] | — | retention 0.85 [0.55, 1.10] | **REPLICATES** |
| C3 (pool A2, n 216) | P6 at k=1/2/4 7.4% / 15.3% / 39.4%; Δ₂ +0.81 [0.35, 1.36]; Δ₄ +2.09 [1.65, 2.73]; Δ₄−2Δ₂ +0.47 [-0.23, 1.20] | — | Δ₂ +1.6 [0.8, 2.4]; Δ₄ +3.2 [1.8, 4.5] | **ATTENUATED** |

| claim | half H1 (ranks 1–150) | half H2 (151–300) |
|---|---|---|
| C1 | +16.7 pp [10.0, 23.8] (REPLICATES) | +20.0 pp [13.5, 26.6] (REPLICATES) |
| C2 | +7.3 pp [2.0, 13.1] (ATTENUATED) | +8.0 pp [3.4, 13.1] (ATTENUATED) |
| C4 | 100% [79, 124] (REPLICATES) | 90% [74, 104] (REPLICATES) |
| C5 | 104% [88, 128] (REPLICATES) | 93% [80, 106] (REPLICATES) |
| C6 | 108% [94, 133] (REPLICATES) | 90% [74, 104] (REPLICATES) |

12B: C8 +0.3 pp [-1.7, 2.3] → **FAILS**; C10 RD(P6 − P1) +1.7 pp, RD(P6 − P0) +2.0 pp → FAILS; C11 P5 removal 400% [-400, 600] → FAILS (underpowered: CI width > 1); C11 P8a removal 500% [-500, 600] → FAILS (underpowered: CI width > 1)

E4B: C9 +4.7 pp [1.3, 8.1] → **REPLICATES**; C10 RD(P6 − P1) -0.7 pp, RD(P6 − P0) +4.0 pp → FAILS; C11 P5 removal 64% [-22, 125] → FAILS (underpowered: CI width > 1); C11 P8a removal 114% [67, 250] → REPLICATES

**§3.4 global statement:** the laundering loop **replicates with attenuation** ({'C1': 'REPLICATES', 'C2': 'ATTENUATED', 'C5': 'REPLICATES'}).

### Verified-only sensitivity (C3 via the documented sensitivity pools; see prereg_deviations_A.json)

Pools: {'A1': 99, 'A2': 58, 'A1k2': 58}; 31B jobs present 693/693; episode-cluster bootstrap B = 2000. Unconditional ITT primary.

| claim | estimate [95% CI] | Holm F1c p | D 80% PI | verdict |
|---|---|---|---|---|
| C1 | +19.2 pp [11.6, 27.8] (20.2% vs 1.0%); cond +27.7 pp | 0 | RD +27 pp [+11, +45] | **REPLICATES** |
| C2 | +10.1 pp [3.9, 17.4] (11.1% vs 1.0%); cond +15.2 pp | 0.001 | +15 pp [+5, +30] | **ATTENUATED** |
| C4 | removal 90% [62, 111]; cond 87% | 0.005 | 1.00 [0.80, 1.15] | **REPLICATES** |
| C5 | removal 95% [77, 115]; cond 94% | 0 | 1.05 [0.85, 1.20] | **REPLICATES** |
| C6 | removal 100% [87, 119]; cond 99% | — | 1.00 [0.75, 1.20] | **REPLICATES** |
| C7 | RD(P9 − P0) +16.2 pp [8.8, 23.7]; retention 0.84 [0.54, 1.27] | — | retention 0.85 [0.55, 1.10] | **REPLICATES** |
| C3 (shortfall branch; A2 n 58) | Δ₂ +1.02 [0.14, 2.31]; Δ₄ +2.15 [1.29, 3.63] | — | Δ₂ +1.6 [0.8, 2.4]; Δ₄ +3.2 [1.8, 4.5] | see note |

| claim | half H1 (ranks 1–150) | half H2 (151–300) |
|---|---|---|
| C1 | +12.0 pp [2.0, 22.4] (ATTENUATED) | +26.5 pp [15.6, 38.8] (REPLICATES) |
| C2 | +10.0 pp [0.0, 20.4] (FAILS) | +10.2 pp [2.1, 19.2] (ATTENUATED) |
| C4 | 83% [-18, 175] (FAILS (underpowered: CI width > 1)) | 92% [70, 100] (REPLICATES) |
| C5 | 117% [100, 300] (REPLICATES) | 85% [62, 100] (REPLICATES) |
| C6 | 100% [57, 200] (REPLICATES) | 100% [100, 100] (REPLICATES) |

12B: C8 +1.0 pp [0.0, 3.2] → **FAILS**; C10 RD(P6 − P1) +0.0 pp, RD(P6 − P0) +1.0 pp → FAILS; C11 P5 removal 100% [100, 100] → REPLICATES; C11 P8a removal 100% [100, 100] → REPLICATES

E4B: C9 +8.1 pp [2.2, 14.6] → **REPLICATES**; C10 RD(P6 − P1) +0.0 pp, RD(P6 − P0) +8.1 pp → REPLICATES; C11 P5 removal 75% [0, 100] → FAILS; C11 P8a removal 75% [0, 133] → FAILS (underpowered: CI width > 1)

**§3.4 global statement:** the laundering loop **replicates with attenuation** ({'C1': 'REPLICATES', 'C2': 'ATTENUATED', 'C5': 'REPLICATES'}).

### Natural descriptives (PREREG_v2 §4, all S1 episodes)

| # | estimate [95% CI] | D 80% PI | verdict |
|---|---|---|---|
| D1 | 1.0% [0.4, 1.6] | [0.05, 0.25] | LOWER |
| D2 | 1.7% [1.2, 2.2] | [0.015, 0.1] | CONSISTENT |
| D3 | 19.0% [6.7, 31.2] | [0.3, 0.8] | CONSISTENT |
| D4 | 12.8% [3.9, 22.2] | [0.45, 0.9] | LOWER |
| D5 | 11.446 [3.764, 22.206] | [4.0, inf] | CONSISTENT |
| D6a | 52.6% [27.0, 67.9] | [0.7, 1.0] | LOWER |
| D6b | 78.4% [43.7, 98.2] | [0.6, 1.0] | CONSISTENT |
| D7 | 100.0% [100.0, 100.0] | [0.85, 1.0] | CONSISTENT |
| D8 | 0.407 [0.344, 0.468] | [0.3, 2.5] | CONSISTENT |
| D9 | 0.8% [0.4, 1.4] | [0.02, 0.15] | LOWER |
| D11 | 67.0% [46.4, 90.0] | [0.25, 0.9] | CONSISTENT |
| D10 | 0.0% [0.0, 0.0] | [0.03, 0.3] | LOWER |

Note: E4B's canonical analysis is its first, single run (out/confirmatory/confirm_v2_31b_e4b_*.json; C9 +4.7 pp [1.4, 8.0], C11 P8a 114% [67, 225]). The E4B lines above come from the combined run, whose bootstrap draws differ in order; the verdicts are identical.
