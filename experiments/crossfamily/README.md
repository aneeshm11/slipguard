# Workstream X: is the laundering loop general? A cross-family and cross-format replication

**Question.** Gemma-4's laundering loop works like this. A lenient parser and the chat template's re-render turn one
delimiter slip into a well-formed but corrupted exemplar, and the model then copies it on retry and imitates it on new
edits. Gemma-4-31B's next-edit malformed rate goes from 5.7% to 46.2%.

Does the same thing happen in another model family with another tool-call format? We test:
- **Qwen3-8B** and **Qwen3-32B-FP8**: hermes JSON, escaped strings.
- **Qwen3.5-9B**: qwen3_coder XML, escape-free, named asymmetric `<parameter=…>` tags.

There are two halves:
- **Model side (GPU).** Causal history injections on real agent states, rendered with each model's own template.
- **Stack side (CPU).** What each format's production parser does with that format's native slip.

The pre-registration is `prereg.md` (2026-11-04T12:15Z, before any GPU job). Deviations are in
`PREREG_DEVIATIONS.md`. The running log is `progress.md`. Machine-readable results are in `results.json`.

## TL;DR (discovery replication on A's main-track contexts; all unconditional rates per context, n = 300 paired)
1. **The laundering loop's copy-on-retry does NOT replicate in any Qwen model. The pre-registered cross-family rule
   FAILS in all three.** S1, S2 and S3 are false everywhere, and all 6 Holm-adjusted p = 1.0.
   P(next call is a malformed edit), original history (P0) vs one laundered exemplar + ADK error (P1L):
   - Qwen3-8B: 0.3% → 0.7%, RD +0.3 pp [0.0, +1.0].
   - Qwen3-32B-FP8: 0.7% → 0.7%, RD 0.0 [−1.4, +1.3].
   - Qwen3.5-9B: 0.0% → 0.0%.
   - Reference, Gemma-4-31B on the same 300 states (workstream A): 5.0% → 40.3%, RD +35.3 pp [+29.8, +41.1].
   - Copy check: Qwen *repairs* the laundered value when it retries. There are 0 verbatim copies in 562 P1L edits, and
     the 187 clean retries are 0% malformed.
   - Held-out contexts 300–599 give the same null in all three models: RD(P1L − P0) = 0.0 pp, CIs within
     ±1.4 pp. Across 572 held-out P1L edits there are 0 verbatim copies.
