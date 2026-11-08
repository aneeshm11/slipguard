# Workstream X pre-registration: cross-family and cross-format replication of the laundering loop

**Registered: 2026-11-04T12:15Z (UTC).** Written before any GPU job of this workstream. No Qwen server exists yet
and no Qwen generation has been made. The CPU format analysis (§8) has been run only as a 3-case code-sanity check;
its outcomes have not been inspected.
Spec: `ideation/neurips_review/UPGRADE_PLAN.md` §P0-X, §4 and §6.
Code and prompt hashes: `data/prereg_hashes.md5` (md5, 12:14Z). Frozen copies of A's history constructions and E's
shipped quarantine: `scripts/frozen/` (`SOURCES.md5`).
Any change after this point goes into `PREREG_DEVIATIONS.md` (this directory) with a UTC time and a reason.

## 1. Question
The question is whether the Gemma-4 laundering loop is general. In Gemma, a lenient parser plus template re-rendering
turns one delimiter slip into a well-formed corrupted exemplar, which the model then copies or imitates. Gemma-4-31B
next-edit malformed rises from 5.7% to 46.2% after one corrupted re-render.

We test it in two other families and formats:
- **Qwen3-8B** and **Qwen3-32B-FP8**: hermes JSON with escaped strings.
- **Qwen3.5-9B**: qwen3_coder XML, escape-free, with named asymmetric `<parameter=…>` tags.

## 2. Design (fixed)
**Contexts**
- **Battery (primary).** A's 300 gate contexts (`contagion/data/ids_gate300.txt`, A's random order; 256 attempts).
  Each is a real base-31B pre-edit state whose most recent prior `edit_file` was valid and succeeded.
- **Census.** Workstream B's Gemma-only first-edit contexts (`intent_decoding/data/replay_gemma_first_edit.jsonl`,
  md5 f2e4fcc4…, in file order), restricted to ids in A's context index. We use the first 600 for Qwen3-8B and
  Qwen3.5-9B, and the first 300 for Qwen3-32B. The lists are in `data/ids_census_<model>.txt`.
- **Held-out (secondary tier).** Contexts 300–599 of A's random phase-1 order. This tier runs only after the primary
  tier has completed in that model's GPU window.
- **Exclusions.** Teacher runs (t1_qwen, t2_qwen_rebench, t3_qwen_rebench, dsprobe) are excluded by construction.
  Every context comes from the plain base-31B index.

**Rendering**
- The logged OpenAI messages plus the carried-forward tool declarations are rendered through vLLM 0.19.1's chat path:
  ChatCompletionRequest → content-format resolution → `parse_chat_messages` (arguments JSON → dict, text parts joined)
  → the model's own HF chat template, with `enable_thinking=True`.
- Histories are off-policy: they were written by Gemma-31B, including its thoughts in `reasoning_content`.

**Arms (k = 1; the most recent prior edit is replaced)**

