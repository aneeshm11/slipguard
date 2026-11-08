# PREREG_v2.3 (addendum): onset transplant. Does tool-result serialization induce first-edit slips? (workstream D)

* **Written:** 2026-11-05, starting 07:07 UTC. **Frozen** when its sha256 is written to
  `PROGRESS.md`. Deviations go to `PREREG_DEVIATIONS.md` (this folder).
* **Blindness.** At writing time no transplant output existed (checked 07:06 UTC). D has seen A's
  `natural_descriptives_v2.json` headline numbers only as relayed by the PI. D has not read `<host-path>/work` or
  `/harness` (audit until 13:00 UTC).
* **Relation to earlier registrations.** This is an addendum to PREREG_v2 (sha256 5da75e61…); conventions follow its §3.
  Earlier files are unchanged. PREREG_v2's natural-descriptive verdicts stand as recorded by A: D1 = 1.0% [0.4, 1.6] is
  **LOWER** than the 80% PI [5, 25], and K = 1 contagion of 7.5% is far below D3's [30, 80]. D's transport assumed the
  main-track onset level carried over; it did not.

## 1. Question and what is already ruled out
* Natural first-edit onset is about 1% on P's public corpus vs about 17% in the main-track logs.
* Ruled out as the main cause:
  * the template (B's arm 12: the July template on discovery contexts did not lower onset);
  * temperature (onset rises with T, and P runs at T = 1.0).
* Remaining candidates:
  * (a) tool-result serialization. ADK + LiteLLM send tool results as JSON strings, so code reaches the model with `\"`
    escapes 46.6% of the time vs 1.3% natively (C);
  * (b) the system prompt and tool descriptions;
  * (c) the task and repo mix.
* This addendum tests (a) causally, and (b) partly.

## 2. Design (history interventions; A builds and runs it)
**States.** P's S1_B1 first-edit states, the first 600 in PREREG_v2 rank order (A's pools). This is the state immediately
before the first edit call of an episode, with a protocol-clean history.

**Model and sampling.**
* 31B QAT-ct, thinking ON, P's sampling (T = 1.0, top-p 0.95, top-k 64).
* One seed per state, shared by all its arms (common random numbers).
* Generation is free: the next turn is not forced to be an edit.

**Arms.**

| arm | construction | status |
|---|---|---|
| **O0** | the state as is (P's native tool-result rendering) | primary |
| **O1** | every tool result in the history re-serialized exactly as ADK + LiteLLM do: the json-encoded result string with `\"` and `\n` escapes, reusing C's library-faithful code in `experiments/conformance/history/`; nothing else changes | primary |
| **O2** | O0 with P's system prompt replaced by the main-track system prompt text, taken from the discovery contexts in `data/protocol/contexts.jsonl` (inside agent_paper, not the audited directories). Tool declarations are unchanged, so S1's key names stay consistent with the history | secondary, optional |
| **O1r** | **reverse transplant** on discovery states: B's Gemma-only first-edit contexts (the first 300 in B's file order), with every JSON-string tool result *de-serialized* to native text. Everything else is unchanged, including the June template and logged sampling. Compared with the same contexts as logged (O0r) | secondary, optional |

I replaced the suggested neutral-rewording O2 with the system-prompt transplant. A neutral rewording of P's own
declarations does not test what differs from the main track. Transplanting declarations would also change key names
(`filepath` vs `file_path`) and break consistency with the history.

