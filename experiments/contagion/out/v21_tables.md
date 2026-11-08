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

not run / not yet analysed

### PREREG_v2.2 arm set H: all prior reasoning stripped from the history (thinking on)

not run / not yet analysed

### Side by side (same contexts; unconditional)

| condition | P0 | RD(P1 − P0) | RD(P6 − P0) | P8a removal |
|---|---|---|---|---|
| ON (discovery) | 5.0% | +35.3 pp [29.6, 41.0] | (see sections) | (see sections) |
| OFF (v2.1) | 6.3% | +33.3 pp [27.2, 39.4] — REPLICATES | +22.0 pp [17.2, 27.0] — REPLICATES | 117% [109, 128] — REPLICATES |
