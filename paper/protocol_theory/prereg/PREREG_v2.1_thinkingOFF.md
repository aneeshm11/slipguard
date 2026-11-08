# PREREG_v2.1 (addendum): thinking-OFF contagion battery (31B), workstream D

* **Written:** 2026-11-04 ~16:15 UTC. **Frozen** when its sha256 is written to `PROGRESS.md`.
  Deviations go to `PREREG_DEVIATIONS.md` (this folder).
* **Blindness.** At writing time no thinking-OFF output existed in `experiments/contagion/out/main/` (checked
  16:13 UTC), and the run is scheduled for about 20:00–22:00 UTC. D has seen only discovery results with thinking ON.
* **Governs** A's thinking-OFF battery on :8302:
  * model: 31B QAT-ct, vLLM 0.19.1;
  * contexts: the **same 300 discovery gate contexts** (A's gate set), June template, logged sampling;
  * arms: **P0, P1, P5, P6, P8a**;
  * A's injection code renders with `enable_thinking=false`, so the model emits the call with no thought.
* **Relation to earlier registrations.** This is an addendum to PREREG_v2 (sha256 5da75e61…). It reuses PREREG_v2's
  conventions and outcome-rule form unless stated otherwise. PREREG_v1 and v2 are unchanged.

## 1. Discovery anchors (thinking ON, same 300 gate contexts unless noted; unconditional ITT)

| contrast | gate (discovery) | held-out (contexts 300–599) |
|---|---|---|
| RD(P1 − P0) | **+35.3 pp** [29.4, 41.1] (P0 5.0%, P1 40.3%) | +42.5 pp |
| RD(P6 − P0) | **+21.3 pp** [16.1, 26.4] | +26.5 pp [21.7, 31.4] |
| P8a removal of the P1 excess | **113%** [107, 122] | 104% |
| P5 removal of the P1 excess | ≈ 108% (P5 −2.7 pp vs P0) | — |

**Evidence used to transport the predictions to thinking OFF:**
* B: first-edit census-malformed is higher with thinking OFF (interim 23.8% vs 18.7%).
* D's identical-context replay (July template, T = 0.2, 633 contexts), 31B no-think vs think:
  * clean history 13.1% vs 10.6%;
  * ≥ 1 malformed edit in context 71.4% vs 64.8%;
  * last edit malformed (q₁) 80.6% vs 73.8%;
  * so contagion is at least as strong without a thought.
* Mechanism: copy-on-retry does not need a thought (85% of P1 slips are byte-exact copies), and the thought that
  sometimes accompanies a retry ("My apologies, I messed up…") is not what produces the copy.

## 2. Registered predictions (D's 80% prediction intervals)

| # | contrast (unconditional ITT, primary) | prediction | θ_D used by the rule |
|---|---|---|---|
| T1 | RD(P1 − P0) | **+38 pp [+22, +52]** | +35.3 |
| T2 | RD(P6 − P0) | **+22 pp [+8, +38]** | +21.3 |
| T3 | P8a removal of the P1 excess | **1.05 [0.85, 1.20]** | removal rule |
| T4 | P5 removal of the P1 excess | **1.00 [0.80, 1.15]** | removal rule |

Secondary and descriptive predictions (no outcome rule; reported with CIs):
* Levels: P0 6% [3, 12]; P1 44% [28, 60]; P6 28% [14, 45]; P8a and P5 each ≤ P0 + 1 pp.
* Paired thinking effect on the same contexts (OFF − ON, using A's thinking-ON gate runs): RD on P1 +5 pp [−5, +15]; RD on
  P0 +1.5 pp [−2, +6].
* Byte-exact copies are ≥ 80% of malformed P1 edits (ON 85.4%).
* P(next call is an edit) under OFF is within ±10 pp of ON in every arm.

## 3. Outcome rules (same form as PREREG_v2 §3)
* **Risk-difference claims (T1, T2)**, with θ_D the thinking-ON gate value:
  * **REPLICATES** iff CI_lo > 0, the Holm-adjusted p < 0.05 (§4), and θ_C ≥ 0.5·θ_D;
  * **ATTENUATED** iff CI_lo > 0 and Holm p < 0.05, but θ_C < 0.5·θ_D;
  * **FAILS** otherwise.
* **Removal claims (T3, T4):**
  * **REPLICATES** iff removal ≥ 0.70 with CI_lo ≥ 0.50 and Holm p < 0.05 for RD(P1 − Q) > 0;
  * **ATTENUATED** iff removal ≥ 0.40 with CI_lo > 0, but the replication rule fails;
  * **FAILS** otherwise;
  * **not evaluable** if T1 FAILS (no excess to remove).
* **Statement the paper may make:** "the loop and its fix hold with thinking disabled" iff T1, T2 and T3 all REPLICATE.
  "With attenuation" iff all three are at least ATTENUATED.

## 4. Statistics
* **Estimands:** the unconditional ITT P(next call is a malformed `edit_file`) is primary; P(malformed | edit) is
  secondary. Contrasts are paired by context, on contexts complete in every arm.
* **CIs:** attempt-cluster bootstrap, B ≥ 2,000, percentile. One-sided bootstrap p-values = (1 + #{RD* ≤ 0})/(B + 1).
* **Family-wise Holm** over the four one-sided primary tests:
  * H1: RD(P1 − P0) > 0;
  * H2: RD(P6 − P0) > 0;
  * H3: RD(P1 − P8a) > 0;
  * H4: RD(P1 − P5) > 0.
* **Missing jobs:** reported per arm. If > 5% of an arm is missing, the complete-case and all-available analyses are
  both reported.
* **Reporting:** risk differences first; no headline ratio with an infinite CI; ON and OFF side by side on the same
  300 contexts.
* **Judge:** A's unchanged vLLM-parse judge.
