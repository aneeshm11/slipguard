# PREREG_v1 — mechanism of in-context error imitation (workstream D; governs A's dose tier and the P0-A1/A2 arms)

* **Written:** 2026-11-04 11:46 UTC by workstream D (theory). **Frozen** when its sha256 is recorded in `PROGRESS.md`. After
  that, any change is a new version (`PREREG_v2.md`) and every deviation goes to `PREREG_DEVIATIONS.md` (same folder).
* **Governs (outcome data not yet in existence when this was written):**
  * A's dose tier `ap-ctg-31b-D`, plan `experiments/contagion/data/plan_31b_T3r.jsonl`: P0 (k = 0) and P1, P4 at k = 1, 2, 4 on
    the 305-context k ≥ 4 set. Output file `out/main/r31b_old_D.jsonl` exists at writing time: **False**.
  * The P0-A1 arms still to be added (r-dose, lag-2, P6k, P4′, P8a/P8b, P9), held-out contexts 300–599, the final P6/P7 at
    n = 300, the NT replication, and the P0-A2 natural-slip quarantine replay.
* **Exact numbers:** `prereg/compute_predictions.py` → `prereg/predictions_v1.json` (pure arithmetic, no data read).

## 1. Data already seen (the conditioning set, stated openly)
All 31B numbers below are A's (`experiments/contagion/progress.md`, 11:25 and 11:30 UTC), using the June template.
P(malformed | next call is edit_file):
* **Final k = 1 gate**, 300 contexts / 256 attempts: P0 5.7% [3.5, 9.2]; **P1k1 46.2% [40.2, 52.2]**; P2 (error only) 1.3%;
  P3 48.5%; P4 3.4%; P5 3.4%. P4 and P5 each remove 105.7% of the P1 excess. 12B (A's 10:47 interim table, 292
  contexts): P0 2.2% → P1 12.4%.
* **Copy check at k = 1** (31B P1k1, 266 edits):
  * 105 byte-exact copies of the corrupted value, all malformed, = 85.4% [78.1, 90.5] of malformed edits;
  * 80 clean rewrites of the same edit: 0 malformed;
  * non-copy other edits: 20.6% [12.7, 31.6] malformed.
* **Interim P6** (corrupted re-render + the original *success* response, so no retry motive; 70 edits): 28.6% [19.3, 40.1],
  with **0 verbatim copies**.
* **Interim P7** (P1 with a `"` closer; 70 edits): 18.6% [11.2, 29.2]. Slips use the injected `"` in 7/13 and the model's own
  backtick in 6/13. P0 slips use `"` in 1/16.
* **Observational (logs; confounded by content stickiness):** immediate-retry rate R = 1 → 2 → 3: 77.6% → 84.0% → 91.1%.
  MR run coefficient β = 1.05 [0.89, 1.21]. After one clean edit the hazard returns to 7.7% (vs 4.3% clean).
* **Consequence, stated before the dose data:** if the interim P6 holds at full n, *pure copy-on-retry* is not the whole
  mechanism. Format is also induced without a retry motive. The dose tier therefore discriminates among the three
  mechanisms below, with M1 read as *recency-1 template copying* (format and value), not as verbatim copying only.

## 2. Mechanisms (from R2 §6(b); the predictions are stated relative to each set's OWN k = 1 arm)
Notation: p₀ and p₁ are the measured P0 and P1(k = 1) rates on the same context set. Δ_k := logit P(k) − logit P(1).
* **M1 — recency-1 template copying.** The next edit copies the format/value of the *most recent* same-tool call only.
  Dose-independent: Δ_k = 0. lag-2 (corrupted call 2nd most recent, most recent valid) ≈ baseline. P7 slips carry the
  injected closer.
* **M2 — exemplar urn / attention dilution.** Weight ∝ number of corrupted exemplars, logit ∝ β log k. β = 1.05 (MR;
  β = 1, a pure count urn, gives the lower edge of the band). So Δ₂ = +0.73 and Δ₄ = +1.46. lag-2 is elevated. P7 slips
  carry the injected closer.