2. **Weak format induction does transfer.** Arm P6 shows the laundered exemplar followed by a *success* response, so
   there is no retry motive. It raises Qwen3-8B to 5.0% (RD +4.7 pp [+2.1, +7.5]), and the held-out set gives the
   same +4.7 pp [+2.3, +7.3].
   - Qwen3.5-9B: +1.0 pp [0.0, +2.3] on the gate and +3.0 pp [+1.0, +5.3] on the held-out set.
   - Qwen3-32B: +0.7 pp on the gate (not significant) and +1.7 pp [0.0, +3.5] on the held-out set.
   - The slips reproduce the laundered junk-key structure (for example `` `,old_string: `` plus junk keys inside
     JSON / XML). Both 8B estimates fall just below the registered +5 pp induction threshold.
   - Gemma-31B: +21.3 pp.
3. **The format proposition holds on CPU** (1,598 real Gemma slip payloads; vLLM 0.19.1 and 0.31.0 agree):
   - **Gemma `<|"|>`** silently absorbs the next argument 100% of the time. 88.5% of those calls re-render to an
     identical corrupted call.
   - **hermes JSON** native slips fail **loud** 100% on the non-streaming path the harness uses. The streaming path
     instead delivers a tool call with non-JSON arguments, 100%.
   - **qwen3_coder XML** re-synchronises at the next `<parameter=` (next argument preserved, 99.4–100%), but
     **silently**:
     - the look-alike stays in the value, and the template re-renders it as a well-formed exemplar 100% of the time;
     - no syntax check can flag it (0%);
     - only an omitted closer is truly repaired;
     - opener drift (`<old_string>`) absorbs like Gemma.
   - Natural Qwen slips are rare and loud. First-edit census (first-edit contexts, original history):
     - Qwen3-8B 2.7% (13/16 unparsed);
     - Qwen3-32B 1.3% (4/4 unparsed);
     - Qwen3.5-9B 0/600;
     - against the logged Gemma-31B rate of 17–19% on the same contexts.
4. **A Qwen-native protocol slip appeared, and the quarantine texts trigger it.** This is exploratory (requested by the
   PI) and labelled as such.
   - Qwen3-8B often writes its tool call inside an *unclosed* `<think>`: 15% at P0, 11% in the census. vLLM 0.19.1's
     reasoning parser delivers such a turn as reasoning only, so the call is dropped. vLLM 0.31's Qwen3 engine
     extracts it.
   - The removal note (P5) raises this to 48%, and E's shipped-quarantine error (P8a) to 30%.
   - Net "any protocol failure" (malformed or dropped edit) on 8B: P5 +32.7 pp [+26.3, +38.9]; P8a +16.3 pp
     [+10.4, +22.3].
   - The side effect is absent in Qwen3-32B (P5 2.7%, P8a 1.3% vs P0 2.7%) and in Qwen3.5-9B, whose template pre-opens
     the thought.
   - A fix tuned on Gemma can hurt another family's protocol boundary.
5. **Implication for the paper.** The UPGRADE_PLAN §4 *variant B* applies: the copy loop is model-specific, and the
   general lesson is the stack- and format-level result (lenient parsers plus template re-rendering, and
   format-dependent loud / silent / absorbed behaviour). The PREREG_v2 confirmatory rerun on workstream P's public corpus
   confirms this (next section).

## PREREG_v2 confirmatory rerun on workstream P's public corpus (2026-11-05): benchmark coverage
Battery: P's pool S1_A1, first 300 states. Census: S1_B1, first 600 states. P's harness texts and sampling were used.
The code is frozen in `scripts/v2_frozen/` (`SHA256SUMS`, written before the pools existed). The labels are PREREG_v2
§3.3's (sha256 `5da75e61…0d73ac`), judged on the full sample. RDs are paired, unconditional and in pp, with
episode-cluster bootstrap 95% CIs (B = 10,000).

| model | format | induction RD(P6 − P0) | induction verdict | copy RD(P1L − P0) | copy verdict | census malformed edit |
|---|---|---|---|---|---|---|
| Qwen3-8B | hermes JSON | +4.7 [+2.0, +7.7] | GENERALIZES | +1.7 [0.0, +3.7] | FAILS | 1.5% (CONSISTENT) |
| Qwen3-32B-FP8 | hermes JSON | +1.0 [−1.7, +3.7] | FAILS | −1.7 [−4.5, +1.0] | FAILS | 1.5% (CONSISTENT) |
| Qwen3.5-9B | qwen3_coder XML | +0.7 [0.0, +1.7] | FAILS | 0.0 [0.0, 0.0] | FAILS | 0.0% (CONSISTENT) |
| gpt-oss-20b ¹ | harmony | +0.3 [−2.6, +3.2] | FAIL | −0.3 [−3.0, +2.4] | FAIL | 1.3% (n = 300) |
| Qwen3-Coder-30B-A3B ¹ | qwen3_coder XML (non-thinking) | +0.3 [−0.7, +1.4] | FAIL | +0.3 [−0.7, +1.6] | FAIL | 0.0% (n = 300) |
| Devstral-Small-2-24B ¹ ² | mistral v13 | **+7.0 [+4.2, +10.2]** | **PASS** | 0.0 [−1.0, +1.0] | FAIL | 0.3% (n = 299) |
| Qwen3.8-27B ¹ ³ | qwen3_coder XML (thinking) | +4.7 [+2.4, +7.2] | FAIL ³ | +1.0 [0.0, +2.3] | FAIL | 0.0% (n = 300) |

- Qwen rows use the PREREG_v2 labels: induction = X4, copy = X1, census = X5 (pool B1, first 600).
- ¹ Extension rows come from the benchmark extension (`prereg_ext.md`, frozen 2026-11-04T18:51Z), on the same A1 states.
  - Induction verdict: the registered secondary rule, RD ≥ 5 pp and CI_lo > 0.
  - Copy verdict: the registered S1–S3 rule.
  - Census: pool B1, first 300.
  - Decisions are in `out/ext/results_ext.json`.
- ² Devstral details:
  - 13 render errors are excluded per prereg_ext §8, giving n = 298 paired.
  - 19 of the 22 P6 malformed edits reproduce the laundered junk-key shape (`",old_string`).
  - Both halves are stable: H1 +6.1, H2 +8.0.
- ³ Qwen3.8-27B details:
  - Its induction RD is below the registered 5 pp threshold (14 vs 0 events, CI_lo > 0). Under the PREREG_v2 X4 rule used for
    the Qwen rows (CI_lo > 0 and RD ≥ 2.5 pp) it would read GENERALIZES, like Qwen3-8B's identical +4.7, but that label is not
    registered for this model.
  - All 14 P6 malformed edits and all 3 P1L malformed edits reproduce the laundered shape (`` `,old_string: ``).
  - The P8a removal flag (1.0) is degenerate: the P1L excess is 3 events and not significant (Holm-adjusted p 0.38).
- X2 (native slip, P1N) and X3 (P5 / P8a removal) FAIL in all three Qwen models.
- X1 GENERALIZES in 0 of 3 models, so the PREREG_v2 statement "generalizes across families" is **false**. F2c Holm,
  6 tests: all adjusted p ≥ 0.34.
- The rerun reproduces the discovery result.
- Outputs:
  - `out/v2/results_v2.json` (decisions);
  - `out/v2/ana_<mk>[_H1|_H2].json` (analyses);
  - `out/v2/run_manifest_qwen3-32b.json` (32B server record);
  - job-order and serving notes in `PREREG_DEVIATIONS.md`;
  - exploratory metrics in `out/v2/pf_<mk>.json`, not used for any verdict.

## 1. Design
**Contexts**
- **Battery.** Workstream A's 300 gate contexts. Each is a real Gemma-4-31B pre-edit state from the main-track logs
  (teacher runs excluded) whose most recent prior `edit_file` was valid and succeeded.
- **Held-out tier.** A's contexts 300–599.
- **Census.** Gemma-only first-edit contexts from workstream B's set: 600 per model, 300 for 32B.

**Rendering**
- The logged OpenAI messages and tool declarations are rendered through **vLLM 0.19.1's own chat path**:
  ChatCompletionRequest → `parse_chat_messages` → the model's HF template, thinking on.
- This matters. Calling `apply_chat_template` directly on the logged messages drops the list-valued user content in
  Qwen3 (−4K tokens), and it crashes the Qwen3.5 template, which needs dict arguments.
- Histories, including Gemma's thoughts carried in `reasoning_content`, are off-policy, exactly as in A's 12B/E4B
  replications.

**Arms** (k = 1; the most recent prior edit is replaced). The message-level constructions are A's and E's, frozen in
`scripts/frozen/`.

| arm | history shown to the model |
|---|---|
| P0 | original |
| P1L | **laundered exemplar**: the swallowed-argument dict vLLM's gemma4 parser makes of a backtick-closer slip (`new_string` ends in `` `,old_string: ``, `old_string` missing, junk keys) + the ADK missing-parameter error, rendered in the model's own format |
| P1N | **the format's native slip through its own production parser**: the slipped argument's closing delimiter is replaced by a backtick (`"` in JSON; `\n</parameter>` in XML). hermes fails **loud** (300/300): the raw text stays in the content, followed by the harness's generic nudge. qwen3_coder re-synchronises **silently** (300/300): the call keeps a trailing-backtick residue, is executed, and the diff in the success response is patched to show the residue |
| P5 | call + response removed, one-line note |
| P6 | P1L exemplar + the original *success* response (no retry motive) |
| P8a | E's frozen shipped quarantine applied to the P1L history: recovered call + MalformedToolCall error |

**Generation**
- Streamed `/v1/completions` on the raw prompt.
- Sampling: the logged temperature and top_p, with top_k = 20. One seed per context, shared by all arms.
- The thinking budget of 4,096 tokens is applied post hoc, as in A: the thought is cut and `</think>` is forced.
- Generation stops at EOS only, max 7,168 new tokens. Servers are vLLM 0.19.1, started by the PI.

**Judge** (one definition)
- Pipeline: the Qwen3 reasoning split (vLLM `Qwen3ReasoningParser`), then the format's production parser (hermes /
  qwen3_coder), then the **first** call is judged.