| arm | construction |
|---|---|
| P0 | original history |
| P1L (laundered exemplar) | A's P1 swallowed-argument dict (vLLM gemma4 parse of a backtick-closer slip: `new_string` ending in `` `,old_string: `` plus junk keys, `old_string` missing) + the exact ADK missing-parameter error, rendered by the Qwen template |
| P1N (format-native slip) | the call in the model's own format, with the slipped string argument's closing delimiter replaced by a backtick (hermes: the closing `"`; XML: the closing `\n</parameter>`), passed through the format's production vLLM 0.19.1 parser (hermes / qwen3_coder). See the outcomes below. |
| P5 | call and response removed; A's one-line note |
| P6 | P1L exemplar + the original success response |
| P8a | E's frozen `quarantine_messages` applied to the P1L history with the slip's raw text (A's P8a): recovered call + MalformedToolCall error |
| C0 | census arm: original history on first-edit contexts |

P1N outcomes:
- **No call returned (loud).** The raw text stays in the assistant content, with no tool response, followed by the
  harness's generic continuation nudge (swegemma `agent_runner`).
- **Call returned.** It is executed as ADK would execute it:
  - a missing required key gives the ADK error;
  - an intact `old_string` gives success, with the logged diff patched to show the residue (falling back to the
    logged diff when the patch is not possible);
  - otherwise the result is old_string-not-found.

CPU pre-render result: hermes P1N is loud in 300/300 contexts. XML P1N is silent in 300/300: 297 applied with a
trailing-backtick residue, 3 old_string-not-found.

**Generation** (`scripts/run_qwen.py`)
- `/v1/completions` on the raw prompt, streamed, with special tokens kept. Sampling uses the context's logged
  temperature and top_p (0.2 or 0.7, and 0.95), with top_k = 20 (Qwen model cards). Each context has one seed, shared
  by all its arms (A's seed function), giving common random numbers.
- Generation stops at EOS only (`<|im_end|>`, `<|endoftext|>`), with at most 7,168 new tokens.
- The thinking budget is 4,096 tokens, applied post hoc: the thought is cut at 4,096 tokens, `</think>` is forced, and
  the continuation (≤ 5,120 tokens, seed + 1) is generated. This is what vLLM's ThinkingTokenBudgetLogitsProcessor
  does.
- Leader-first prefix-cache scheduling, as in A. Servers are vLLM 0.19.1, started by the PI. No server-side
  tool-call or reasoning parser is involved.

**Judge** (`qwenproto.judge`; one definition)
- The Qwen3 reasoning split (vLLM `Qwen3ReasoningParser`) runs first. The format's production parser then runs on the
  content, and the **first** call is judged.
- A call is malformed if:
  - a call was opened but the parser returns no call (loud / unparsed);
  - a required key is missing;
  - an unknown key appears (`edit_file`);
  - a string value contains A's look-alike closer + `,<declared key>:` leak, or its JSON spelling (closer +
    `"<edit key>":`);
  - a string value contains an XML tag fragment (`</parameter>`, `<parameter=`, `</function>`, `<function=`);
  - a special token appears inside a value;
  - the arguments are not an object;
  - an `edit_file` string argument is not a string.
- A's subset (`gemma_flags`) and the strict reference parsers' verdicts are reported as a cross-tab.
- The judge flags 0/51 historical calls of 6 contexts re-rendered in either format (CPU smoke test,
  `out/smoke_cpu_6.json`). The false-positive scan is repeated on all P0 histories in the final report.

## 3. Endpoints
- **Primary** (UPGRADE_PLAN §2): unconditional, per context, P(the next call is a malformed `edit_file`)
  (intention-to-treat).
- **Secondary:** P(malformed | the next call is edit_file); P(edit); P(malformed | any call); A's-definition subset;
  strict-reject rate; and the copy-check classes for P1L/P6/P8a/P1N edits:
  - verbatim copy of the injected corrupted value (for loud hermes P1N: the raw slip junction);
  - clean retry;
  - same-content variant;
  - new content.
- **Census:** natural onset P(malformed edit) and P(malformed any call), each slip classified loud (unparsed) or
  silent (parsed + flagged), plus the production-ok-but-strict-reject rate.

## 4. Sample size and power
300 paired contexts per model (256 attempt clusters). With P0 ≈ 2%, an RD of +10 pp gives ≥ 36 expected discordant
pairs against ≈ 6, so power is above 99% at α = 0.05/6. Power for RD = +6 pp is about 85%. The census has
600 / 600 / 300 contexts: the Wilson half-width at 2% is ≤ 1.2 pp (600) and ≤ 1.7 pp (300).

## 5. Statistics
- **Pairing and resampling.** All contrasts are paired by context. CIs come from an attempt-cluster bootstrap
  (B = 10,000, percentile; seed 20261104).
- **p-values.** One-sided bootstrap p-values are (1 + #{RD* ≤ 0}) / (B + 1). The exact one-sided McNemar test on
  discordant pairs is reported as a sensitivity check.
- **Ratios.** Ratios use bootstrap order-statistic CIs, and may be infinite. No headline ratio is reported with an
  infinite CI; risk differences come first.
- **Removal fraction** = (P1L − Q) / (P1L − P0), unconditional, on contexts that have all three arms. It is reported
  with a bootstrap CI and the one-sided p of RD(P1L − Q) > 0.
- **Holm (family F2, UPGRADE_PLAN §6).** For each of the 3 models: H1 = RD(P1L − P0) > 0, and H2 = RD(P1L − P5) > 0.
  That is 6 tests, Holm-adjusted together (`scripts/combine.py`).

## 6. Pre-registered success rule (UPGRADE_PLAN §P0-X, operationalised)
For each model, three conditions:
- **S1.** RD_uncond(P1L − P0) ≥ +10 pp, and Holm-adjusted p(H1) < 0.05.
- **S2.** If P0 has ≥ 5 malformed events: P1L / P0 ≥ 3 with bootstrap CI_lo > 1. If P0 has < 5 events (the ratio is
  ill-defined): Haldane ratio ≥ 3, and exact one-sided McNemar p < 0.05.
- **S3.** P5 removes ≥ 50% of the P1L excess (unconditional point estimate), and Holm-adjusted p(H2) < 0.05.

**"The laundering loop is cross-family"** iff S1 ∧ S2 ∧ S3 hold in at least one Qwen model. If it fails in all three
models, the outcome is UPGRADE_PLAN §4 variant B: model-specific loop, general stack/format result. The conditional
metric is reported beside every rule, and any disagreement with the unconditional metric is stated.

**Secondary rules** (not in F2)
- **Shipped quarantine works in model m** iff P8a removes ≥ 70% of the excess, with CI_lo ≥ 50% (A's rule).
- **Induction without a retry motive in m** iff RD(P6 − P0) ≥ +5 pp with CI_lo > 0. "Confirmed" additionally requires
  the same on the held-out tier, if it was run.
- **Held-out replication of P1L** iff RD(P1L − P0) has CI_lo > 0 on contexts 300–599.
- **Copy-on-retry share:** the fraction of malformed P1L edits that are verbatim copies, with a Wilson CI.

## 7. Format proposition: predictions (from UPGRADE_PLAN §P0-X / P0-D(c), verbatim intent)
- **FP1.** JSON (hermes) native single-closer slips are loud: vLLM 0.19.1 hermes non-streaming returns no call for
  ≥ 95% of them, so nothing is laundered. Tested on the backtick variant and on the real-closer variant (a `"` closer
  is no slip in JSON and is counted separately).
- **FP2.** XML (qwen3_coder) native slips mostly re-synchronise at the next `<parameter=`: exact, local residue or loud
  in ≥ 50%, with the next argument preserved. The absorbed share is reported.
- **FP3.** Gemma's symmetric delimiter launders the same slips about 100% (silent).
- **FP4.** Model-side copying and induction are family-general: P1L > P0 and P6 > P0 in the Qwen models.
- **Exploratory, no directional prediction:**
  - P1N − P0 per model. For hermes it is the loud-failure pathway (raw text + nudge; the nudge also hides earlier
    thoughts in the Qwen3 template, the same confound as A's P3). For XML it is the silent local-residue pathway.
  - The streaming paths (hermes streaming may deliver invalid argument JSON to the client).

## 8. CPU format analysis (`scripts/format_cpu.py`)
**Inputs and variants**
- Inputs: the 1,610 real Gemma-4 slip payloads with known intent (C's `fuzz/cases.jsonl`, `slip_reassembled_*`).
- Variants per payload: G (the real Gemma text); hermes J_real / J_bt / J_omit / J_unesc; XML X_real / X_bt / X_omit /
  X_tag / X_open (defined in the script docstring).

**Parser paths**
- vLLM 0.19.1 hermes, non-streaming and streaming;
- qwen3_coder, non-streaming and streaming;
- qwen3_xml, non-streaming;
- gemma4, non-streaming;
- the strict references.

**Outcomes:** loud / exact / silent_local / silent_absorbed / silent_other / delivered_invalid / error. Each silent
outcome also records laundered (template-render fixed point) and flagged-by-judge.

**Validity controls:** the intended calls serialised canonically, and C's 1,500 real clean calls.

## 9. Execution, stopping and exclusions
**Schedule.** The PI starts the servers. The planned schedule:
- Qwen3-32B-FP8 on GPU0, Nov 5 02:30–10:00;
- Qwen3-8B and Qwen3.5-9B on GPU1, Nov 5 06:00–13:00.

Each model runs its primary prompt file first (battery and census interleaved by context index) and then the held-out
tier.

**Stopping.** If a window closes early, the analysis uses the contexts completed so far. The context order is random,
and only contexts with every arm present enter paired contrasts. The achieved n is reported.

**Exclusions.**
- `context_too_long`: none expected; the maximum prompt is 16,061 tokens.
- Render errors: 0 at registration.
- Generation errors after 6 retries are re-queued. Records that still fail are reported and excluded.
- Budget-forced jobs are included.

**Interim looks.** Allowed only for operational QA (throughput, errors, budget rate, parse sanity). No design change
may be based on outcome data.

**Optional extension.** Qwen3.8-27B-FP8 (P1-9, XML) needs a template-specific serializer (its template renders
non-string arguments with `tojson`). It is not part of this registration and would be registered separately.
