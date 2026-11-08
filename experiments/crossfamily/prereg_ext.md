# Workstream X pre-registration addendum: benchmark extension to new model families and tool-call formats

**Registered: 2026-11-04T18:51Z (UTC).**
- **Status at registration:**
  - no GPU job of this extension has run;
  - no server for these models exists;
  - none of workstream P's corpus data exist yet: the pools land about Nov 5 09:00, and no P outcome has been seen by X.
- **Code:** `scripts/ext_frozen/` (sha256 in `scripts/ext_frozen/SHA256SUMS`, computed 18:50:23Z).
- **Governing rules:** the same rules as X's discovery prereg (`prereg.md` §3–§6). PREREG_v2-style labels are reported
  as secondary, for comparability with X's Qwen rows on the same states.
- **Deviations:** go into `PREREG_DEVIATIONS.md`, tagged `[ext]`.

## 1. Purpose
The paper is reframed as a causal benchmark of history-borne tool-call failure. This addendum extends X's cross-family
battery from 3 Qwen models to more families and tool-call protocols. Every row sits on the same public, releasable
states: workstream P's SWE-bench-Verified corpus, pool A1.

## 2. Models, formats and serving (vLLM 0.19.1; one model at a time on GPU3; launch lines in progress.md)

| key | model | format (production parser) | thinking | prompt form |
|---|---|---|---|---|
| gpt-oss-20b | openai/gpt-oss-20b (MXFP4) | harmony: `…commentary to=functions.NAME <\|constrain\|>json<\|message\|>{JSON}<\|call\|>` (vLLM `openai`; non-JSON arguments are still delivered) | yes, analysis channel (reasoning effort: harmony default, medium) | token ids (vLLM harmony render; conversation start date pinned to 2026-11-04) |
| qwen3-coder-30b | Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 | qwen3_coder XML (re-syncs at `<parameter=`) | no | text (HF template through vLLM's chat path) |
| devstral-24b | mistralai/Devstral-Small-2-24B-Instruct-2512 (FP8) | Mistral v13 `[TOOL_CALLS]NAME[ARGS]{JSON}` (vLLM `mistral` with the MistralTokenizer; v11+ arguments are not validated, so non-JSON arguments are delivered) | no | token ids (vLLM Mistral path); output detokenised with skip_special_tokens=True, as the server does |
| qwen3.8-27b | Qwen/Qwen3.8-27B-FP8 | qwen3_coder XML (its template serialises non-string arguments with `tojson`) | yes; template default reasoning effort xhigh | text |

Not included: **Llama-3.1-8B-Instruct.** It is blocked: the HF token has no gated access (403).

**Documented format adaptations.** These are required to serve the models at all. They apply to all arms of the
model.
- **Devstral, thoughts.** Assistant `reasoning_content` is stripped before rendering. The v13 tokenizer has no think
  tokens, and mistral_common otherwise rejects every request ("think tokens are not available"; HTTP 400).
- **Devstral, P5 with a final assistant turn.** When the removed call was the last turn, the history ends with the
  assistant note. It is rendered with `continue_final_message=True`, because mistral_common rejects
  add_generation_prompt after an assistant message.
- **Devstral, non-JSON arguments in history.** mistral_common re-serialises them as a JSON *string*
  (double-encoded). This is production behaviour and is kept.

## 3. Contexts (public)
- **Battery.** Workstream P's corpus, pool **A1**, the first **300** states in rank order (`S1_A1.jsonl`, PREREG_v2 §2,
  built by workstream A). Halves are H1 = ranks 1–150 and H2 = ranks 151–300. These are the same states as A's
  confirmatory arms and X's Qwen PREREG_v2 arms, so the comparison is paired across models.
- **Census (secondary tier, run after the battery).** Pool **B1**, the first **300** states.
- X does not sample. `ext_prepare.py` asserts rank order and reads P's manifest and contexts; P's `outcomes.jsonl` is
  never opened.
- Histories are off-policy: they were written by Gemma-4-31B, and its thoughts are rendered where the template supports
  them.