- A call is malformed if any of these holds:
  - the parser returns no call although one was opened;
  - a required key is missing;
  - an unknown key appears (`edit_file`);
  - A's look-alike + `,key:` leak, or its JSON spelling;
  - an XML tag fragment or a special token inside a value;
  - non-object arguments.
- A's subset and the strict reference parsers are reported as a cross-tab.
- False-positive check: the judge flags **0 / 3,013** historical calls re-rendered in each format.

**Endpoint.** The primary endpoint is unconditional P(next call is a malformed `edit_file`) per context. The rule
(UPGRADE_PLAN §P0-X) requires, in at least one Qwen model:
- RD(P1L − P0) ≥ +10 pp, Holm-adjusted;
- P1L / P0 ≥ 3 with CI_lo > 1 (Haldane + exact McNemar when P0 has < 5 events);
- P5 removing ≥ 50% of the excess.

## 2. Results
<!-- RESULTS:BEGIN (generated by scripts/report.py) -->
### Qwen3-8B (hermes JSON): battery (A's 300 gate contexts) and census

| arm | P(edit) | P(malformed edit), unconditional (primary) | P(malformed \| edit) | RD vs P0, uncond. [95% CI] | ratio vs P0 [95% CI] |
|---|---|---|---|---|---|
| P0 original history | 67.7% [62.2, 72.7] (n=300) | 0.3% [0.1, 1.9] (n=300) | 0.5% [0.1, 2.7] (n=203) | - | - |
| P1L laundered exemplar + ADK error | 60.0% [54.4, 65.4] (n=300) | 0.7% [0.2, 2.4] (n=300) | 1.1% [0.3, 4.0] (n=180) | +0.3 pp [+0.0, +1.0] | 2.00 [1.00, inf] |
| P1N native slip through own parser | 66.0% [60.5, 71.1] (n=300) | 0.7% [0.2, 2.4] (n=300) | 1.0% [0.3, 3.6] (n=198) | +0.3 pp [-0.7, +1.6] | 2.00 [0.00, inf] |
| P5 removed + note | 43.7% [38.2, 49.3] (n=300) | 0.3% [0.1, 1.9] (n=300) | 0.8% [0.1, 4.2] (n=131) | +0.0 pp [+0.0, +0.0] | 1.00 [1.00, 1.00] |
| P6 laundered exemplar + success | 66.7% [61.2, 71.8] (n=300) | 5.0% [3.0, 8.1] (n=300) | 7.5% [4.6, 12.0] (n=200) | +4.7 pp [+2.1, +7.5] | 15.00 [3.67, inf] |
| P8a shipped quarantine (E, recovered) | 58.3% [52.7, 63.8] (n=300) | 1.0% [0.3, 2.9] (n=300) | 1.7% [0.6, 4.9] (n=175) | +0.7 pp [+0.0, +1.7] | 3.00 [1.00, inf] |

Census (first-edit contexts, original history): P(call) 88.0% [85.2, 90.4] (n=600); P(edit) 71.3% [67.6, 74.8] (n=600); P(malformed edit) 2.7% [1.7, 4.3] (n=600); P(malformed | edit) 3.7% [2.3, 6.0] (n=428); P(malformed | any call) 3.0% [1.9, 4.9] (n=528); malformed flags {'unparsed': 13, 'extra_key': 3}. Logged Gemma-4-31B next call on the same contexts: malformed 17.0% [14.2, 20.2] (n=600).

P5 removal of the P1L excess (uncond.): 1.0 [1.0, 1.0] (P1L 0.7%, P5 0.3%, P0 0.3%; n=300; undefined when P1L shows no excess over P0).

P8a removal of the P1L excess (uncond.): -1.0 [-4.0, 1.0] (P1L 0.7%, P8a 1.0%, P0 0.3%; n=300; undefined when P1L shows no excess over P0).

**Pre-registered rule:** S1 False, S2 False (haldane+exact_mcnemar (P0 events < 5)), S3 False -> **FAIL**.

Copy check (edits only): class n / malformed rate
| arm | verbatim copy of injected value | clean retry | same-content variant | new content | unparsed/other | share of malformed = copies | non-copy edits malformed |
|---|---|---|---|---|---|---|---|
| P0 | 0 | 4 / 0.0% [0.0, 49.0] | 14 / 0.0% [0.0, 21.5] | 184 / 0.0% [0.0, 2.1] | 1 / 100.0% [20.6, 100.0] | 0.0% [0.0, 79.3] (n=1) | 0.5% [0.1, 2.7] (n=203) |
| P1L | 0 | 60 / 0.0% [0.0, 6.0] | 34 / 0.0% [0.0, 10.2] | 84 / 0.0% [0.0, 4.4] | 2 / 100.0% [34.2, 100.0] | 0.0% [0.0, 65.8] (n=2) | 1.1% [0.3, 4.0] (n=180) |
| P6 | 2 / 100.0% [34.2, 100.0] | 2 / 0.0% [0.0, 65.8] | 14 / 14.3% [4.0, 39.9] | 174 / 1.7% [0.6, 5.0] | 8 / 100.0% [67.6, 100.0] | 13.3% [3.7, 37.9] (n=15) | 6.6% [3.9, 10.9] (n=198) |
| P8a | 0 | 77 / 0.0% [0.0, 4.8] | 19 / 0.0% [0.0, 16.8] | 76 / 0.0% [0.0, 4.8] | 3 / 100.0% [43.9, 100.0] | 0.0% [0.0, 56.1] (n=3) | 1.7% [0.6, 4.9] (n=175) |
| P1N | 1 / 100.0% [20.6, 100.0] | 16 / 0.0% [0.0, 19.4] | 18 / 0.0% [0.0, 17.6] | 162 / 0.0% [0.0, 2.3] | 1 / 100.0% [20.6, 100.0] | 50.0% [9.4, 90.5] (n=2) | 0.5% [0.1, 2.8] (n=197) |

