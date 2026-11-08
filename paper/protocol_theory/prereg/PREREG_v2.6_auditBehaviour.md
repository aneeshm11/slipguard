# PREREG_v2.6 (addendum): behavioural validation of `slipguard audit-weights` on public states (workstream D)

* **Written:** 2026-11-05, starting 17:37 UTC. **Frozen** when its sha256 is written to `PROGRESS.md`.
  Deviations go to `PREREG_DEVIATIONS.md` (this folder).
* **What was known when this was written:**
  * **The audit deficits.** F's T1 sweep (`experiments/quant_margins/wsa/out/sweep_report.json`): 454 held-out PNC
    string ends, endpoint top-20 margins paired against 31B bf16. Median deficits in nats:

    | checkpoint | median deficit |
    |---|---|
    | cyankiwi AWQ-4bit | 0.02 [−0.18, 0.21] |
    | RedHat FP8-dynamic | 0.03 |
    | Intel AutoRound int4 | 0.63 [0.31, 0.83] |
    | NVFP4 | 0.79 |
    | QuantTrio AWQ | 1.91 |
    | PTQ-Q4_0 | 2.60 |
    | Google QAT-ct | 5.13 [4.69, 5.56] |
    | QAT-unquantized | 5.51 |

    The sweep's slip-state look-alike masses were also seen: AWQ 0.012, AutoRound 0.052, QAT-ct 0.328, bf16 0.023.
  * **Behaviour at both ends**, on the 300 public S1_A1 states:
    * bf16: P0 0.0%, P1 9.0%, P6 4.7%, P8a 0.0% (A, exploratory);
    * QAT-ct: P0 1.3%, P1 19.7%, P6 9.0%, P8a 0.3% (C1, confirmatory).
* **What was not known.** D has seen **no** behavioural outcome for cyankiwi AWQ or Intel AutoRound. None existed at
  writing time.
* **Relation to earlier registrations.** This is an addendum to PREREG_v2 (5da75e61…) and v2.5 (50f8a395…). Conventions
  follow PREREG_v2 §3 (ITT malformed-edit rate, paired by state, episode-cluster bootstrap B ≥ 2,000).

## 1. Question
Does the weights-plus-one-pass audit (`slipguard audit-weights`: the margin deficit at string ends vs bf16) rank 4-bit
checkpoints by their **behaviour** after a laundered slip? Specifically:
* (H1) Does the audit's top-ranked 4-bit checkpoint have less contagion than Google's QAT-ct?
* (H2) Does a mid-deficit checkpoint sit below QAT-ct?
* (H3) Is the history guard still needed and effective on a good checkpoint?

## 2. Runs (A; frozen runner, no code changes)
* **Plan.** A's frozen runner on the same core plan, `experiments/contagion/data/confirmatory/plans/plan_bf16_core_full.jsonl`:
  * P0/P1/P6/P8a × the 300 S1_A1 states = 1,200 jobs;
  * T = 1.0, top-p 0.95, generation_config top-k, the same per-state seeds.
* **Checkpoints.** Two new ones, each served by vLLM 0.19.1 on one GPU with its own repo's quantization config:
  * **cyankiwi AWQ-4bit** (audit deficit 0.02);
  * **Intel AutoRound int4** (deficit 0.63).
* **Comparators** (reused; same plan, states and seeds):
  * QAT-ct = C1's confirmatory outputs;
  * bf16 = A's exploratory bf16 core run.
* **Judge.** A's frozen judge, as used for C1.
* **Logging.** A records each checkpoint's repo revision, the vLLM args and the runner/judge hashes in PROGRESS.md
  before the first job.
* **Pairing** is by state, not by sample: different models do not share samples even with equal seeds.

## 3. Hypotheses, predictions (D's 80% prediction intervals) and tests
**Basis for the predictions:**
* the AWQ deficit is indistinguishable from bf16 and FP8, so its behaviour should track bf16;
* AutoRound sits slightly off bf16;
* QAT-ct's excess contagion comes with a large slip-state look-alike mass (0.33), and AWQ's mass (0.012) is
  bf16-like.

| quantity | cyankiwi AWQ | Intel AutoRound | (known) bf16 / QAT-ct |
|---|---|---|---|
| P1 malformed-edit rate | **9.5% [5.5, 15]** | **11% [6, 17]** | 9.0% / 19.7% |
| P0 | 0.3% [0, 1.5] | 0.5% [0, 2.0] | 0.0% / 1.3% |
| P6 | 5% [2, 9] | 5.5% [2.5, 10] | 4.7% / 9.0% |
| P8a | 0.3% [0, 1.3] | 0.3% [0, 1.5] | 0.0% / 0.3% |
| RD(P1, vs QAT-ct) | **−10 pp [−16, −4]** | **−9 pp [−15, −2]** | — |
| P8a removal of the P1 excess | 1.00 [0.85, 1.10] | 1.00 [0.85, 1.10] | — |

D's probability that H1 holds: 0.75. The main risk is that contagion (copying a laundered call) depends on factors that
the string-end margin does not measure.