## 4. Arms (k = 1, the most recent prior edit call; `arms_v2.py`)
- **Shared arms.** P0, P1L (laundered exemplar + P's missing-parameter error), P5 (removed + note), P6 (P1L + the
  original success response) and P8a (E's frozen shipped quarantine, recovered) are built at the message level exactly
  as for the Qwen models, using P's harness texts from the manifest.
- **P1N, the native single-closer slip in the model's own syntax.** A backtick replaces the closing delimiter of the
  slipped string. The result is passed through the model's production parser, and the arm follows the outcome:
  - XML formats: a silent local residue. The call executes and the success diff is patched.
  - harmony and mistral: the call is **delivered with non-JSON arguments**. The modelled harness keeps it as delivered,
    unable to read any argument, and answers with P's missing-parameter error for every required key. The
    construction is stated in advance as a modelling choice: ADK's own LiteLLM path would raise on `json.loads`.

## 5. Generation, judge, endpoints and statistics
**Generation** (`run_ext.py`)
- Sampling uses the context's temperature and top_p from P's manifest, plus **top_k 20 for every model**. That is the
  same protocol as X's Qwen rows.
- Each context gets one seed, shared by all arms.
- Thinking models (Qwen3.8 `</think>`; gpt-oss analysis channel, closed with `<|end|><|start|>assistant`) get a
  post-hoc thinking budget of 4,096 tokens. Non-thinking models get none.
- Generation is capped at 7,168 new tokens.
- Stop tokens:
  - Qwen: `<|im_end|>` / `<|endoftext|>`;
  - harmony: `<|return|>` / `<|call|>` / `<|endoftext|>`;
  - mistral: `</s>`.

**Judge.** The format's production parser judges the **first** call, with the registered malformed flags and key names
derived from P's declared tools.
- A delivered call with non-JSON arguments is malformed (`args_not_object`) and is also counted as
  `delivered_invalid`.
- The strict references are reported as a cross-tab.

**Endpoints (as `prereg.md` §3)**
- **Primary:** unconditional P(the next call is a malformed edit) per context.
- **Secondary:**
  - P(malformed | edit);
  - P(edit);
  - the copy-check classes;
  - the exploratory "any protocol failure" metric.

**Statistics (as `prereg.md` §5)**
- Comparisons are paired by context.
- CIs come from an episode-cluster bootstrap: B = 10,000, cluster = P's `attempt_id`.
- One-sided p-values come from the bootstrap. The exact McNemar test is a sensitivity check.

**Holm family F-ext.** For each extension model: H1, RD(P1L − P0) > 0; and H2, RD(P1L − P5) > 0. That is 8 tests
across 4 models, Holm-adjusted together (`combine_ext.py`).

## 6. Decision rules (same as `prereg.md` §6, per extension model)
- **S1:** RD_uncond(P1L − P0) ≥ +10 pp, and Holm-adjusted p(H1) < 0.05.
- **S2:** P1L / P0 ≥ 3 with bootstrap CI_lo > 1. If P0 has fewer than 5 events: Haldane ratio ≥ 3, and exact one-sided
  McNemar p < 0.05.
- **S3:** P5 removes ≥ 50% of the P1L excess (point estimate), and Holm-adjusted p(H2) < 0.05.
- **"The laundering loop replicates in model m"** iff S1 ∧ S2 ∧ S3.

**Secondary rules**
- **Shipped quarantine works:** P8a removes ≥ 70% of the excess, with CI_lo ≥ 50%.
- **Induction without a retry motive:** RD(P6 − P0) ≥ +5 pp, with CI_lo > 0.
- **PREREG_v2-style X1 label (θ_D = 10 pp):**
  - GENERALIZES iff CI_lo > 0 and the point is ≥ 5 pp;
  - PARTIAL iff CI_lo > 0 and the point is < 5 pp;
  - FAILS otherwise.
- **Halves:** H1 and H2 are reported beside the full sample.
- **Census:** descriptive only.

## 7. Format predictions (CPU; already measured before registration, therefore descriptive)
These were run on the 1,598 real Gemma slip payloads (`format/format_ext_summary.json`, 18:48Z). They are not tested
here; they define the format column of the benchmark.
- **harmony and mistral JSON-argument slips:** delivered-invalid 100% for the backtick, omission and unescaped-quote
  variants, and 90.6% for the real closers (the other 9.4% are closers that are valid JSON).
- **Valid calls:** exact 100%.
- **History re-render of delivered-invalid calls:** harmony keeps the raw argument text verbatim 100%; mistral
  double-encodes it 100%.

## 8. Execution, stopping and exclusions (as `prereg.md` §9)
- **Order on GPU3:**
  1. gpt-oss-20b;
  2. Qwen3-Coder-30B-A3B;
  3. Devstral-Small-2;
  4. Qwen3.8-27B.

  For each model, the battery runs first and the census tier second.
- **Gemma-4-31B bf16 core arms** (P0, P1, P6, P8a on the same A1 states) run after these, with workstream A's runner.
  They are governed by PREREG_v2 / A, not by this addendum.
- **Stopping:** if a window closes early, the completed contexts are analysed. The achieved n is reported.
- **Interim looks:** operational QA only.
