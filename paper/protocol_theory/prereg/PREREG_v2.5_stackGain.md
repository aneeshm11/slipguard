# PREREG_v2.5 (addendum): the full slipguard stack vs the stock stack on public states (workstream D)

* **Written:** 2026-11-05, starting 13:58 UTC. **Frozen** when its sha256 is written to `PROGRESS.md`.
  Deviations go to `PREREG_DEVIATIONS.md` (this folder).
* **Blindness.** No v2.5 output exists; B builds and runs it after the freeze.
  * D has seen these registered summaries:
    * C1: P0 1.3% → P1 19.7%;
    * C5: P8a removal 98% [88, 110];
    * C12–C14: 13 natural first-edit slips, IPD 13 → 1, 0/582 valid calls changed;
    * v2.3: closer slips O0 1/600 vs O1 6/600; string-mode drift 0/342 vs 19/342 edits;
    * slipguard conformance and README numbers;
    * the development thinking-leak cell, 1,200/1,200.
  * D has **not** opened any emission file of C1, P8a or v2.3, and has seen no v2.4 output.
* **Relation to earlier registrations.** This is an addendum to PREREG_v2 (sha256 5da75e61…), v2.3 (7111525f…) and v2.4
  (e7af894b…). Conventions follow PREREG_v2 §3. Earlier files are unchanged.
* **Purpose.** This is the single registered test of the **whole** slipguard stack against the stock stack, in the
  three failure regimes it exists for:
  * F1, a contaminated history;
  * F2, framework tool-result serialization;
  * F3, a thinking-off leak.
* **It is composition only.** It uses frozen or shipped code with recorded hashes. No new modelling code is written. The
  only new code is B's glue script `experiments/intent_decoding/v25/stack_runner.py` (render → base decode → IPD →
  strict parse → log; no modelling).
  * B writes its sha256 to PROGRESS.md before the first generation, together with the hashes of the frozen confirm/
    files it imports: gemma_protocol b8dac830…, intent_decode bda60a08…, arms 5a521ae8…, prior 47f2853a….
  * B's IPD is verify-then-repair: it acts only after the call ends. So `rollback_resume` applied post hoc to a logged
    base emission is the **same algorithm** as live SLIPGUARD decoding on that sample, not an approximation (B).

## 1. The two stacks

| component | STOCK | SLIPGUARD |
|---|---|---|
| history | as the framework sends it | `slipguard.history.HistoryGuard` with shipped defaults: quarantine = E's frozen renderer (recovered call + `MalformedToolCall` error = the **P8a** rendering when the raw emission is available), raw-call removal, control-token neutralization. `native_tool_results=True` in F2 only |
| template (F1, F2) | P's July template (official; md5 f016bd4b…) | the same, so that F1/F2 isolate history + decoding + parsing |
| template (F3) | official July template | `slipguard/template/gemma4_july_guarded.jinja` |
| decoding | plain sampling, P's settings (T = 1.0, top-p 0.95, top-k 64, thinking on with B's budget emulation; F3 thinking off) | the same base sample; then **IPD (i+)** on the first call: B's frozen `rollback_resume(rule='nc', rules=('closer','opener'))` with the frozen prior |
| parsing / delivery | vLLM 0.19.1 `gemma4` lenient parser | slipguard strict parser; a strictly invalid residual is **loud** (no call delivered, error surfaced) |

**Hashes** (sha256; B re-verifies them before the first generation and logs any mismatch as a deviation):
* slipguard history:
  * `history/pipeline.py` b0740ed0…
  * `history/transforms.py` e64583bc…
  * `history/neutralize.py` e54626f9…
  * `_frozen/endtoend/export/quarantine_renderer.py` 5ca5c62c…
* slipguard parser: `parse/engine.py` 8aed8e4e…, `parse/schema.py` b8ce8dbe…, `parse/__init__.py` 20b58b62…
* slipguard integrations: `integrations/adk.py` 88f6f549…, `integrations/litellm_hook.py` f3961b83…
* templates: `template/gemma4_july_official.jinja` ae53464b… (md5 f016bd4b…, the template P served) and
  `template/gemma4_july_guarded.jinja` 533500b8…
* B's frozen package: `experiments/intent_decoding/confirm/`, combined sha256 2ee89869… (`FREEZE_MANIFEST.txt`)
* judges: A's `experiments/contagion/scripts/gemma_protocol.py` (`judge`, as used by the C1 analysis) and v2.3's
  `analyze_onset_v23.py` (drift). Their hashes are logged by B before analysis.

**Residual handling.** The slipguard parser decides strict validity. Every disagreement with B's `is_valid` is logged and
reported. Disagreements do not change the classification.

## 2. Outcome classification (next turn, natural; no edit is forced)
The classification is made per state, on the next turn's first edit call as the stack **delivers** it.

