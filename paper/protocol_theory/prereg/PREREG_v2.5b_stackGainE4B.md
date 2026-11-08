# PREREG_v2.5b (addendum): full slipguard stack vs stock on Gemma-4-E4B. v2.5 Family 1 (R1 replay) only (workstream D)

* **Written:** 2026-11-05, starting 21:10 UTC. **Frozen** when its sha256 is written to `PROGRESS.md`.
  Deviations go to `PREREG_DEVIATIONS.md` (this folder).
* **Blindness.**
  * D has seen these registered E4B summaries:
    * C9: P0 2.3% → P1 7.0%, RD +4.7 pp [1.4, 8.0];
    * C11: P8a removal 114% [67, 225].
  * D has not opened any E4B emission file, and has seen no v2.5 or v2.5b outcome.
* **Relation to earlier registrations.** This copies **PREREG_v2.5 Family 1** (frozen 14:00:57 UTC, sha256 50f8a395…)
  with the model changed to **Gemma-4-E4B (QAT-ct)**. Everything not restated here follows v2.5 §1–§3, §6 and §8:
  * the stack definitions and hashes;
  * the outcome classification;
  * the no-harm checks N1–N4;
  * the verdict rules and paper-sentence rules;
  * the statistics and firewall.
* **Scope.** F1 only, and only the **same-run replay R1**. There is no live run (L1), no F2 and no F3.
* **Purpose.** To test whether the Gemma-4-tailored stack carries across model sizes.

## 1. Arms (same 300 PREREG_v2 A1 states, which E4B shares with 31B; A's public E4B confirmatory run)
* **STOCK** = A's E4B confirmatory **P1** emissions, classified under the vLLM 0.19.1 lenient parser (v2.5 §2).
* **SLIPGUARD (R1)** = A's E4B confirmatory **P8a** emissions, with these steps applied:
  1. B's frozen `rollback_resume(rule='nc', rules=('closer','opener'))` with the frozen prior (B's `confirm/` package,
     combined sha256 2ee89869…), post hoc;
  2. the slipguard strict parser. A strictly invalid residual is **loud**.
* **Validity of R1.** It is valid on every state where a CPU check confirms that `HistoryGuard().apply(P1 messages,
  tools, raw_by_call_id)` renders, token for token, to A's E4B P8a context. The renderer is E's frozen
  `quarantine_renderer.py` (5ca5c62c…). The tokenizer is shared across Gemma-4 sizes.
* **Pairing** is by state.
* **Glue.** B's v2.5 glue script (`experiments/intent_decoding/v25/stack_runner.py`), as hashed for v2.5, with the
  model/server argument pointed at E4B. Any other code change is a deviation and is logged with its hash before any
  outcome is opened.
* **IPD on E4B.** IPD's cut scoring and resume use the E4B model itself, through the server below. The prior and the
  rules are the frozen 31B-derived ones. IPD has not been validated on E4B before, so the intervals below are wider than
  v2.5's.

## 2. Preconditions (B verifies on CPU; logged in `PREREG_DEVIATIONS.md` before any outcome is opened)
1. **The same replay preconditions as v2.5**, now on A's E4B run files:
   * the s1/s2 junction (the model-generated `<|tool_call>`);
   * stop id 49 only, with no truncation;
   * re-render with A's frozen builders gives len = n_prompt for P0, P1 and P8a.
   * Budget-forced records are handled as in v2.5 (deviation entry of 14:06 UTC): flagged, with a sensitivity analysis
     excluding them.
2. **Render identity:** HistoryGuard(P1) = E4B P8a context.
3. **N1:** HistoryGuard leaves the P0 history byte-identical, and the rendered prompt is identical.
4. **Server.** IPD continuations run on the idle **E4B QAT-ct server on :8311** (GPU1). B compares its model revision,
   vLLM version, max_model_len, and sampling defaults (T 1.0, top-p 0.95, generation_config top-k) against A's E4B
   confirmatory records.

**Switch rules:**
* **Identity.** If the render identity or the replay preconditions hold on < 95% of states, v2.5b reports **NOT
  EVALUABLE** for the failing part, with counts. No live substitute is run within this registration.