### Qwen3-32B-FP8 (hermes JSON): battery (A's 300 gate contexts) and census

| arm | P(edit) | P(malformed edit), unconditional (primary) | P(malformed \| edit) | RD vs P0, uncond. [95% CI] | ratio vs P0 [95% CI] |
|---|---|---|---|---|---|
| P0 original history | 74.0% [68.8, 78.6] (n=300) | 0.7% [0.2, 2.4] (n=300) | 0.9% [0.2, 3.2] (n=222) | - | - |
| P1L laundered exemplar + ADK error | 79.3% [74.4, 83.5] (n=300) | 0.7% [0.2, 2.4] (n=300) | 0.8% [0.2, 3.0] (n=238) | +0.0 pp [-1.4, +1.3] | 1.00 [0.00, inf] |
| P1N native slip through own parser | 73.3% [68.1, 78.0] (n=300) | 1.3% [0.5, 3.4] (n=300) | 1.8% [0.7, 4.6] (n=220) | +0.7 pp [-0.7, +2.4] | 2.00 [0.00, inf] |
| P5 removed + note | 79.7% [74.8, 83.8] (n=300) | 1.3% [0.5, 3.4] (n=300) | 1.7% [0.7, 4.2] (n=239) | +0.7 pp [-0.7, +2.0] | 2.00 [0.50, inf] |
| P6 laundered exemplar + success | 73.3% [68.1, 78.0] (n=300) | 1.3% [0.5, 3.4] (n=300) | 1.8% [0.7, 4.6] (n=220) | +0.7 pp [-1.0, +2.3] | 2.00 [0.25, inf] |
| P8a shipped quarantine (E, recovered) | 82.3% [77.6, 86.2] (n=300) | 1.0% [0.3, 2.9] (n=300) | 1.2% [0.4, 3.5] (n=247) | +0.3 pp [-1.0, +1.8] | 1.50 [0.00, inf] |

Census (first-edit contexts, original history): P(call) 75.0% [69.8, 79.6] (n=300); P(edit) 59.3% [53.7, 64.7] (n=300); P(malformed edit) 1.3% [0.5, 3.4] (n=300); P(malformed | edit) 2.2% [0.9, 5.6] (n=178); P(malformed | any call) 2.2% [0.9, 5.1] (n=225); malformed flags {'unparsed': 4}. Logged Gemma-4-31B next call on the same contexts: malformed 19.3% [15.3, 24.2] (n=300).

P5 removal of the P1L excess (uncond.): None [-4.0, 5.0] (P1L 0.7%, P5 1.3%, P0 0.7%; n=300; undefined when P1L shows no excess over P0).

P8a removal of the P1L excess (uncond.): None [-3.0, 3.0] (P1L 0.7%, P8a 1.0%, P0 0.7%; n=300; undefined when P1L shows no excess over P0).

**Pre-registered rule:** S1 False, S2 False (haldane+exact_mcnemar (P0 events < 5)), S3 False -> **FAIL**.

Copy check (edits only): class n / malformed rate
| arm | verbatim copy of injected value | clean retry | same-content variant | new content | unparsed/other | share of malformed = copies | non-copy edits malformed |
|---|---|---|---|---|---|---|---|
| P0 | 0 | 3 / 0.0% [0.0, 56.1] | 12 / 0.0% [0.0, 24.2] | 205 / 0.0% [0.0, 1.8] | 2 / 100.0% [34.2, 100.0] | 0.0% [0.0, 65.8] (n=2) | 0.9% [0.2, 3.2] (n=222) |
| P1L | 0 | 89 / 0.0% [0.0, 4.1] | 40 / 0.0% [0.0, 8.8] | 107 / 0.0% [0.0, 3.5] | 2 / 100.0% [34.2, 100.0] | 0.0% [0.0, 65.8] (n=2) | 0.8% [0.2, 3.0] (n=238) |
| P6 | 0 | 1 / 0.0% [0.0, 79.3] | 14 / 0.0% [0.0, 21.5] | 201 / 0.0% [0.0, 1.9] | 4 / 100.0% [51.0, 100.0] | 0.0% [0.0, 49.0] (n=4) | 1.8% [0.7, 4.6] (n=220) |
| P8a | 0 | 111 / 0.0% [0.0, 3.4] | 35 / 0.0% [0.0, 9.9] | 98 / 0.0% [0.0, 3.8] | 3 / 100.0% [43.9, 100.0] | 0.0% [0.0, 56.1] (n=3) | 1.2% [0.4, 3.5] (n=247) |
| P1N | 1 / 100.0% [20.6, 100.0] | 9 / 0.0% [0.0, 29.9] | 20 / 0.0% [0.0, 16.1] | 187 / 0.0% [0.0, 2.0] | 3 / 100.0% [43.9, 100.0] | 25.0% [4.6, 69.9] (n=4) | 1.4% [0.5, 4.0] (n=219) |

### Qwen3.5-9B (qwen3_coder XML): battery (A's 300 gate contexts) and census