| class | definition |
|---|---|
| **harmful** | (a) **delivered-malformed**: A's judge flags the edit call as malformed, and the stack delivers it (a lenient parse into a tool call, or raw call text left in content); or (b) **silent corruption**: the delivered call is strictly valid but carries slip damage. Slip damage means A's judge flags it (look-alike residue such as `ℓ,<key>:` inside a value, or a copied corrupted argument), or, in F2, string-mode drift by the v2.3 definition |
| **loud** | the strict parser refuses the call. Not harmful; reported separately |
| **clean** | a delivered edit call that is strictly valid, has no judge flag and no drift |
| **no edit** | the next turn contains no edit call (not harmful) |

* **Primary estimand:** unconditional P(harmful next edit) per state (ITT), as in C1.
* **Secondary:** the conditional rate given an edit; the loud rate; harmful + loud; per-closer breakdown.
* Under STOCK the lenient parser delivers every judged-malformed edit. So harmful_STOCK equals C1's malformed-edit
  indicator (plus drift in F2).

## 3. Family 1 (primary): contaminated history
**States.** PREREG_v2 pool A1, 300 states (the C1 states; 31B QAT-ct).

**Arms.**
* **STOCK P1: reused** from A's PREREG_v2 confirmatory run (the C1 P1 jobs, server :8303; analysis frozen 34ea4647) and
  re-classified by §2.
* **SLIPGUARD P1, primary: the same-run replay R1.**
  * **History.** `HistoryGuard().apply(P1 messages, tools, raw_by_call_id)`. The laundered call is A's injected
    counterfactual, so its raw form comes from A's P1/P8a construction.
  * **Render identity (CPU).** The HistoryGuard history must render token for token to A's P8a context.
  * **Base emissions.** On every state where the identity holds, A's C1 **P8a emissions** are SLIPGUARD-before-IPD
    samples from the **same run and server** as STOCK.
  * **Then:** B's `rollback_resume` post hoc (server resumes only at slips, T 1.0, top-p 0.95, top-k 64, the state's
    seed), followed by the slipguard strict parse.
  * **Pairing** is by state. STOCK and SLIPGUARD are separate samples (P1 vs P8a jobs) from one run.
* **SLIPGUARD P1, secondary: the live run L1** (B's glue; GPU0 :8300). The same composition run end to end on a fresh
  sample: HistoryGuard → July template → base decode (one seed per state, thinking-budget emulation) → IPD on the first
  call → strict parse.
  * L1 confirms that the composed runtime behaves as the replay does.
  * It is compared with STOCK across runs. B notes C1 ran on :8303, so the build, args and top-k must be confirmed by A
    or the PI.
* **Replay preconditions**, confirmed by A and logged in `PREREG_DEVIATIONS.md` before any v2.5 outcome is opened:
  * A's run files hold s1/s2 text, finish, seed and sampling, but not the prompt. The glue re-renders each state with
    A's frozen pathway builder (P0/P1/P8a/O0/O1) and requires len = n_prompt. Mismatches are skipped and counted.
  * A states what sits between s1_text and s2_text (assumed: a forced `<|tool_call>`), and whether s2 stopped at the
    first `<tool_call|>`.
* **Switch rule:**
  * If the render identity holds on < 95% of states, or a replay precondition fails, L1 becomes the primary F1
    estimate. Its STOCK comparator is C1's P1, with the cross-run caveat stated.
  * This decision is logged before any v2.5 outcome is opened.
  * If L1 cannot finish its 300 states within the GPU slot, it is reported as partial.
* **Consistency (reported).** L1 agrees with R1 iff L1's harmful rate lies inside R1's 95% CI, or both are ≤ 1%. If they
  disagree in verdict, the paper uses the more conservative verdict and reports both.

**No-harm (P0, clean history).** B showed that two runs cannot be compared byte for byte: the same seed and prompt
reproduce bytes in only 267/528 long thinking generations. So no-harm is established within samples:

| # | check | rule |
|---|---|---|
| N1 | CPU: `HistoryGuard().apply(P0 messages)` returns byte-identical messages and the identical rendered prompt | 300/300; any exception is a defect, reported with ids |
| N2 | C14 byte identity, on every replay and live sample (P8a replay, P0 replay, O0 replay, L1). A base emission whose first call is strictly valid is delivered byte-identically. IPD changes an emission **only** where it intervenes, and every intervention is at a call A's judge flags as malformed: a closer or opener slip, i.e. a true slip | 0 violations. Any violation FAILS no-harm and is reported with the case |
| N3 | P0 harmful, non-inferiority: A's C1 P0 emissions with post-hoc IPD + strict parse (valid SLIPGUARD P0 samples by N1), vs the same emissions under lenient (STOCK P0 = C1's 1.3%) | RD(SLIPGUARD − STOCK) point ≤ 0, and 95% CI upper ≤ +1 pp |
| N4 | refusal cost: P0 loud rate under SLIPGUARD (strict refusals of emissions lenient delivers), Wilson CI | descriptive; if > 2%, the gain sentence must state it |