**Confirmatory Holm family (α = 0.05, one-sided, paired by state):**

| # | hypothesis | contrast | test |
|---|---|---|---|
| **H1 (primary)** | AWQ has less contagion than QAT-ct | RD = P1(AWQ) − P1(QAT-ct) < 0 | exact one-sided McNemar on per-state discordant pairs; CI from an episode-cluster bootstrap |
| **H2 (dose-response, simple form)** | a mid-deficit checkpoint has less contagion than the high-deficit one | RD = P1(AutoRound) − P1(QAT-ct) < 0 | same |
| **H3** | quarantine still matters on a good checkpoint | P8a(AWQ) < P1(AWQ) | same |

**H2 monotonicity (descriptive; n = 4 points).** I report the four P1 point estimates against the four deficits.
* With n = 4, the best possible exact one-sided Spearman p is 1/24 = 0.042. I report ρ and that p, but it is not part
  of the Holm family.
* bf16 (0) and AWQ (0.02) are treated as **one tier**: their deficits do not differ.
* "**Ordered**" iff P1(QAT-ct) ≥ P1(AutoRound) − 1.5 pp and P1(AutoRound) ≥ max(P1(bf16), P1(AWQ)) − 1.5 pp. The 1.5 pp
  tolerance is about 0.6 binomial SE at 10% with n = 300.

**H3 evaluability.**
* H3 is evaluated only if AWQ shows contagion, i.e. RD(P1 − P0) under AWQ has CI_lo > 0.
* Otherwise H3 is **NOT EVALUABLE**. It is dropped from the Holm family, and the paper says contagion was not detected
  under AWQ.
* Removal = (P1 − P8a)/(P1 − P0) under AWQ, with a bootstrap CI.

**No-harm / quality (non-inferiority, outside Holm).** P0(AWQ) − P0(QAT-ct) must have point ≤ 0 and 95% CI upper
≤ +2 pp. The same is reported for AutoRound. P6 is reported for both, descriptively.

## 4. Verdict rules
* **H1:**

  | verdict | rule |
  |---|---|
  | **AUDIT PICK CUTS CONTAGION** | Holm-adjusted p(H1) < 0.05 and RD ≤ −5 pp |
  | **SMALLER CUT** | Holm p < 0.05 and −5 pp < RD < 0 |
  | **NOT SHOWN** | otherwise |

* **H2:**

  | verdict | rule |
  |---|---|
  | **DOSE-RESPONSE SUPPORTED** | Holm p(H2) < 0.05 and the four points are "Ordered" |
  | **PARTIAL** | exactly one of those two holds |
  | **NOT SHOWN** | neither holds |

* **H3:**

  | verdict | rule |
  |---|---|
  | **QUARANTINE STILL NEEDED AND WORKS** | evaluable, Holm p(H3) < 0.05, removal ≥ 0.90 with CI_lo ≥ 0.50 |
  | **WORKS (attenuated)** | evaluable, Holm p < 0.05, removal ≥ 0.70 with CI_lo ≥ 0.50 |
  | **NOT SHOWN** | otherwise |
  | **NOT EVALUABLE** | per §3 |

* **No-harm:** **HOLDS** or **FAILS**, by the §3 bound.

## 5. Pre-written paper sentences
X and Y are the P1 point estimates with 95% CIs.

| condition | sentence |
|---|---|
| H1 = AUDIT PICK CUTS CONTAGION and no-harm HOLDS | "Serving the audit's top-ranked 4-bit checkpoint (AWQ, deficit 0.02 nats) instead of Google's QAT checkpoint (5.13 nats) cuts contagion after a laundered slip from 19.7% to X% at the same 4-bit weight precision, on 300 public states." |
| H1 = SMALLER CUT | "...reduces contagion from 19.7% to X%..." |
| H1 = NOT SHOWN | no ranking claim. "The audit's deficit did not predict contagion in a registered test" goes to the limitations |
| H2 = DOSE-RESPONSE SUPPORTED | "Contagion rises with the audit deficit (bf16/AWQ ≈ 0 → AutoRound 0.63 → QAT 5.13 nats: X% → Y% → 19.7%)." With PARTIAL, only the supported half is stated, with the n = 4 caveat |
| H3 = QUARANTINE STILL NEEDED AND WORKS | "Even on the best-ranked checkpoint, the history guard removes Z% of the remaining contagion: checkpoint choice and slipguard are complementary." |
| H3 = NOT EVALUABLE | "No contagion was detected under AWQ, so there was nothing for the guard to remove" |

## 6. Notes
* **The audit metric was fixed before this registration; behaviour was not.** This is a test of the audit's
  *behavioural validity*, not a refit.
* **Off-policy limit.** The states and laundered exemplars come from 31B QAT-ct histories, so the AWQ and AutoRound runs
  are off-policy, as bf16's was. This affects every arm equally.
* **Exploratory comparator.** The bf16 numbers are exploratory, so bf16 enters only the descriptive ordering, not any
  Holm test.
* **Memory.** "Same 4-bit weight precision" refers to weight bit-width. Exact checkpoint sizes are reported from the
  repos, not asserted here.
