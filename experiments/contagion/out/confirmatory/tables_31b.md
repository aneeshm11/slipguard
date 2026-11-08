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

**§3.4 global statement:** the laundering loop **replicates with attenuation** ({'C1': 'REPLICATES', 'C2': 'ATTENUATED', 'C5': 'REPLICATES'}).

