# PREREG_v2.2 (addendum): flag-off manipulation check, a thought-suppressed arm set S, and a reasoning-stripped arm H (workstream D)

* **Written:** 2026-11-04 17:37–17:50 UTC. **Frozen** when its sha256 is written to
  `PROGRESS.md`. Deviations go to `PREREG_DEVIATIONS.md` (this folder).
* **Blindness.** At writing time no output of v2.1, S or H existed in `experiments/contagion/out/main/` (checked
  17:36 UTC). A starts about 18:10–18:30 UTC: v2.1 on :8300, v2.2 on :8302.
* **Relation to earlier registrations.**
  * **PREREG_v2.1 (sha256 bb3696da…) stays frozen and is run exactly as written** (flag off).
  * This addendum corrects only its *interpretation*, adds a manipulation check, and registers two new arm sets.
  * PREREG_v1, v2 and E_PREDICTIONS_v1 are unchanged. Conventions follow PREREG_v2 §3: unconditional ITT primary, paired
    by context, attempt-cluster bootstrap with B ≥ 2,000, D's 80% prediction intervals.

## 1. Correction to v2.1's premise and its manipulation check
* **The fact** (B's replays, June and July templates): `enable_thinking=false` does **not** suppress the thought.
  * The model opens `<|channel>thought` in 583/587 June-OFF and 584/588 July-OFF samples.
  * Median thought length is about 680 characters, vs about 952 with thinking on.
  * 298/300 OFF contexts still render earlier logged thoughts into history.
* v2.1's sentence "the model emits the call with no thought" is therefore false. v2.1 tests the **shipped
  thinking-off flag**, not the absence of reasoning.
* **Reading of v2.1's verdicts T1–T4 (registered now, before any v2.1 output):** they are verdicts on "contagion and its
  fix under the shipped thinking-off flag", **not** "without reasoning". v2.1's predictions and rules are unchanged.
* **Manipulation check M-v2.1** (reported with every v2.1 table):
  * share of samples whose generated text opens a thought channel: **predicted ≥ 0.95** (point 0.99);
  * median thought length in characters: **680 [450, 900]**, vs the thinking-on gate runs' median;
  * both are reported per arm.
* If fewer than 80% of samples open a thought, the v2.1 tables are also reported split by "thought opened / not
  opened", and the verdicts are labelled "mixed condition".

## 2. Arm set S: thought suppressed (primary for "without reasoning")
* **Contexts:** the same 300 discovery gate contexts (A's gate set), June template, logged sampling.
* **Arms:** P0, P1, P6, P8a (A's constructions, unchanged).
* **Generation:** the model's own closed-thought form `<|channel>thought\n<channel|>` is prefilled immediately after
  the generation prompt, so the model must emit its next turn with no reasoning. Prior thoughts stay in history as logged.
* **Manipulation check M-S:** the share of samples that re-open a thought channel after the prefill is **predicted
  ≤ 0.05**. If it exceeds 0.10, the S verdicts are also reported on the samples that did not re-open, and S is labelled
  "thought-prefilled" rather than "thought-free".
* **Discovery anchors:**
  * thinking on, gate: RD(P1 − P0) +35.3 pp; RD(P6 − P0) +21.3 pp; P8a removal 113%; held-out +42.5 pp / +26.5 pp / 104%.
  * D's identical-context replay already ran a no-reasoning condition: `order_replay.py` without `--think` prefills
    `<|tool_call>call:edit_file{` directly after the generation prompt. On 633 Gemma contexts (July template, T = 0.2):

    | condition | clean history | ≥ 1 malformed edit in context | RD | q₁ |
    |---|---|---|---|---|
    | no thought | 13.1% | 71.4% | +58 pp | 0.81 |
    | with a thought | 10.6% | 64.8% | +54 pp | 0.74 |

  * Removing the thought does not weaken contagion; if anything it strengthens it slightly. Mechanism: the thought is
    where the model sometimes notices the failure and rewrites cleanly (80/266 clean rewrites under P1 with thinking on).

### 2.1 Predictions for S (80% PI) and outcome rules

| # | contrast (unconditional ITT) | prediction | θ_D for the rule |
|---|---|---|---|
| S1 | RD(P1 − P0) | **+38 pp [+22, +55]** | +35.3 |
| S2 | RD(P6 − P0) | **+24 pp [+8, +40]** | +21.3 |
| S3 | P8a removal of the P1 excess | **1.05 [0.80, 1.20]** | removal rule |

Secondary and descriptive predictions (no rule):
* levels: P0 6.5% [3, 13]; P1 45% [28, 63];
* paired S − ON on the same contexts: P1 +5 pp [−5, +18];
* clean rewrites of the same edit under P1: **lower** than with thinking on (ON 30%): S 15% [5, 30];
* byte-exact copies ≥ 80% of malformed P1 edits.

Rules (PREREG_v2 §3 form):
* **S1 and S2:**
  * REPLICATES iff CI_lo > 0, Holm-adjusted p < 0.05 and θ_C ≥ 0.5·θ_D;
  * ATTENUATED iff CI_lo > 0 and Holm p < 0.05, but θ_C < 0.5·θ_D;
  * FAILS otherwise.
* **S3:**
  * REPLICATES iff removal ≥ 0.70 with CI_lo ≥ 0.50 and Holm p < 0.05 for RD(P1 − P8a) > 0;
  * ATTENUATED iff removal ≥ 0.40 with CI_lo > 0, but the replication rule fails;
  * FAILS otherwise;
  * not evaluable if S1 FAILS.
* **Holm (family S, separate from v2.1's family)** over three one-sided tests: RD(P1 − P0) > 0, RD(P6 − P0) > 0,
  RD(P1 − P8a) > 0.
* **Statement the paper may make:** "the loop and its fix hold without reasoning" iff S1, S2 and S3 all REPLICATE.

## 3. Arm set H: realistic reasoning-stripped history (included; secondary, run if lane time allows)
* **Why:** plain ADK drops `reasoning_content` from history in about 91% of histories (C's finding).
* **Construction:** the same 300 gate contexts; ALL prior reasoning is stripped from the history; thinking stays ON (the
  model thinks normally in its new turn).
* **Arms:** P0 and P1.
* **Prediction:** RD(P1 − P0) **+33 pp [+16, +50]**, since the copy is of the rendered *call*, not of the thoughts. P0 is
  5% [2, 11].
* **Rule:** the RD rule above with θ_D = +35.3. This is its own one-test family (α = 0.05, no Holm).
* If H is not run, no verdict is recorded.

## 4. Reporting
* ON (discovery), v2.1 (flag off), S (thought suppressed) and H (reasoning stripped) are shown side by side on the same
  300 contexts.
* Risk differences come first; there is no headline ratio with an infinite CI.
* The manipulation checks appear in the same table.
* Judge: A's unchanged vLLM-parse judge.