| arm | P(edit) | P(malformed edit), unconditional (primary) | P(malformed \| edit) | RD vs P0, uncond. [95% CI] | ratio vs P0 [95% CI] |
|---|---|---|---|---|---|
| P0 original history | 65.7% [60.1, 70.8] (n=300) | 0.0% [0.0, 1.3] (n=300) | 0.0% [0.0, 1.9] (n=197) | - | - |
| P1L laundered exemplar + ADK error | 48.0% [42.4, 53.6] (n=300) | 0.0% [0.0, 1.3] (n=300) | 0.0% [0.0, 2.6] (n=144) | +0.0 pp [+0.0, +0.0] | n/a |
| P1N native slip through own parser | 56.0% [50.3, 61.5] (n=300) | 0.0% [0.0, 1.3] (n=300) | 0.0% [0.0, 2.2] (n=168) | +0.0 pp [+0.0, +0.0] | n/a |
| P5 removed + note | 62.7% [57.1, 68.0] (n=300) | 0.3% [0.1, 1.9] (n=300) | 0.5% [0.1, 2.9] (n=188) | +0.3 pp [+0.0, +1.0] | inf [inf, inf] |
| P6 laundered exemplar + success | 62.7% [57.1, 68.0] (n=300) | 1.0% [0.3, 2.9] (n=300) | 1.6% [0.5, 4.6] (n=188) | +1.0 pp [+0.0, +2.3] | inf [inf, inf] |
| P8a shipped quarantine (E, recovered) | 50.7% [45.0, 56.3] (n=300) | 0.0% [0.0, 1.3] (n=300) | 0.0% [0.0, 2.5] (n=152) | +0.0 pp [+0.0, +0.0] | n/a |

Census (first-edit contexts, original history): P(call) 99.8% [99.1, 100.0] (n=600); P(edit) 34.3% [30.6, 38.2] (n=600); P(malformed edit) 0.0% [0.0, 0.6] (n=600); P(malformed | edit) 0.0% [0.0, 1.8] (n=206); P(malformed | any call) 0.0% [0.0, 0.6] (n=599); malformed flags {}. Logged Gemma-4-31B next call on the same contexts: malformed 17.0% [14.2, 20.2] (n=600).

P5 removal of the P1L excess (uncond.): None [None, None] (P1L 0.0%, P5 0.3%, P0 0.0%; n=300; undefined when P1L shows no excess over P0).

P8a removal of the P1L excess (uncond.): None [None, None] (P1L 0.0%, P8a 0.0%, P0 0.0%; n=300; undefined when P1L shows no excess over P0).

**Pre-registered rule:** S1 False, S2 False (haldane+exact_mcnemar (P0 events < 5)), S3 False -> **FAIL**.

Copy check (edits only): class n / malformed rate
| arm | verbatim copy of injected value | clean retry | same-content variant | new content | unparsed/other | share of malformed = copies | non-copy edits malformed |
|---|---|---|---|---|---|---|---|
| P0 | 0 | 0 | 13 / 0.0% [0.0, 22.8] | 184 / 0.0% [0.0, 2.1] | 0 | n/a | 0.0% [0.0, 1.9] (n=197) |
| P1L | 0 | 38 / 0.0% [0.0, 9.2] | 45 / 0.0% [0.0, 7.9] | 61 / 0.0% [0.0, 5.9] | 0 | n/a | 0.0% [0.0, 2.6] (n=144) |
| P6 | 0 | 1 / 0.0% [0.0, 79.3] | 16 / 6.2% [1.1, 28.3] | 171 / 1.2% [0.3, 4.2] | 0 | 0.0% [0.0, 56.1] (n=3) | 1.6% [0.5, 4.6] (n=188) |
| P8a | 0 | 40 / 0.0% [0.0, 8.8] | 39 / 0.0% [0.0, 9.0] | 73 / 0.0% [0.0, 5.0] | 0 | n/a | 0.0% [0.0, 2.5] (n=152) |
| P1N | 0 | 20 / 0.0% [0.0, 16.1] | 27 / 0.0% [0.0, 12.5] | 121 / 0.0% [0.0, 3.1] | 0 | n/a | 0.0% [0.0, 2.2] (n=168) |

### Held-out tier (A's contexts 300-599; registered secondary) -- RD vs P0, unconditional [95% CI]

| model | P0 | P1L | P5 | P6 |
|---|---|---|---|---|
| Qwen3-8B (hermes JSON) | 1.3% [0.5, 3.4] (n=300) | 1.3% [0.5, 3.4]; RD +0.0 [-1.3, +1.3] | 1.7% [0.7, 3.8]; RD +0.3 [-1.4, +2.1] | 6.0% [3.8, 9.3]; RD +4.7 [+2.3, +7.3] |
| Qwen3-32B-FP8 (hermes JSON) | 0.3% [0.1, 1.9] (n=300) | 0.3% [0.1, 1.9]; RD +0.0 [-1.0, +1.0] | 0.7% [0.2, 2.4]; RD +0.3 [-0.7, +1.4] | 2.0% [0.9, 4.3]; RD +1.7 [+0.0, +3.5] |
| Qwen3.5-9B (qwen3_coder XML) | 0.0% [0.0, 1.3] (n=300) | 0.0% [0.0, 1.3]; RD +0.0 [+0.0, +0.0] | 0.3% [0.1, 1.9]; RD +0.3 [+0.0, +1.0] | 3.0% [1.6, 5.6]; RD +3.0 [+1.0, +5.3] |

### Reference: Gemma-4-31B on the same 300 gate contexts (workstream A, read-only)

| A arm (X analogue) | P(malformed edit), uncond. | RD vs P0 [95% CI] |
|---|---|---|
| P0k0 (P0) | 5.0% [3.0, 8.1] (n=300) | - |
| P1k1 (P1L) | 40.3% [34.9, 46.0] (n=300) | +35.3 pp [+29.8, +41.1] |
| P3k1 (P1N (hermes analogue: raw text + nudge)) | 39.0% [33.7, 44.6] (n=300) | +34.0 pp [+28.3, +39.9] |
| P5k1 (P5) | 2.3% [1.1, 4.7] (n=300) | -2.7 pp [-5.6, +0.0] |
| P6k1 (P6) | 26.3% [21.7, 31.6] (n=300) | +21.3 pp [+16.4, +26.4] |
| P8ak1 (P8a) | 0.3% [0.1, 1.9] (n=300) | -4.7 pp [-7.2, -2.3] |

