# PREREG_v2.15 result: the weight audit's deficit predicts TranscriptLab copying out of sample (registered; analysis once 12:26:04 UTC)
- **Files:** experiments/contagion/out/confirmatory/v215_audit_panel.json; runs experiments/transcriptlab_cli/run_v215_{qatawq,qatnvfp4,nvnvfp4}/.
- **New runs:** n = 300 states × 4 arms = 1,200 generations each, 0 errors, 0 missing. The bf16 point is PREREG_v2.14's registered run.

| checkpoint | deficit (nats) | P1 [95% CI] | copying RD |
|---|---|---|---|
| bf16 | 0 | 8.7% [5.7, 12.0] | +8.7 |
| AWQ (bf16-derived) | 0.02 | 10.3% [7.2, 13.9] | +10.0 |
| AutoRound | 0.63 | 13.3% [9.7, 17.3] | +5.0 (P0 8.3%) |
| **nvidia NVFP4** (new, not flagged) | 1.36 | 10.0% [6.7, 13.6] | +10.0 |
| QAT-ct | 5.13 | 19.7% [15.3, 24.3] | +18.3 |
| **QAT-AWQ** (new, flagged) | 6.00 | 22.3% [17.8, 27.1] | +22.0 |
| **QAT-NVFP4** (new, flagged) | 7.41 | 24.3% [19.5, 29.2] | +24.0 |

- **Primary: AUDIT PREDICTS COPYING.** Spearman ρ(deficit, P1) = 0.893; exact one-sided permutation p = 0.0062 over 5,040 orderings.
- **Secondary, out of sample (exact one-sided McNemar):** all met.

  | test | contrast | discordant | p |
  |---|---|---|---|
  | S1 | QAT-AWQ above bf16: −13.7 pp [−18.1, −9.4] | 44 vs 3 | 1.2e-10 |
  | S2 | QAT-NVFP4 above bf16: −15.7 pp [−20.1, −11.0] | 50 vs 3 | 2.8e-12 |
  | S3 | nvidia NVFP4 below QAT: −9.7 pp [−14.3, −5.4] | 37 vs 8 | 7.7e-6 |

- **Descriptive:**
  - ρ with copying RD: 0.865 (p = 0.008);
  - quarantine removal 96–100% on the new checkpoints;
  - the only rank inversion is nvidia NVFP4 (1.36 nats, 10.0%) below AutoRound (0.63, 13.3%; AutoRound's P0 is 8.3%).
- **Predictions:**

  | endpoint | predicted | observed |
  |---|---|---|
  | ρ | 0.8–0.95 | 0.89 (met) |
  | QAT-AWQ P1 | 18–22% | 22.3% (just above the range) |
  | QAT-NVFP4 P1 | 18–25% | 24.3% (met) |
  | nvidia NVFP4 P1 | 9–13% | 10.0% (met) |
  | S1–S3 | met | met |

- **Reading:** the audit's flags, set before any behaviour was measured (PREREG_v2.10), sort the three new checkpoints. The two flagged QAT-derived exports copy more than QAT itself. The unflagged NVFP4 copies like bf16.