* **Server.**
  * If :8311's configuration differs from A's E4B run in any listed item, R1 stays primary, and every resumed record is
    flagged "cross-server resume".
  * A **worst-case sensitivity** treats every resumed record as harmful.
  * If the worst case changes the verdict, the paper uses the worst-case verdict.
  * Resumes occur only at detected slips, so they are expected on ≤ 15 of the 600 records.

## 3. Outcomes, no-harm and statistics (as v2.5)
* **Primary:** unconditional P(harmful next edit) per state (v2.5 §2), STOCK vs SLIPGUARD, paired by state.
* **Tests and intervals:** exact one-sided McNemar on per-state discordant pairs, plus an episode-cluster bootstrap
  (B ≥ 2,000) for the RD and the relative reduction.
* **No-harm:**
  * N1 (CPU, P0 no-op);
  * N2 (C14 within-sample on every replayed P8a and P0 sample; every IPD intervention is at a judged slip);
  * N3 (P0 non-inferiority: E4B P0 emissions + post-hoc IPD + strict vs lenient; RD point ≤ 0 and CI upper ≤ +1 pp);
  * N4 (P0 loud rate).
* **Holm:** a single confirmatory test (H1-E4B), so α = 0.05. This registration is a separate family from v2.5.

## 4. Predictions (D's 80% prediction intervals)
Basis:
* E4B's P8a is about 1.6% (removal 114% of the 4.7 pp excess);
* IPD removes most of the closer slips in that residue;
* E4B's non-closer malformations (a larger share in a small model) become loud under the strict parser, not harmful.

| quantity | prediction |
|---|---|
| STOCK P1 harmful | 7.0% (by construction: reused) |
| **SLIPGUARD harmful (R1)** | **0.3% [0, 1.0]** (≤ 0.5% point) |
| SLIPGUARD loud | 1.5% [0.3, 4.0] |
| RD(SLIPGUARD − STOCK) | −6.7 pp [−9.5, −4.0] |
| **relative reduction** | **96% [86, 100]** |
| render identity / N1 / N2 | 300/300 / 300/300 / 0 violations |
| N3 | SLIPGUARD P0 harmful 0.3% [0, 1.0] vs STOCK 2.3% |
| N4 | P0 loud 1.5% [0.3, 4.0] |
| resumed records (P8a + P0) | ≈ 10 [3, 20] |

**Power note.** STOCK has about 21 harmful states. If SLIPGUARD has ≤ 2, the exact McNemar p is far below 0.05. The
lower bound of the relative-reduction CI is the binding part of the CONFIRMED rule: ≥ 0.75 with about 21 events.

## 5. Verdict and paper sentence (v2.5's rules)
| verdict | rule |
|---|---|
| **STACK GAIN CONFIRMED (E4B)** | p(H1-E4B) < 0.05; relative reduction ≥ 0.90 with 95% CI_lo ≥ 0.75; N1–N3 hold |
| **STACK GAIN ATTENUATED (E4B)** | p < 0.05; reduction ≥ 0.50 with CI_lo > 0; N1–N3 hold; the confirmation rule fails |
| **GAIN WITH HARM** | the gain rules hold but N1, N2 or N3 fails |
| **FAILS** | otherwise |
| **NOT EVALUABLE** | per the §2 switch rule |

**Pre-written sentences** (X = 100·(1 − harmful_SG/harmful_STOCK)):

| condition | sentence |
|---|---|
| CONFIRMED | "The same stack carries to Gemma-4-E4B: on the 300 contaminated public states it removes X% [95% CI] of harmful edits (7.0% → b%) and changes no valid call; c% of turns become loud refusals." |
| ATTENUATED | "...reduces harmful edits on E4B by X% [CI]..." |
| CONFIRMED on both v2.5 F1 and v2.5b | the paper may say "across Gemma-4 sizes (31B, E4B)" |
| otherwise | no cross-size claim; the result goes to the limitations |

## 6. Run plan and budget (B; :8311, GPU1; ≤ 30 min of GPU time)
1. CPU: the hashes, the §2 preconditions, the render identity and N1. All are logged before any outcome is opened.
2. Post-hoc IPD on the E4B P8a and P0 emissions. Server resumes happen only at detected slips: expected about 10
   short requests, a few minutes.
3. Analysis with the frozen v2.5 analysis path.

There is no live generation, so E's 12B population on :8301 (same GPU) is barely affected. Stop rule: 30 GPU-minutes.