### EXPLORATORY: Qwen-native reasoning-delimiter slip and "any protocol failure" (PI request; not pre-registered)

A call written inside an unclosed `<think>` is delivered by vLLM 0.19.1's reasoning parser as reasoning only (no call).
PF_edit = registered malformed edit OR edit call dropped this way. Unconditional rates; RD vs P0 [95% CI].

| model | arm | dropped call (any) | PF_edit | RD(PF_edit) vs P0 |
|---|---|---|---|---|
| Qwen3-8B (hermes JSON) | C0 | 11.2% [8.9, 13.9] | 9.5% [7.4, 12.1] | - |
| Qwen3-8B (hermes JSON) | P0 | 15.3% [11.7, 19.9] | 13.0% [9.7, 17.3] | - |
| Qwen3-8B (hermes JSON) | P1L | 19.0% [15.0, 23.8] | 16.7% [12.9, 21.3] | +3.7 pp [-0.7, +8.0] |
| Qwen3-8B (hermes JSON) | P1N | 5.7% [3.6, 8.9] | 4.7% [2.8, 7.7] | -8.3 pp [-12.8, -3.9] |
| Qwen3-8B (hermes JSON) | P5 | 48.0% [42.4, 53.6] | 45.7% [40.1, 51.3] | +32.7 pp [+26.3, +38.9] |
| Qwen3-8B (hermes JSON) | P6 | 15.3% [11.7, 19.9] | 18.0% [14.1, 22.7] | +5.0 pp [+1.7, +8.4] |
| Qwen3-8B (hermes JSON) | P8a | 29.7% [24.8, 35.1] | 29.3% [24.5, 34.7] | +16.3 pp [+10.4, +22.3] |
| Qwen3-32B-FP8 (hermes JSON) | C0 | 10.3% [7.4, 14.3] | 7.7% [5.2, 11.2] | - |
| Qwen3-32B-FP8 (hermes JSON) | P0 | 2.7% [1.4, 5.2] | 3.0% [1.6, 5.6] | - |
| Qwen3-32B-FP8 (hermes JSON) | P1L | 0.7% [0.2, 2.4] | 1.3% [0.5, 3.4] | -1.7 pp [-3.9, +0.3] |
| Qwen3-32B-FP8 (hermes JSON) | P1N | 1.0% [0.3, 2.9] | 1.7% [0.7, 3.8] | -1.3 pp [-3.6, +1.0] |
| Qwen3-32B-FP8 (hermes JSON) | P5 | 2.7% [1.4, 5.2] | 2.7% [1.4, 5.2] | -0.3 pp [-2.6, +1.7] |
| Qwen3-32B-FP8 (hermes JSON) | P6 | 4.3% [2.5, 7.3] | 4.0% [2.3, 6.9] | +1.0 pp [-1.3, +3.3] |
| Qwen3-32B-FP8 (hermes JSON) | P8a | 1.3% [0.5, 3.4] | 1.7% [0.7, 3.8] | -1.3 pp [-3.6, +1.0] |
| Qwen3.5-9B (qwen3_coder XML) | C0 | 0.2% [0.0, 0.9] | 0.0% [0.0, 0.6] | - |
| Qwen3.5-9B (qwen3_coder XML) | P0 | 0.0% [0.0, 1.3] | 0.0% [0.0, 1.3] | - |
| Qwen3.5-9B (qwen3_coder XML) | P1L | 0.0% [0.0, 1.3] | 0.0% [0.0, 1.3] | +0.0 pp [+0.0, +0.0] |
| Qwen3.5-9B (qwen3_coder XML) | P1N | 0.0% [0.0, 1.3] | 0.0% [0.0, 1.3] | +0.0 pp [+0.0, +0.0] |
| Qwen3.5-9B (qwen3_coder XML) | P5 | 0.0% [0.0, 1.3] | 0.3% [0.1, 1.9] | +0.3 pp [+0.0, +1.0] |
| Qwen3.5-9B (qwen3_coder XML) | P6 | 0.0% [0.0, 1.3] | 1.0% [0.3, 2.9] | +1.0 pp [+0.0, +2.3] |
| Qwen3.5-9B (qwen3_coder XML) | P8a | 0.0% [0.0, 1.3] | 0.0% [0.0, 1.3] | +0.0 pp [+0.0, +0.0] |

Figure: `out/fig_forest_rd.{png,svg}` (numbers in `out/fig_forest_rd.json`).

**F2 Holm** (6 tests): raw {'qwen3-8b:H1': 0.36416, 'qwen3-8b:H2': 0.37016, 'qwen3-32b:H1': 0.61474, 'qwen3-32b:H2': 0.85721, 'qwen3.5-9b:H1': 1.0, 'qwen3.5-9b:H2': 1.0}; adjusted {'qwen3-8b:H1': 1.0, 'qwen3-8b:H2': 1.0, 'qwen3-32b:H1': 1.0, 'qwen3-32b:H2': 1.0, 'qwen3.5-9b:H1': 1.0, 'qwen3.5-9b:H2': 1.0}.

**Cross-family laundering loop (pre-registered rule): FAIL** (models evaluated: qwen3-8b, qwen3-32b, qwen3.5-9b).

### Format proposition, CPU (1,598 real Gemma slip payloads with known intent; Wilson 95%)