* **M3 — Bayesian evidence accumulation** (in-context inference; logit linear in the count). Each corrupted exemplar adds
  D₁ = logit p₁ − logit p₀, so Δ_k = (k − 1)·D₁, saturating in probability. lag-2 is elevated. P7 slips are mixed (the
  inferred "broken format" is expressed with the model's own closer as well).

## 3. Numeric predictions (registered)

### 3.1 k-dose, P1 at k = 1, 2, 4 (305-context set; primary mechanism test)

| mechanism | Δ₂ (logit) | Δ₄ (logit) | P1(k = 2) and P1(k = 4) at the plan anchor (p₁ = 0.43, p₀ = 0.065) | at the final-gate anchor (p₁ = 0.462, p₀ = 0.057) |
|---|---|---|---|---|
| M1 | 0 | 0 | 0.43 / 0.43 | 0.46 / 0.46 |
| M2 (β = 1.05; band β = 1.00) | +0.73 (+0.69) | +1.46 (+1.39) | **0.61** (0.60) / 0.76 (0.75) | 0.64 (0.63) / 0.79 (0.77) |
| M3 | +D₁ = +2.38 (anchor) / +2.65 (gate) | +3·D₁ | **0.89** / 0.999 | 0.92 / 0.9996 |

The set's own p₁ and p₀ replace the anchors when the run completes, so the predictions are the logit differences. The
numeric columns illustrate them; the plan's r = 2 figures are 0.43 / 0.61 / 0.89.

### 3.2 Secondary predictions, same mechanisms

| quantity | M1 | M2 | M3 |
|---|---|---|---|
| r-dose: the same corrupted call + error shown r = 2, 4 times (Δ vs r = 1) | 0 / 0 | +0.73 / +1.46 | +D₁ / +3D₁ |
| lag-2 vs P0: excess as a share of the k = 1 excess, (P_lag2 − p₀)/(p₁ − p₀) | < 0.25 (≈ 0) | ≥ 0.5 (≈ 1 for a recency-insensitive urn) | ≥ 0.5 |
| P6 at k = 2, 4 (anchor P6(1) = 0.286) | 0.29 / 0.29 | 0.45 / 0.63 | 0.73 / 0.99 |
| P7: share of slips using the injected `"` | ≥ 0.80 | ≥ 0.80 | 0.3–0.7 ("mixed") |
| new-content edits under P1(k): slip rate vs k (by edit class) | flat | rises, logit ∝ β log k | rises, logit linear in k |
| copies of an *earlier* (not most recent) corrupted value, k ≥ 2 | rare (< 5% of edits) | proportional to their count | proportional to their count |
| order imitation under P4(k): share of next edits emitted old-first (k = 1 seen: 148/263 = 0.563) | flat at 0.56 | 0.73 (k = 2), 0.85 (k = 4) | → ≈ 1.0 |
| P4(k) quarantine: rate vs p₀ | ≤ p₀ + 2 pp at all k (excess removed ≥ 90%) under **every** mechanism (no corrupted exemplar remains) | same | same |

### 3.3 Other P0-A1/A2 arms (D's point predictions, with the probability D assigns to each prediction holding)

| arm | D's prediction | P(holds) |
|---|---|---|
| NT (July template) | P1/P0 ≥ 3× with CI_lo > 1, i.e. the July template does not fix the loop (replay RR 6.1 for 31B under July) | 0.90 |
| P4′ (canonical re-render, model's own new-first order + success) | removes ≥ 80% of the P1 excess; de-corruption, not the order flip, is the active ingredient (T4: order matters only in contaminated histories) | 0.80 |
| P8a (shipped quarantine, recovered call + `MalformedToolCall`) | removes ≥ 70% of the P1 excess (error-only P2 is 1.3%) | 0.75 |
| P8b (sanitized, `old_string` still missing, + error) | removes ≥ 50%, and less than P8a | 0.60 |
| P9 (P1 + an informative error message) | still ≥ 50% of the P1 excess; feedback does not remove the exemplar | 0.70 |
| Final P6 at n = 300 (gate half) | RD(P6 − P0) ≥ +5 pp with CI_lo > 0 | 0.80 |
| Final P7 at n = 300 | share of injected `"` among slips 0.55 (80% PI 0.40–0.70) | — |
| A2 natural-slip quarantine replay | history-borne share h = 1 − q(P5)/q(L) ≈ 0.6 (80% PI 0.4–0.8): copy-on-retry of a *sticky* natural slip is partly content-driven | — |

### 3.4 D's own forecast for the dose tier
P1(k = 2) = 0.52 (80% PI 0.44–0.62) and P1(k = 4) = 0.57 (80% PI 0.45–0.70) at p₁ = 0.46. Region probabilities under rule
D-M (§4.2): M1 0.45, M2 0.40, M3 0.05, undiscriminated or none 0.10. Rationale: the copy share (85%) and the full reset
after one clean edit favour recency; the interim P6 and P7 show some count-independent induction; M3's near-certain
saturation is inconsistent with the 20.6% non-copy rate at k = 1.

## 4. Decision rules

### 4.1 Verbatim from `ideation/neurips_review/UPGRADE_PLAN.md` (lines 181–188, P0-A1)
**Pre-registered decision rules.**

| question | rule |
|---|---|
| Format induction | **Claimed iff** RD(P6 − P0) ≥ +5 pp with CI_lo > 0 on **both** the gate and held-out halves. Otherwise the name is "copy-on-retry". |
| Copying | Confirmed iff ≥ 80% of P1 malformed edits are verbatim copies **and** P7 slips carry `"` well above P0's 1/16. |
| Shipped quarantine works | Iff P8a and P4′ each remove ≥ 70% of the P1 excess (unconditional), with CI_lo ≥ 50%. |
| July template | "Does not fix the loop" iff NT P1/P0 ≥ 3× with CI_lo > 1. |

### 4.2 Mechanism rule D-M (new; primary for the dose tier)
* Estimate Δ̂₂ and Δ̂₄ on the 305 set: paired by context, attempt-cluster bootstrap with B = 2,000, 95% percentile CIs.
* Regions on Δ₂ use the midpoints between the predictions at the measured D₁ (at the gate anchor: M1 < 0.364 ≤ M2 < 1.691 ≤ M3).
* A mechanism is **supported** iff the whole 95% CI of Δ̂₂ lies inside its region **and** Δ̂₄ is consistent with its shape:
  * M1: the CI of Δ̂₄ contains 0;
  * M2: the CI of Δ̂₄ − 2Δ̂₂ contains 0;
  * M3: P1(4) ≥ 0.95.
* If the CI straddles a boundary, report "not discriminated between Mi and Mj". If Δ̂₂ < 0 (CI_hi < 0), or the shapes
  contradict every mechanism, report "none of M1–M3" and fit the free curve.
* Mixtures, e.g. M1 + induction (a step at k = 1 then flat with a non-zero P6), are reported as such. They are not forced
  into a single class.

### 4.3 Verbatim from the plan (lines 210–212, P0-A2)
- **Rule:**
  - h ≥ 0.7: "quarantine is the dominant lever for 31B" survives, and its ε_q feeds the DP.
  - h ≤ 0.4: content stickiness dominates. Re-rank the levers as IPD-first and say so.

### 4.4 Verbatim from the plan (lines 678–699, §6)
## 6. Pre-registration and statistical rules (written by D and R, committed before the data they govern)

- **Families and primary contrasts.** Holm correction within each family.

  | family | primary contrasts |
  |---|---|
  | F1 mechanism (31B) | P1 − P0; P6 − P0 on new content; P8a and P4′ removal; NT P1 − P0 |
  | F2 cross-family | P1-L − P0 and P5 removal, per Qwen model |
  | F3 decoders | IPD vs each baseline on delivered-malformed; exact intent on gold slips |
  | F4 end to end | the 2 co-primary endpoints, `full′` vs base, 31B |

- **Held-out confirmation.** A's contexts 300–599 are analysed once, after the lock. B's gold slips are split 50/50 into tuning and test sets, and τ is tuned on the tuning half only.
- **Reporting.**
  - Risk differences first; ratios second.
  - No headline ratio with an infinite CI.
  - Per-template tables (June vs July).
  - Natural vs forced edits reported separately.
  - Base vs FT always reported separately.
- **Clustering.** Attempts (injection), tasks (e2e) and contexts (replay). B ≥ 2,000 for the gates.
- **Unblinding.** E's outcome analysis is not allowed before D's Nov 6 00:00 predictions. Every deviation is logged in `PREREG_DEVIATIONS.md`.

---

## 5. Analysis plan
* **Primary outcome:** P(malformed | next call is edit_file), judged by A's full vLLM-parse judge (`scripts/analyze_injection.py`),
  unchanged.
* **Secondary outcomes:**
  * ITT P(malformed edit | any next call) and P(next call is edit_file);
  * the edit-class split from `scripts/copy_check.py`: byte-exact copy of the most recent corrupted value; copy of an
    earlier corrupted value; clean rewrite of the same edit; same-content variant; new content;
  * the closer of every malformed edit (P7);
  * the order of every generated edit (P4(k) order imitation).
* **Contrasts:**
  * risk differences first, then ratios;
  * Δ_k on the logit scale for rule D-M;
  * removal fraction (P1(k) − P4(k))/(P1(k) − p₀) at each k.
* **Uncertainty:** attempt-cluster bootstrap, B ≥ 2,000; Wilson intervals for single rates.
* **Multiplicity:** Holm within family F1 (§4.4). Rule D-M is one pre-specified classification, not a family of tests.
* **Exclusions:** none beyond A's existing filters (protocol-clean prior history, k_usable ≥ 4). Contexts whose next call is
  not an edit count in ITT only. No outcome-based exclusion.
* **Missing or failed jobs:**
  * reported per arm;
  * if > 5% of the jobs of an arm are missing, the paired analysis is restricted to contexts complete in every arm, and both
    versions are reported.
* **Stopping:** none. The planned n is used, with no interim looks at the dose tier.
* **Replication:**
  * the 12B dose tier, if run, is analysed with the same rule (anchors = its own p₀, p₁);
  * held-out contexts 300–599 are analysed once (§4.4).
* **Theory updates that this pre-registration triggers** (in `theory.md`, after the data):
  * the identified kernel h(k, lag) replaces Prop. 3.3's observational cascade law;
  * the DP of Prop. 3.4 is re-run with the measured ε_q (P5/P8a) and the history-borne share h (A2).
