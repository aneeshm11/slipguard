### Observational (main-track logs; edits as Wilson 95% CIs; cluster bootstrap over attempts in brackets where given)

| quantity | synthesis population (incl. teacher runs) | plain base 31B-QAT | team adapters r*/rl* |
|---|---|---|---|
| edit calls / attempts | 13267 / 4184 | 9077 / 2564 | 9843 / 3743 |
| malformed edits | 24.1% [23.4, 24.9] | 35.1% [34.1, 36.1] | 2.0% [1.8, 2.3] |
| first edit malformed | 10.8% [9.9, 11.8] (n=4184) | 17.6% [16.2, 19.1] (n=2564) | 0.3% [0.1, 0.5] (n=3743) |
| later edit, clean history | 2.8% [2.4, 3.2] (n=5633) | 4.4% [3.8, 5.2] (n=3097) | 0.3% [0.2, 0.4] (n=5908) |
| later edit after 1 prior malformed | 54.6% [51.2, 58.0] (n=818) | 57.0% [53.5, 60.4] (n=784) | 58.6% [40.7, 74.5] (n=29) |
| later edit after 2 prior malformed | 69.7% [65.5, 73.5] (n=501) | 69.7% [65.5, 73.5] (n=501) | 72.2% [49.1, 87.5] (n=18) |
| later edit after 3 prior malformed | 76.7% [72.3, 80.6] (n=399) | 76.7% [72.3, 80.6] (n=399) | 88.9% [56.5, 98.0] (n=9) |
| later edit after >=4 prior malformed | 86.3% [84.6, 87.8] (n=1732) | 86.3% [84.6, 87.8] (n=1732) | 98.5% [94.8, 99.6] (n=136) |

- synthesis: P(bad | previous bad) = 0.874 vs within-attempt permutation null mean 0.823 (max 0.836, 1000 permutations, p = 0.0010); attempt-cluster bootstrap 95% CIs: {"malformed_rate": [0.2166, 0.2654], "first_edit": [0.0987, 0.1171], "later_clean_history": [0.0233, 0.0315], "after_1_bad": [0.4964, 0.599], "after_ge4_bad": [0.8197, 0.8988]}
- base: P(bad | previous bad) = 0.879 vs within-attempt permutation null mean 0.827 (max 0.841, 1000 permutations, p = 0.0010); attempt-cluster bootstrap 95% CIs: {"malformed_rate": [0.3204, 0.3823], "first_edit": [0.1607, 0.1911], "later_clean_history": [0.0371, 0.0515], "after_1_bad": [0.519, 0.6287], "after_ge4_bad": [0.8207, 0.8996]}
- adapters: P(bad | previous bad) = 0.940 vs within-attempt permutation null mean 0.891 (max 0.933, 1000 permutations, p = 0.0010)

- Natural episodes (base): 577 attempts with a malformed edit followed by later edits; later edits malformed 2596/3416; retries of the same content 2348/2530; new content 248/886; recover a clean edit 342/577.
- Hazard model (base; logistic, run fixed effects, attempt-cluster bootstrap): prev_bad OR 7.087 [4.928, 9.938]; log1p_n_prior_bad OR 2.429 [1.91, 3.228]; retry_of_prev OR 0.192 [0.012, 0.426]; prev_bad_x_retry OR 73.362 [32.384, 1225.725]; first_edit OR 4.141 [2.765, 5.894]; log1p_position OR 0.841 [0.616, 1.078]; temp_0.7plus OR 0.948 [0.658, 1.704]

### Injection, 31b_old: k = 1 pathways on the random sample (86 contexts)