**Outcomes** (A's vLLM-parse judge with S1 keys; for O1r, discovery keys):
* **Primary:** unconditional closer-slip rate of the first edit, per state: P(the next turn contains an edit call whose
  string value is closed by a look-alike closer).
* **Secondary:**
  * census-malformed rate (any failure class, any tool; unconditional);
  * escaped-closer share: among closer slips, the share whose closer run contains `\"` or `"` (vs backtick);
  * string-mode drift share: edit values containing literal `\n` or `\"` escape sequences where the file has none;
  * P(next turn is an edit).

## 3. Predictions (D's 80% prediction intervals)

| quantity | prediction |
|---|---|
| O0 closer-slip rate | **1.2% [0.3, 3.0]** (should reproduce P's natural D1) |
| O1 closer-slip rate | **3.5% [1.0, 10.0]**; RD(O1 − O0) **+2.3 pp [0, +8]** |
| O1 census-malformed rate | 5% [2, 13] |
| escaped-closer share among slips | O0 ≤ 0.20; O1 0.40 [0.15, 0.75] |
| string-mode drift share among edits | O0 ≤ 1%; O1 5% [1, 15] |
| O2 closer-slip rate | 1.5% [0.3, 5]; RD(O2 − O0) +0.3 pp [−1, +3] |
| O1r: RD(O1r − O0r), discovery states | −4 pp [−12, 0], i.e. de-serializing lowers onset from about 17% |

D's probability that serialization explains **most** of the onset gap (G ≥ 0.5 below) is 0.20. My reasons:
* The dominant main-track closer is a backtick (84%), not an escaped quote, so escapes alone are not the obvious inducer.
* String-mode drift and escaped closers should rise under O1, but they were a minority class in discovery.
* I expect the gap to be shared with (b) and (c).

## 4. Decision rules
Primary contrast: RD = closer-slip(O1) − closer-slip(O0). It is paired by state, with an episode-cluster bootstrap
(B ≥ 2,000, percentile 95% CI) and the exact one-sided McNemar test as a sensitivity check. The **gap fraction** is
G = (O1 − O0)/(0.174 − O0), where 0.174 is the main-track first-edit onset.

| verdict | rule |
|---|---|
| **SERIALIZATION INDUCES ONSET, EXPLAINS MOST OF THE GAP** | CI_lo(RD) > 0 and G ≥ 0.50 |
| **SERIALIZATION INDUCES ONSET, PARTIAL** | CI_lo(RD) > 0 and G < 0.50 |
| **NO MATERIAL EFFECT** | CI_hi(RD) < +2.0 pp (rules out an effect of 2 pp or more; about 12% of the gap) |
| **INCONCLUSIVE** | otherwise |

Power: with an O0 rate of about 1% and n = 600 paired states, an RD of +3 pp gives about 20 expected discordant pairs
against about 3, so it is detectable. The NO-EFFECT verdict needs the upper bound below +2 pp, which this n can deliver if
the true RD ≈ 0.

* **Mechanism corroboration** (reported, not a verdict): if the verdict is "induces onset", the paper may say "via escape
  or string-mode drift" only if the escaped-closer share **or** the string-mode drift share under O1 exceeds O0's with
  CI_lo > 0.
* **O2** (system prompt) uses the same rules with O2 in place of O1. **O1r** (reverse): "de-serializing reduces onset" iff
  CI_hi(RD(O1r − O0r)) < 0. Both are secondary and outside any Holm family.
* **Holm:** the primary family is {RD(O1 − O0) > 0} alone, so α = 0.05. Secondary contrasts are reported with unadjusted
  CIs and labelled secondary.
* **Paper statements:**
  * "the public-setup / main-track onset gap is (partly) caused by tool-result serialization" requires one of the two
    INDUCES verdicts on O1, and is strengthened by O1r;
  * otherwise the paper reports that serialization was tested and not supported, and that the gap is attributed to
    unmeasured differences (prompt, tasks, harness behaviour), without a causal claim.

## 5. Notes
* The injection arms (PREREG_v2 C1–C11) do not depend on natural onset. Their verdicts are unaffected by this addendum.
* PREREG_v2's descriptive misses (D1, D3, D4) are reported as **LOWER than predicted**, as registered. The transport
  error is itself a finding: natural onset is setup-dependent by an order of magnitude, while the injected-exemplar
  effect is what the confirmatory arms test.