**Predictions (D's 80% PIs).** Basis:
* quarantine leaves about the P0-level onset (C5: removal 98%, so P8a ≈ 1.6%);
* IPD removes about 92% of closer slips (C13);
* the strict parser turns the remaining residue loud.

| quantity | prediction |
|---|---|
| STOCK P1 harmful | 19.7% (by construction: reused) |
| **SLIPGUARD P1 harmful (R1, primary)** | **0.3% [0, 1.0]** |
| SLIPGUARD P1 loud | 1.0% [0.3, 4.0] |
| RD(SLIPGUARD − STOCK) | −19.4 pp [−24, −15] |
| **relative reduction** | **98% [93, 100]** |
| L1 live harmful | 0.3% [0, 1.0]; render identity HistoryGuard(P1) = P8a on 300/300 |
| N1 / N2 | 300/300 / 0 violations |
| N3 | SLIPGUARD P0 harmful 0.2% [0, 0.8] vs STOCK 1.3% |
| N4 | P0 loud 1.0% [0.3, 3.0] |

**Decision rule (F1).**

| verdict | rule |
|---|---|
| **STACK GAIN CONFIRMED** | Holm-adjusted p(H1) < 0.05; relative reduction ≥ 0.90 with 95% CI_lo ≥ 0.75; N1–N3 hold |
| **STACK GAIN ATTENUATED** | Holm p < 0.05; reduction ≥ 0.50 with CI_lo > 0; N1–N3 hold; the confirmation rule fails |
| **GAIN WITH HARM** | the gain rules hold but N1, N2 or N3 fails. Reported; no gain sentence |
| **FAILS** | otherwise |

**Paper sentence** (X = 100·(1 − harmful_SG / harmful_STOCK) from the primary estimate):
* CONFIRMED (n = the number of analysed states): "On contaminated public states (n = …), slipguard removes X% [95% CI] of harmful edits (a% → b%),
  changes no valid call, and turns c% of turns into loud refusals."
* ATTENUATED: "...reduces harmful edits by X% [CI]...".
* FAILS or GAIN WITH HARM: no gain sentence. The result goes to the limitations.
* If R1 and L1 disagree in verdict, the paper uses the more conservative verdict and reports both.

## 4. Family 2: framework serialization (v2.3's O1)
**States.** v2.3's 600 S1_B1 first-edit states.
* **STOCK: reused** v2.3 O1 emissions (A's run), under the lenient parser.
* **SLIPGUARD (primary, same-runner replay).**
  * CPU identity **I2**: render(`HistoryGuard(native_tool_results=True).apply(O1 messages)`) = render(O0 messages)
    token for token. `native_tool_results` is the exact inverse of the ADK 1.36.1 + LiteLLM serialization.
  * On every state where I2 holds, v2.3's **O0 emissions** (same run as O1, shared seed per state) are
    SLIPGUARD-before-IPD samples. Then apply post-hoc IPD and the strict parse.
  * The replay preconditions of §3 apply to A's v2.3 run files (`rO_v23.jsonl`): re-render, check len = n_prompt, and
    confirm the s1/s2 junction.
* **Live confirmation (secondary).** The full composite runs live on the first 100 O1 states (B's glue) if GPU time
  remains (§7).

**Outcomes.** All are paired by state:
* (a) string-mode drift (v2.3 definition): unconditional per state, and among edits;
* (b) harmful closer slips, unconditional;
* (c) total harmful.

**Predictions (80% PIs).**

| quantity | STOCK | SLIPGUARD |
|---|---|---|
| drift among edits | 5.6% (19/342, by construction) | **0.2% [0, 1.0]** |
| closer-slip harmful | 1.0% (6/600) | 0.05% [0, 0.4] |
| I2 identity | — | 600/600 |
| live, 100 states | — | drift 0 edits [0, 2]; closer slips 0 [0, 1] |

**Decision rules.**
* **H2a (drift):**

  | verdict | rule |
  |---|---|
  | **DRIFT REMOVED** | Holm p < 0.05, and SLIPGUARD drift ≤ 1% of edits with Wilson upper ≤ 2.5% |
  | **DRIFT REDUCED** | Holm p < 0.05 otherwise |
  | **NOT SHOWN** | otherwise |

* **H2b (closer slips):** the exact one-sided McNemar test. **REMOVED** iff Holm p < 0.05. With ≈ 6 discordant pairs, a
  6–0 split gives p = 0.016, so power is limited. This is stated in advance.
* **If I2 holds on < 95% of states:** the replay is restricted to the identity states and reported as such.
* **If I2 holds on < 50%:** the live 100 becomes the primary F2 evidence, and Holm uses its tests.
* **Paper sentence:** "Under ADK/LiteLLM tool-result serialization, slipguard's history hook removes X% of escape-drift
  edits (a% → b% of edits) and Y of Z closer slips."

## 5. Family 3: thinking-off leak after a tool response
**States.** The 300 A1 states, with their P0 (clean) histories, rendered with `enable_thinking=false`. A state whose last
message is not a tool response is excluded and counted (expected 0).

**Arms.** This is a single request per state: render with `enable_thinking=false` and the named template, decode with
`skip_special_tokens=False`, and apply no thinking-budget emulation.
* **STOCK:** the official July template (sha256 ae53464b…; the template P served).
* **GUARDED:** slipguard's `gemma4_july_guarded.jinja` (sha256 533500b8…).
* Both run on the same server with P's sampling. Each state has one seed shared by both arms, and **max_tokens = 32**:
  only the opening of a thought is needed.

**Outcome.** The thought opens: the generated tokens contain the thought-open token `<|channel>` (id 100) followed by
`thought`.

**Predictions.** STOCK **99% [95, 100]** (development 1,200/1,200). GUARDED **0.3% [0, 2]** (L: 0/188 re-opened once the
closed thought is present).

**Template no-harm (CPU T-check), on all 300 states:**
1. With `enable_thinking=true`, the two renders are byte-identical: 300/300 predicted. Any difference is documented
   with ids, e.g. control-token text in tool data, which the guarded template neutralizes by design.
2. With `enable_thinking=false`, the guarded render equals the official render plus exactly `<|channel>thought\n<channel|>`
   (ids 100, 45518, 107, 101) appended. Any other difference is documented.

**Decision.**
* **THINKING-OFF HONOURED** iff all of these hold:
  * Holm p(H3) < 0.05 (exact McNemar);
  * GUARDED ≤ 2% with Wilson upper ≤ 3%;
  * STOCK ≥ 90%;
  * the T-check passes, or every difference it finds is a documented neutralization.
* **NOT SHOWN** otherwise, with the numbers.
* **Paper sentence:** "With thinking off, the stock template still opens a thought after a tool response in a% of public
  states; slipguard's template in b%." This replaces the development cell (1,200/1,200) in the gains table.

## 6. Statistics
* **Confirmatory Holm family** (α = 0.05, one-sided): **H1** (F1 harmful reduction; R1, or L1 under the switch rule),
  **H2a** (F2 drift), **H2b** (F2 closer slips), **H3** (F3 thought opening).
* **Tests and intervals:**
  * tests: exact McNemar on discordant pairs per state;
  * CIs: episode-cluster bootstrap (B ≥ 2,000, percentile) for RDs and the relative reduction; Wilson for single rates.
* **Outside Holm:**
  * the no-harm checks (N1–N4, T-check, I2, render identity), which are guarantees or non-inferiority bounds;
  * secondary quantities: conditional estimands, the loud rate, harmful + loud, per-closer shares, live-vs-replay
    agreement, glue/parser disagreements, tokens and latency.
* The STOCK numbers are the registered measurements from C1 and v2.3. What v2.5 adds is SLIPGUARD on the same states.

## 7. Run plan and budget (B; GPU0 :8300 after v2.4; ≤ 75 min of GPU time)
1. **CPU, before any generation:**
   * hashes (§1) and the glue's sha256, logged;
   * N1, the HistoryGuard(P1) = P8a render identity, I2, and the template T-check.
2. **F3:** 600 generations capped at 32 tokens; the two arms share all but the last 4 prompt tokens. About 5–10 min.
3. **Replay resumes** (IPD only at slips) for R1 (P8a), N3 (P0) and F2 (O0). These are the primaries' GPU needs.
   Expected ≤ 30 resumes, ≤ 5 min.
4. **L1 live:** SLIPGUARD P1 on 300 states. About 50–60 min at ≈ 16–20 min per 100 thinking-on generations (B).
5. **F2 live:** the first 100 O1 states, only while the budget remains. An incomplete run is reported as partial
   (it is secondary).
* **Stop rule:** at 75 min of GPU time, or at the end of the slot the PI sets, the run stops.
  * The order above makes every primary (F3, R1, N3, F2 replay) finish first.
  * B estimates that F3 + replays + L1 end at about 15:50–15:55 if v2.4 frees :8300 at 14:40–14:45. The PI decides on
    the slot; a truncated L1 is reported as partial.

## 8. Firewall
* B builds the replays from A's files with the frozen scripts.
* The analysis scripts are hashed before any v2.5 output is opened.
* D opens no outcome before B's analysis file exists.
* Any analysis not listed here is labelled exploratory.