| arm | P(next call is edit_file) | P(malformed \| edit) | paired diff vs P0 [cluster bootstrap] | ratio vs P0 | malformed among retries of the replaced call | among other edits | emitted order |
|---|---|---|---|---|---|---|---|
| P0 original history | 85.4% [76.1, 91.4] (n=82) | 4.3% [1.5, 11.9] (n=70) | - | - | 0/7 | 3/63 | {'new_first': 70} |
| P1 corrupted re-render + error | 81.9% [72.3, 88.7] (n=83) | 44.1% [33.0, 55.9] (n=68) | +38.7 pp [+25.3, +51.7] | 9.908 [4.038, inf] | 28/49 | 2/19 | {'new_first': 67, 'null': 1} |
| P2 error message only | 91.3% [73.2, 97.6] (n=23) | 0.0% [0.0, 15.5] (n=21) | -5.0 pp [-15.8, +0.0] | 0.0 [0.0, 0.0] | 0/13 | 0/8 | {'new_first': 21} |
| P3 raw slip text + nudge | 70.4% [51.5, 84.2] (n=27) | 42.1% [23.1, 63.7] (n=19) | +34.3 pp [+15.2, +54.6] | 8.556 [2.286, inf] | 6/11 | 2/8 | {'new_first': 19} |
| P4 canonical old-first re-render | 86.9% [78.0, 92.5] (n=84) | 4.1% [1.4, 11.4] (n=73) | -1.5 pp [-8.3, +4.1] | 0.648 [0.0, inf] | 0/7 | 3/66 | {'new_first': 34, 'old_first': 39} |
| P5 removed + note | 63.4% [52.6, 73.0] (n=82) | 1.9% [0.3, 10.1] (n=52) | -2.4 pp [-9.5, +3.9] | 0.442 [0.0, inf] | 1/31 | 0/21 | {'new_first': 52} |

- **G1** P(slip | k=1, P1) / P(slip | k=0) = 9.908 [4.038, inf] (43.1% vs 4.3%, paired diff +38.7 pp [+25.3, +51.7], 80 contexts / 76 attempts) -> PASS (needs >= 3 and CI_lo > 1)
- **G2 (P4)** fraction of the P1 excess removed = 1.038 [0.893, 1.299] (P1 43.1%, P4 2.9%, P0 4.3%; 80 contexts) -> PASS (needs >= 0.5)
- **G2 (P5)** fraction of the P1 excess removed = 1.063 [0.932, 1.286] (P1 43.8%, P5 1.9%, P0 4.4%; 79 contexts) -> PASS (needs >= 0.5)

- Replay fidelity (P0 vs logged next call on the same contexts): logged malformed 7.3% [3.4, 15.1] (n=82); replay P(edit) 85.4% [76.1, 91.4] (n=82); replay malformed | edit 4.3% [1.5, 11.9] (n=70).

### Injection, 12b_old: k = 1 pathways on the random sample (231 contexts)

| arm | P(next call is edit_file) | P(malformed \| edit) | paired diff vs P0 [cluster bootstrap] | ratio vs P0 | malformed among retries of the replaced call | among other edits | emitted order |
|---|---|---|---|---|---|---|---|
| P0 original history | 63.2% [56.7, 69.2] (n=228) | 2.8% [1.1, 6.9] (n=144) | - | - | 0/11 | 4/133 | {'new_first': 142, 'old_first': 1, 'null': 1} |
| P1 corrupted re-render + error | 60.4% [54.0, 66.5] (n=230) | 12.2% [7.8, 18.7] (n=139) | +8.9 pp [+3.7, +14.4] | 4.175 [1.913, 22.452] | 15/103 | 2/36 | {'new_first': 117, 'old_first': 21, 'null': 1} |
| P2 error message only | 51.3% [44.9, 57.7] (n=230) | 0.9% [0.1, 4.6] (n=118) | -1.9 pp [-5.7, +0.8] | 0.308 [0.0, 1.406] | 1/82 | 0/36 | {'new_first': 116, 'old_first': 2} |
| P3 raw slip text + nudge | 69.9% [63.6, 75.5] (n=226) | 2.5% [1.0, 6.3] (n=158) | -0.3 pp [-3.8, +3.5] | 0.904 [0.141, inf] | 1/105 | 3/53 | {'new_first': 154, 'old_first': 2, 'null': 2} |
| P4 canonical old-first re-render | 64.3% [57.9, 70.3] (n=227) | 0.7% [0.1, 3.8] (n=146) | -2.1 pp [-4.3, +0.0] | 0.245 [0.0, 0.75] | 0/8 | 1/138 | {'old_first': 133, 'new_first': 12, 'null': 1} |
| P5 removed + note | 45.0% [38.7, 51.4] (n=229) | 1.0% [0.2, 5.3] (n=103) | -1.8 pp [-5.0, +1.2] | 0.353 [0.0, 1.867] | 0/39 | 1/64 | {'new_first': 77, 'old_first': 26} |

