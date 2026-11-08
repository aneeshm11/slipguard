# DEFINITIONS -- one meaning per word (GemmaProtocol paper + release)

*Owner: workstream R. Version 1.0, 2026-11-04. This file is normative for the paper, the datasheet and every number
in `release/numbers.json`. Any number computed under another definition must say so and appear only as a cross-tab.*

The audit behind this file found **at least 7 different "malformed" predicates** (A judge, A's synthesis replica, B
census judge, C corpus labels, D 13-key classifier, E proxy classifier, F order-replay judge, census). On the 9,430
logged base edits they agree on 9,425 calls. **Almost all of the numeric drift (24.3% vs 34.9% vs 35.0% vs 35.25%;
9,077 / 9,111 / 9,430 / 13,620; 10.8% vs 16.8-17.6%) comes from populations and aggregation, not from the
predicate** (§9). The fixes are therefore (i) one predicate, pinned by hash; (ii) one population key; (iii) one
estimand per question.

---------------------------------------------------------------------------------------------------------------------

## 1. Units and populations

| term | definition |
|---|---|
| **call** | one tool call in one assistant turn: the text from `<|tool_call>` to `<tool_call|>` (or to the end of generation), or tool-call text the server left in `content`. |
| **edit** | a call whose name, as recovered by the judge (also from unparsed text), is `edit_file`. |
| **attempt** | one agent run on one task, keyed by **(run, log file, attempt id)**. Never by attempt id alone: runs `run-03` and `run-05` reuse bare task ids (8 collide; 109 task ids are shared). |
| **trajectory** | the chain of calls of one attempt as seen through its message-prefix history (D's unit; interleaved chains are split). |
| **context** | the exact prompt (messages + tools) that preceded a call. |
| **base** | `gemma-4-31b-it-qat-w4a16-ct` without adapters (official QAT checkpoint, competition pin). |
| **FT** | the competition team's LoRA adapters (r0, r1, r1v, r2, r3b, rl1, rl1v2, rl2, rl3). Always a separate split; r1/r2/rl* were trained on data containing Qwen teacher rows. |
| **BROKEN** | runs `BROKEN_*` (a known-bad adapter). Kept in the corpus with `run_status=broken_run`, excluded from every rate. |
| **teacher run** | `t1_qwen`, `t2_qwen_rebench`, `t3_qwen_rebench` (Qwen3.8-Flash-Next) and `dsprobe` (DeepSeek-V4-Flash) -- served under the Gemma alias. **Excluded from every Gemma statistic.** A context containing any teacher-authored turn is *teacher-contaminated* and excluded from "Gemma-only" sets. |
| **natural edit / forced edit** | natural: the model's own next call was `edit_file`. forced: the replay forced an `edit_file` header. Never pooled; forced-edit results are a separate row. |
| **field split** | the logged June-5-template corpus (deprecated configuration). **replay split**: generations made by this project (July template unless stated). **gold-intent split**: slips whose intended arguments are known. |
| **template** | June-5 (md5 `d6c5bd0d`, produced the logs) or July-9 (md5 `f016bd4b`, current HF). Every table states its template. |

## 2. MALFORMED (canonical: **M-A v1**)

**Definition.** A call is *malformed* iff the competition-pinned lenient pipeline would hand the agent something other
than a well-formed call with exactly the declared, required arguments. Operationally it is the function
`judge(stage2_text, stopped_on_close)` in `experiments/contagion/scripts/gemma_protocol.py`
(**sha256 prefix `e10becb233b3c384`**, lines 132-175; preserved verbatim as `gemma_protocol_v1_backup.py`), applied
to the generated text after `<|tool_call>`.
*Version note (15:35 UTC).* A's current `gemma_protocol.py` (`7cb28718...`, frozen 15:13 UTC for the confirmatory
study, judge at lines 179-224) parameterizes the edit tool and its key names by a tool profile so that the same rules
apply to P's harness. Under the `main_track` profile the judge is unchanged: the diff is confined to the profile
substitution (`edit_file` / `filepath` / `old_string` / `new_string` -> `PROFILE[...]`) and an extra `is_edit` field
for profiles other than `main_track` (A's name for the discovery harness); `parse_args` and `raw_args` are byte-identical; A's regression re-judged 20,374 outputs
and 616 re-renders with 0 mismatches. M-A v1 on `pnc` = the same rules under P's profile.
The rules:

1. **Extraction** with vLLM 0.19.1's own regex `<\|tool_call>call:([\w\-\.]+)\{(.*?)\}<tool_call\|>`. No match ->
   malformed (`unparsed` / `unparsed_unclosed`); the tool name is still recovered so an unparsed `edit_file` counts
   as an edit.
2. **Lenient parse** with vLLM 0.19.1 `_parse_gemma4_args` (array-hang guard; 5 s alarm -> `parse_timeout`).
3. **Flags** (any flag -> malformed):
   * `missing:<key>` -- a required key is absent (`REQ` for edit_file, write_file, read_file, run_command);
   * `extra_key` -- edit_file carries a key outside {filepath, old_string, new_string, allow_multiple};
   * `leak_closer:<key>` -- any string value contains a look-alike closer run `["`\\']+` followed by optional
     whitespace, `,`, a protocol key name and `:` (the absorption signature);
   * `special_tok` -- a value contains `<|"|>`, `<tool_call|>` or `<|tool_call>`.

**For logged calls** (field split), where only the server's parsed arguments survive, M-A is applied as: post-parse
flags 3 on the logged arguments + step 1-2 on any tool-call text left in `content`. **Unit decision:** under M-A an
unparsed `edit_file` text is an edit *and* malformed, so the 5 base raw-unparsed edit texts enter both numerator and
denominator: 3,298 / 9,435 = **34.95%** (verified from the records by `release/hosting/notebook/recompute.py`), versus
C's published 3,293 / 9,430 = 34.92% (parsed calls only). Post-parse flag differences on the parsed calls are
expected to move the count by about +/-4 (definitions audit; recompute pending, §9). Until the recompute lands, the
paper writes "35% (3,293 / 9,430 parsed edit calls)".

**Known gaps of M-A v1 (kept for comparability; fixed only in a versioned M-A v2):** unknown keys are checked for
edit_file only; an undeclared tool is not flagged; an empty-closer `,key:` is not flagged; no-op edits are not
flagged; type mismatches are not flagged.

**Cross-tab definitions** (report beside M-A, never instead of it):

| tag | name | where | differs from M-A by |
|---|---|---|---|
| M-C | corpus labels | `conformance/slips/extract_slips.py:78-108` | schema-based for every tool; undeclared tool and non-object args flagged; absorption only for keys that are declared **and absent** (`gemmaproto.find_absorbed`); type mismatch recorded, not malformed |
| M-S | strict | `gemmaproto` reference parser + schema | any deviation from the L0/L1 grammar (17 error codes) -- the fail-loud contract |
| M-B | census judge | `intent_decoding/gemma_protocol.py:700-731` | empty closer allowed; any declared key; schema-based unknown keys for all tools |
| M-SYN | synthesis replica | `contagion/scripts/extract_index.py`, `ideation/community/synthesis_scripts` | 8-key global list; teacher runs included in the original synthesis -- **retired** |
| M-D | 13-key classifier | `protocol_theory/sim/extract_calls.py:10-50` | 13-key global list |
| M-E | proxy classifier | `endtoend/export/quarantine_renderer.py:37-79` | closer must be immediately before `,KEY:`; KEY declared and != host |
| M-F | order-replay judge | `protocol/order_replay.py:35-48` | no unknown-key or special-token check; edit_file header forced |
| M-CEN | census | `format_census/census.py:5-21` | adds `noop_edit`; all models pooled -- **never a Gemma base rate** |

## 3. SLIP

* **closer slip** (the mechanism the paper is about): inside a string argument, the model emits a look-alike closer
  -- a maximal run over {`` ` ``, `"`, `\"`, `"""`, `'`, `'''`} (composites such as `` "` `` included) -- where the
  protocol requires `<|"|>`, and continues with `,<key>:`. Under the lenient parser the next argument is swallowed into
  the open string. Detector: B's `first_slip_site` on raw text; on logged arguments the `leak_closer` flag / C's
  `absorbed_arg`. A closer slip is malformed (M-A) except when the swallowed key is optional and still present.
* **slip** without qualifier = closer slip. Other malformed classes use workstream E's taxonomy
  (`key_restart`, `opener_drift`, `key_drift`, `unparsed_call`, `unknown_tool`, `other_malformed`), carried by every
  corpus record as `e2e_class`.
* **closer share** (e.g. "backtick 84.1%"): numerator = base edit slips whose first absorption closer *adjacent to the
  comma* is a backtick; denominator = **all** base malformed edits (M-C). State this every time; other definitions give
  83% (maximal run) and 86.5% (four canonical closers only).

## 4. ONSET

* **onset** = a malformed edit whose visible context contains **no** malformed call (nothing compacted-out counts as
  visible). This is a property of the call and its context, not of the attempt.
* **first-edit rate** = P(malformed | the edit is the first edit_file call visible in its context). Canonical value:
  D's `first_ctx` = 484 / 2,883 = **16.8% [15.5, 18.2]** (base, June template). Per-file "first edit of the attempt"
  (17.1%, C/F) is an acceptable cross-tab; 10.8% is **retracted** (teacher runs included).
* **onset rate (later edits)** = P(malformed | edit with a clean visible history and >= 1 earlier clean edit):
  4.3% [3.6, 5.1] (D `eps_later`).
* **onset at the decision point** (F) = P(the token after the end of `new_string` is a look-alike instead of `<|"|>`)
  on clean-history states, by teacher forcing; population-weighted to the logged slip rate.
* Causal replays: onset = the P0 arm (original, clean history).

## 5. CONTAGION

* **contagion (causal)** = the change in the **unconditional** probability that the next call is a malformed edit
  caused by putting a corrupted call, as the template re-renders it, plus its tool response into the history;
  estimated by paired history injection on identical contexts with common random numbers:
  **RD = P(P1k1) - P(P0k0)** (primary; attempt-cluster bootstrap); the ratio is secondary and never quoted with an
  infinite CI. P(edit) and P(malformed | edit) are reported beside it.
* **decomposition** of the P1 malformed mass (A's copy check): *verbatim copy* of the laundered value, *clean retry*,
  *same-content variant*, *new content*. **copy-on-retry** = the verbatim-copy share; **format induction** = elevated
  malformation on new-content edits, claimed only under the pre-registered rule (P6 - P0 >= +5 pp, CI_lo > 0, on both
  the gate and the held-out half).
* **post-slip hazard (observational)** = P(malformed | >= 1 malformed call visible in the context). Descriptive and
  confounded (retries, task difficulty); never called "contagion" without the word *observational*. "Critical",
  "absorbing", "self-reinforcing" and "cascade law" are retired (PLAN §5).

## 6. LAUNDERED (three different things; never interchange)

| term | definition | example number |
|---|---|---|
| **laundered call** (record label `history_laundered`) | the parser accepted the corrupted call without error, and the chat template re-renders it as a strictly **well-formed** call that parses back (strict reference parser) to the **same corrupted arguments** | 53.0% [51.3, 54.7] of base edit slips (1,746 / 3,293) |
| **re-rendered unflagged** | the corrupted call re-enters the next prompt byte-identical to the canonical re-render, with no flag from LiteLLM/ADK (it may be well-formed or not) | 7,274 / 7,274 parsed-malformed calls (base + FT). PLAN §1.1's "7,274 laundered slips" must be re-worded to this term |
| **parser laundering** | a runtime turns a *visible* failure (text left in content) into a *silent* call | vLLM 0.31: 620 / 676 real raw outputs -> calls, 20.0% of them schema-valid |

**laundering loop** (paper title concept) = lenient parse -> well-formed re-render -> copy/imitation on the next
edit. A *laundered exemplar* in the P1 arm is a laundered call by the first definition.

## 7. DELIVERED-MALFORMED and related outcomes

* **delivered** = what the serving stack (server parser + proxy/decoder, if any) hands to the agent framework for one
  model turn.
* **delivered-malformed** = a delivered call that is malformed under M-A applied to the delivered arguments.
* **delivered-loud** = the stack returns an explicit error or no call (refusal, `MalformedToolCall`, text in content);
  not malformed, counted separately.
* **silent corruption** = a delivered call that the framework accepts (declared tool, required keys present, no unknown
  keys) but whose arguments are not the intended ones: on gold-intent data, `args != gold`; on natural traffic, the
  proxy "strict-invalid or look-alike + `,KEY:` text or a special token inside an accepted call". Grammar-constrained
  decoding is judged on this outcome.
* **executed-corrupted** (ADK) = ADK runs the tool with corrupted arguments: 832 / 4,411 = 18.9% of base parsed-malformed
  calls of **any** tool; 35.5% of all 7,274 (base + FT). Always state the denominator.

## 8. Reporting rules (binding for every workstream)

1. Primary causal outcome: unconditional per-context P(next call is a malformed edit), RD first, ratio second.
2. Populations: base vs FT separate; teacher runs and teacher-contaminated contexts excluded; natural vs forced
   separate; June vs July separate.
3. Clustering: attempts (injection), tasks (end to end), contexts (replay). Wilson for single proportions.
4. Holm within each pre-registered family (F1 mechanism, F2 cross-family, F3 decoders, F4 end to end).
5. Every number in the paper exists in `release/numbers.json` with its source file hash; `release/claims_ledger.md`
   must show no MISMATCH row for a main-text claim (`python release/build_numbers.py --strict`).

## 9. Audit: which numbers follow these definitions (2026-11-04 ~12:30 UTC)

| workstream / headline | predicate | population issue | follows? | action (owner, cost) |
|---|---|---|---|---|
| A injection gate (x8.13, P2-P7, copy check) | M-A | gate = 300 pre-registered contexts (`out/gate_gate31b_final.json`); `results.json` has at times pooled pilot files | **yes** | cite the gate file; lead with the unconditional RD (A, none) |
| A 12B / E4B | M-A | off-policy 31B histories | yes | re-word: 12B x4.91 [2.67, 12.4] (n=600); E4B x2.30 [1.18, 5.36] (n=404), fails >=3x gate |
| A observational (35.1%, 17.6%, 76% post-slip, 22.9% affected, resolve 45.4 vs 50.8) | M-SYN | **index drops runs** with a key logged after `response` (9,077 base, ~9.8k FT edits); duplicate attempt ids merged | **no** | fix `extract_index.split_line` (full `json.loads`), key on (run, file, attempt), apply M-A post-parse flags; rerun `analyze_obs`, `export_episodes`, A2 states (A, CPU minutes) |
| B gate (16.0% slips, 17.0% census, rollback 100%) | M-B / closer-slip | 89 of 194 edits are **forced**; contexts drawn from a pool with **546/1,500 teacher** contexts | partly | re-score stored calls with `judge()` (seconds); report natural-only (19.0%, n=105); finish the Gemma-only requeue (B) |
| C corpus (34.9%, 84.1% backtick, 53.0% laundered) | M-C | complete; per-file keys | cross-tab | add an `m_a_v1` boolean per record (rescan logs, ~3 min CPU) so the corpus carries the canonical label (C) |
| D T3 (35.0%, 16.8%, hazards) | M-D | complete; `t3_seqs_check` overwrites 319 edits | cross-tab | rerun `extract_calls` with M-A post-parse flags (D, CPU) |
| E pilots | M-E | own sessions | no | M-A on stored `raw`/`calls[].args` (E, seconds) |
| F order replay (10.5% vs 2.5%; 64.8% vs 50.7%) | M-F | edit header forced in every arm | no | only ok/why/closer stored -> cannot be re-judged without regeneration; label as M-F in the paper |
| F decision point (R = 0.235; 3.7x) | token-level (closer at decision point) | clean-history states, population-weighted | n/a (different unit) | keep; call it "decision-point slip probability" |
| PROT history_split (8.9% -> 86.7%) | M-F | 138/771 contexts teacher-contaminated | **retired** | use D's identical-context replay on Gemma-only contexts (10.6% -> 64.8%) |
| census (12.3%) | M-CEN | all models pooled incl. teacher | **retired as a rate** | keep only call totals (329,359 calls; 1,117 raw) |

## 10. One implementation

Four protocol implementations exist (sha256 prefixes at 2026-11-04 12:40 UTC):
`conformance/gemmaproto/parser.py` `dd041e55...`, `contagion/scripts/gemma_protocol.py` `e10becb2...` (since 14:54
UTC `7cb28718...`, profile-parameterized; see section 2),
`intent_decoding/gemma_protocol.py` `aaf369b9...`, `endtoend/proxy/gemma_protocol.py` `fcff4bed...`.
For v1.0 of the release: `gemmaproto` is the only parser/renderer; M-A v1 is shipped verbatim as
`gemmaproto.judge.judge_v1` with a test that reproduces A's gate labels byte-for-byte on `r31b_old_G.jsonl`; the proxy
and decoders import it (dogfooding columns in the conformance matrix, P0-C). No refactor of running code before the
Nov 5 12:00 freeze -- the release package copies and pins.