| variant | parser path | n | loud | exact | silent local residue | silent absorbed | silent other | delivered invalid | laundered (of silent) | judge-flagged (of silent) |
|---|---|---|---|---|---|---|---|---|---|---|
| G | vLLM 0.19.1 gemma4.nonstream | 1598 | 0 | 0 | 0 | 100.0% | 0 | 0 | 88.5% | 100.0% |
| J_real | vLLM 0.19.1 hermes.nonstream | 1462 | 99.9% | 0.1% | 0 | 0 | 0 | 0 | 0 | 0 |
| J_real | vLLM 0.19.1 hermes.stream | 1462 | 0 | 0.1% | 0 | 0 | 0 | 99.9% | 0 | 0 |
| J_real | vLLM 0.19.1 strict_hermes | 1462 | 99.9% | 0.1% | 0 | 0 | 0 | 0 | 0 | 0 |
| J_bt | vLLM 0.19.1 hermes.nonstream | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| J_bt | vLLM 0.19.1 hermes.stream | 1598 | 0 | 0 | 0 | 0 | 0 | 100.0% | 0 | 0 |
| J_bt | vLLM 0.19.1 strict_hermes | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| J_omit | vLLM 0.19.1 hermes.nonstream | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| J_omit | vLLM 0.19.1 hermes.stream | 1598 | 0 | 0 | 0 | 0 | 0 | 100.0% | 0 | 0 |
| J_omit | vLLM 0.19.1 strict_hermes | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| J_unesc | vLLM 0.19.1 hermes.nonstream | 685 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| J_unesc | vLLM 0.19.1 hermes.stream | 685 | 0 | 0 | 0 | 0 | 0 | 100.0% | 0 | 0 |
| J_unesc | vLLM 0.19.1 strict_hermes | 685 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| X_real | vLLM 0.19.1 qwen3_coder.nonstream | 1598 | 0 | 0.6% | 99.4% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_real | vLLM 0.19.1 qwen3_coder.stream | 1598 | 0 | 0.6% | 99.4% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_real | vLLM 0.19.1 qwen3_xml.nonstream | 1598 | 0 | 0.6% | 99.4% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_real | vLLM 0.19.1 strict_xml | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| X_bt | vLLM 0.19.1 qwen3_coder.nonstream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_bt | vLLM 0.19.1 qwen3_coder.stream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_bt | vLLM 0.19.1 qwen3_xml.nonstream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_bt | vLLM 0.19.1 strict_xml | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| X_omit | vLLM 0.19.1 qwen3_coder.nonstream | 1598 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 |
| X_omit | vLLM 0.19.1 qwen3_coder.stream | 1598 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 |
| X_omit | vLLM 0.19.1 qwen3_xml.nonstream | 1598 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 |
| X_omit | vLLM 0.19.1 strict_xml | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| X_tag | vLLM 0.19.1 qwen3_coder.nonstream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_tag | vLLM 0.19.1 qwen3_coder.stream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_tag | vLLM 0.19.1 qwen3_xml.nonstream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 100.0% | 0.0% |
| X_tag | vLLM 0.19.1 strict_xml | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| X_open | vLLM 0.19.1 qwen3_coder.nonstream | 1598 | 0 | 0 | 0 | 100.0% | 0 | 0 | 100.0% | 100.0% |
| X_open | vLLM 0.19.1 qwen3_coder.stream | 1598 | 0 | 0 | 0 | 100.0% | 0 | 0 | 100.0% | 100.0% |
| X_open | vLLM 0.19.1 qwen3_xml.nonstream | 1598 | 0 | 0 | 0 | 100.0% | 0 | 0 | 100.0% | 100.0% |
| X_open | vLLM 0.19.1 strict_xml | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| J_bt | vLLM 0.31.0 hermes.nonstream | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| J_bt | vLLM 0.31.0 hermes.stream | 1598 | 0 | 0 | 0 | 0 | 0 | 100.0% | 0 | 0 |
| J_real | vLLM 0.31.0 hermes.nonstream | 1462 | 99.9% | 0.1% | 0 | 0 | 0 | 0 | 0 | 0 |
| J_real | vLLM 0.31.0 hermes.stream | 1462 | 0 | 0.1% | 0 | 0 | 0 | 99.9% | 0 | 0 |
| J_omit | vLLM 0.31.0 hermes.nonstream | 1598 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| J_omit | vLLM 0.31.0 hermes.stream | 1598 | 0 | 0 | 0 | 0 | 0 | 100.0% | 0 | 0 |
| X_bt | vLLM 0.31.0 qwen3_coder.nonstream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| X_bt | vLLM 0.31.0 qwen3_engine.server | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| X_bt | vLLM 0.31.0 qwen3_engine.stream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| X_real | vLLM 0.31.0 qwen3_coder.nonstream | 1598 | 0 | 0.6% | 99.4% | 0 | 0 | 0 | 0 | 0 |
| X_real | vLLM 0.31.0 qwen3_engine.server | 1598 | 0 | 0.6% | 99.4% | 0 | 0 | 0 | 0 | 0 |
| X_real | vLLM 0.31.0 qwen3_engine.stream | 1598 | 0 | 0.6% | 99.4% | 0 | 0 | 0 | 0 | 0 |
| X_omit | vLLM 0.31.0 qwen3_coder.nonstream | 1598 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 |
| X_omit | vLLM 0.31.0 qwen3_engine.server | 1598 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 |
| X_omit | vLLM 0.31.0 qwen3_engine.stream | 1598 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 |
| X_tag | vLLM 0.31.0 qwen3_coder.nonstream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| X_tag | vLLM 0.31.0 qwen3_engine.server | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| X_tag | vLLM 0.31.0 qwen3_engine.stream | 1598 | 0 | 0 | 100.0% | 0 | 0 | 0 | 0 | 0 |
| X_open | vLLM 0.31.0 qwen3_coder.nonstream | 1598 | 0 | 0 | 0 | 100.0% | 0 | 0 | 0 | 0 |
| X_open | vLLM 0.31.0 qwen3_engine.server | 1598 | 0 | 0 | 0 | 100.0% | 0 | 0 | 0 | 0 |
| X_open | vLLM 0.31.0 qwen3_engine.stream | 1598 | 0 | 0 | 0 | 0 | 100.0% | 0 | 0 | 0 |

Pre-registered format predictions: FP1_J_bt_hermes_nonstream_loud: 1.0 (pass=True); FP1_J_real_hermes_nonstream_loud: 0.9993 (pass=True); FP2_X_bt_qwen3coder_resync_or_loud: 1.0 (pass=True); FP2_X_real_qwen3coder_resync_or_loud: 1.0 (pass=True); FP3_gemma_silent: 1.0 (pass=None)