- **G1** P(slip | k=1, P1) / P(slip | k=0) = 4.175 [1.913, 22.452] (11.7% vs 2.8%, paired diff +8.9 pp [+3.7, +14.4], 227 contexts / 200 attempts) -> PASS (needs >= 3 and CI_lo > 1)
- **G2 (P4)** fraction of the P1 excess removed = 1.238 [1.001, 2.117] (P1 11.8%, P4 0.7%, P0 2.8%; 226 contexts) -> PASS (needs >= 0.5)
- **G2 (P5)** fraction of the P1 excess removed = 1.203 [0.834, 2.251] (P1 11.7%, P5 1.0%, P0 2.8%; 226 contexts) -> PASS (needs >= 0.5)

- Replay fidelity (P0 vs logged next call on the same contexts): logged malformed 6.1% [3.7, 10.0] (n=228); replay P(edit) 63.2% [56.7, 69.2] (n=228); replay malformed | edit 2.8% [1.1, 6.9] (n=144).

### Injection, e4b_old: k = 1 pathways on the random sample (53 contexts)

| arm | P(next call is edit_file) | P(malformed \| edit) | paired diff vs P0 [cluster bootstrap] | ratio vs P0 | malformed among retries of the replaced call | among other edits | emitted order |
|---|---|---|---|---|---|---|---|
| P0 original history | 84.3% [72.0, 91.8] (n=51) | 4.7% [1.3, 15.5] (n=43) | - | - | 0/4 | 2/39 | {'new_first': 43} |
| P1 corrupted re-render + error | 69.8% [56.5, 80.5] (n=53) | 2.7% [0.5, 13.8] (n=37) | -1.9 pp [-10.9, +7.5] | 0.597 [0.0, inf] | 1/19 | 0/18 | {'new_first': 37} |
| P2 error message only | 64.1% [50.7, 75.7] (n=53) | 0.0% [0.0, 10.2] (n=34) | -4.7 pp [-11.9, +0.0] | 0.0 [0.0, 0.0] | 0/18 | 0/16 | {'new_first': 34} |
| P3 raw slip text + nudge | 65.4% [51.8, 76.8] (n=52) | 8.8% [3.0, 23.0] (n=34) | +4.1 pp [-7.5, +15.3] | 1.853 [0.0, inf] | 1/5 | 2/29 | {'new_first': 34} |
| P4 canonical old-first re-render | 81.1% [68.6, 89.4] (n=53) | 4.7% [1.3, 15.5] (n=43) | +0.1 pp [-6.5, +6.9] | 1.024 [0.0, inf] | 0/4 | 2/39 | {'old_first': 25, 'new_first': 17, 'null': 1} |
| P5 removed + note | 78.4% [65.4, 87.5] (n=51) | 2.5% [0.4, 12.9] (n=40) | -2.3 pp [-10.3, +7.0] | 0.525 [0.0, inf] | 0/16 | 1/24 | {'new_first': 40} |

- **G1** P(slip | k=1, P1) / P(slip | k=0) = 0.597 [0.0, inf] (2.8% vs 4.7%, paired diff -1.9 pp [-10.9, +7.5], 51 contexts / 49 attempts) -> FAIL (needs >= 3 and CI_lo > 1)
- **G2 (P4)** fraction of the P1 excess removed = 1.059 [-4.542, 5.955] (P1 2.8%, P4 4.8%, P0 4.7%; 51 contexts) -> PASS (needs >= 0.5)
- **G2 (P5)** fraction of the P1 excess removed = -0.187 [-2.861, 9.35] (P1 2.9%, P5 2.5%, P0 4.8%; 50 contexts) -> FAIL (needs >= 0.5)

- Replay fidelity (P0 vs logged next call on the same contexts): logged malformed 9.8% [4.3, 21.0] (n=51); replay P(edit) 84.3% [72.0, 91.8] (n=51); replay malformed | edit 4.7% [1.3, 15.5] (n=43).

### Dose-response, 31b_old (nested set: contexts with >= 4 clean prior edits; P(malformed | edit), Wilson 95%)

| pathway | contexts | k=0 | k=1 | k=2 | k=4 |
|---|---|---|---|---|---|

### Dose-response, 12b_old (nested set: contexts with >= 4 clean prior edits; P(malformed | edit), Wilson 95%)

| pathway | contexts | k=0 | k=1 | k=2 | k=4 |
|---|---|---|---|---|---|

### Dose-response, e4b_old (nested set: contexts with >= 4 clean prior edits; P(malformed | edit), Wilson 95%)

| pathway | contexts | k=0 | k=1 | k=2 | k=4 |
|---|---|---|---|---|---|