Teacher Qwen3.8-flash-next (qwen3_coder XML, same harness, descriptive only): 19/4133 edit calls malformed (schema-level: wrong/missing keys 12 extra-key, 15 missing); loud unparsed responses 0/35502; XML residue at a value end 0.
<!-- RESULTS:END -->

## 3. Caveats (read before citing)
1. **Off-policy histories.** Every history is a real Gemma-4-31B trajectory: its thoughts, its argument order (mostly
   new-first) and its content. This is the same design as A's 12B/E4B replications. It tests the history pathway, not
   on-policy Qwen dynamics.
2. **P1L carries Gemma-spelled corruption.** The value ends in `` `,old_string: ``, rendered inside JSON or XML. That is
   by design: it is "the same swallowed-argument dict". A natively laundered exemplar in each format is P1N.
3. **The P1N hermes nudge also hides earlier thoughts.** The nudge is a new user message, so the Qwen3 template drops
   every earlier thought. This is the same confound as A's P3. P1N is the production pathway, not a clean single-factor
   contrast.
4. **XML residues are invisible to any syntax judge.** A copied trailing backtick is not "malformed". The copy check
   measures re-emission of the injected value directly.
5. **Thinking budget applied post hoc.** It is applied after generation, and generation runs over raw completions
   rather than through ADK/LiteLLM.
6. **The streaming hermes path delivers invalid JSON.** vLLM 0.19.1's streaming hermes path delivers a tool call whose
   argument text is not JSON. JSON is "loud" only on the non-streaming path, which is the one the swegemma harness
   uses.

## 4. Files
| path | content |
|---|---|
| `prereg.md`, `PREREG_DEVIATIONS.md`, `data/prereg_hashes.md5` | pre-registration, deviations, code and prompt hashes |
| `scripts/qwenproto.py` | renderer (vLLM chat path), serializers, native-slip builders, vLLM parsers (non-streaming and streaming), strict references, judge |
| `scripts/arms.py` (+ `scripts/frozen/`) | arm constructions (A's P1/P5/P6/P8a, E's quarantine, X's P1N) |
| `scripts/prep_prompts.py` → `data/prompts_<model>[_heldout].jsonl` | pre-rendered prompts (+ manifests, census id lists) |
| `scripts/run_qwen.py`, `scripts/run_chain.sh` | generation runner → `out/gen_<model>[_heldout].jsonl` |
| `scripts/analyze.py` → `out/ana_<model>[_heldout].json` | per-arm rates, paired contrasts, removal, copy check, census |
| `scripts/combine.py` → `out/results_x.json` (= `results.json`) | Holm F2, success rule, format predictions |
| `scripts/format_cpu.py` / `scripts/format_v31.py` → `format/` | CPU format analysis (vLLM 0.19.1 / 0.31.0) |
| `scripts/teacher_xml_slips.py` → `out/teacher/` | natural production slips of the Qwen teacher runs (descriptive) |
| `scripts/smoke.py` → `out/smoke_cpu_300.json` | CPU smoke test (render, serializer identity, judge false positives) |
| `scripts/report.py` | regenerates the results block of this README |

**Reproduce.** All commands run through `tools/limited.sh`.
```bash
X=experiments/crossfamily
L=tools/limited.sh
PY=/opt/envs/env_gemma/bin/python
cd $X

# prompts and CPU checks
NAME=xprep $L scripts/prep_all.sh
NAME=xprepho $L scripts/prep_heldout.sh
NAME=xsmoke $L $PY scripts/smoke.py 300 out/smoke_cpu_300.json
NAME=xfmt $L $PY scripts/format_cpu.py format 8
NAME=xv31 $L /opt/envs/env_vllm31/bin/python scripts/format_v31.py format

# generation (servers started by the PI)
NAME=xr32 $L scripts/run_chain.sh qwen3-32b http://127.0.0.1:<port>/v1 <served> 24 4

# analysis
for m in qwen3-8b qwen3-32b qwen3.5-9b; do
  $PY scripts/analyze.py --mk $m --gen out/gen_$m.jsonl --out out/ana_$m.json
  $PY scripts/analyze.py --mk $m --gen out/gen_${m}_heldout.jsonl --out out/ana_${m}_heldout.json
done
$PY scripts/combine.py out/results_x.json && cp out/results_x.json results.json && $PY scripts/report.py
```

## 5. Status of later phases
- **PREREG_v2 confirmatory rerun:** done (section above).
- **Benchmark extension, `prereg_ext.md`** (frozen 2026-11-04T18:51Z): gpt-oss-20b (harmony), Qwen3-Coder-30B-A3B (XML),
  Devstral-Small-2-24B (Mistral v13) and Qwen3.8-27B (XML, thinking), all on the same public A1 states.
  - Prompts are pre-rendered in `out/ext/`. The run and post-run scripts are `scripts/run_ext_chain.sh` and
    `scripts/post_ext.sh`.
  - Demoted: it runs as idle fill on GPU0.
  - gpt-oss-20b is done (coverage table). It has a production-parser caveat: 125 of 2,100 first calls go to an
    unknown tool. Of these, 56 are harmony header slips that vLLM 0.19.1 delivers as names like
    `edit_file<|channel|>commentary`; the rest are invented tools such as `search`. The frozen judge does not count
    these as edits.
  - All four models are done: gpt-oss-20b, Qwen3-Coder-30B, Devstral-24B and Qwen3.8-27B. None meets the S1–S3 copy rule.
  - Devstral needs two serving notes:
    - It is served text-only (`--limit-mm-per-prompt '{"image": 0}'`), recorded in PREREG_DEVIATIONS.
    - 18 of the 298 P5 continuations are empty, so those turns have no call. This is the expected effect of the
      registered `continue_final_message` adaptation, used when a P5 history ends in an assistant text turn.
  - The CPU format column is in `format/format_ext_summary.json`.
