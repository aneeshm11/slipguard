# PREREG deviations log (workstream D)

Any deviation from prereg/PREREG_v1.md (sha256 53e34f1fc0c061e8d67bb559b2458419154159608f9e63cadae8eb9bcbecee38, frozen 2026-11-04 11:47:06 UTC) is recorded here with a UTC timestamp, the reason, and whether it was decided before or after seeing the governed outcome data.

- 2026-11-04 11:57 UTC — clerical, no content change: `E_PREDICTIONS_v1.md` (sha256 182365c9…) says "Written: 2026-11-04
  ~12:10 UTC" in its header. The authoritative freeze time is **11:56:08 UTC**, the PROGRESS.md line written at hashing.
  The file was not edited after hashing.

## Copied from workstream A (`experiments/contagion/out/prereg_deviations_A.json`), verbatim fields; copied by D at 2026-11-04 14:48 UTC
Governing document: paper/protocol_theory/prereg/PREREG_v1.md sha256=53e34f1fc0c061e8d67bb559b2458419154159608f9e63cadae8eb9bcbecee38 frozen 2026-11-04 11:47:06 UTC. Logged by: workstream A (experiments/contagion); for D to copy into PREREG_DEVIATIONS.md (A writes only in its own directory).

1. **2026-11-04 11:47-11:50 UTC — interim look (NT, not prohibited)** (during NT data collection). The NT (July template) runner started at 11:42, before the freeze, without blind logging. Its progress lines showed per-arm counts after the freeze: P0 1/63, P1 28/59, P4 3/65, P5 2/60 (malformed/edit) at 11:50. No analysis decision depended on them. From 11:52 every governed arm runs with --blind (no outcome counts in logs) and is analysed only when complete.
2. **2026-11-04 11:42:25 UTC — data timing** (data existed, not analysed). The final P6/P7 runs at n=300 (out/main/r31b_old_P6.jsonl) completed at 11:42:25, before the freeze. They were not analysed or shown to D before 11:53 UTC, when A's decision_rules.py first computed them. D's predictions for final P6/P7 rest on the interim n=70 only, as PREREG_v1 section 1 states.
3. **2026-11-04 11:52 UTC — operationalisation** (before (final P7 share)). Copying rule, 'P7 slips carry " well above P0's 1/16'. Operationalised as: the Wilson 95% CI of the share of P7 malformed edits whose closer contains '"' lies entirely above the P0 share's point estimate. Written after seeing the interim P7 (7/13) and before the first computation of the final P7 share.
4. **2026-11-04 11:52 UTC — design addition** (before). P6k: besides P6 at k=2,4 on the 305 set, P6 at k=1 is also run on that set, so the P6 dose curve is paired on the same contexts.
5. **2026-11-04 11:47 UTC — design detail** (before). Lag-2 set (k_usable>=2): the 146 gate contexts with k_usable>=2, plus 104 contexts from the random order position 600+ (outside the gate and held-out halves) with their own P0 and P1k1, for 250 in total (data/ids_lag2.txt).
6. **2026-11-04 11:47 UTC — design detail** (before). r-dose: copies 2..r of the corrupted call + ADK error carry no thought (reasoning). The first copy keeps the original thought. Repeats get unique tool_call ids.
7. **2026-11-04 11:47 UTC — design fact** (before). P4' (the replaced call re-rendered canonically in the model's own emitted order + its true success response) is byte-identical to P0 in 297/300 gate contexts (out/p4prime_identity.json). P4' is run only on the 3 differing contexts; on the gate set its removal is 100% by construction. Its informative test is A2 (P4'-MAP).
8. **2026-11-04 11:55 UTC — estimand conflict (flag)** (before (dose, r-dose, lag-2, P6k, P8, P9, A2, held-out)). PREREG_v1 section 5 names P(malformed | next call is edit_file) primary for the governed analyses; its anchors p1=0.462 and p0=0.057 are conditional. UPGRADE_PLAN section 2 and the PI name the unconditional ITT rate primary. A reports both for every contrast. Rule D-M is computed on the prereg's primary (conditional) with the unconditional version beside it. The plan rules that name the unconditional estimand use it. Where a rule names neither, both are reported.
9. **2026-11-04 12:08 UTC — design addition (A2)** (before (no A2 data exists)). A2 adds arm Q8b: E's frozen renderer applied to the LOGGED post-slip history with no raw emission, i.e. sanitized. The logs hold only vLLM-parsed arguments, so the plan's P8a (recovered) needs the raw emission or B's MAP repair. Q8b gives a real natural-slip number for the sanitized shipped path now. P8a and P4'-MAP on A2 follow when B's repairs exist.
10. **2026-11-04 12:08 UTC — data hygiene (flag)** (before). E's renderer flags 11 quoted-key read_file calls (e.g. 'start_line"') in 9/300 gate histories that A's protocol-clean filter passed (A checked unknown keys only for edit_file). A pre-specified sensitivity analysis excludes these 9 contexts (out/p8_extra_quarantined_calls.json).

## D entries for PREREG_v2

- 2026-11-04 14:48 UTC — clerical, no content change: `PREREG_v2.md` (sha256 5da75e61…) says "Written: 2026-11-04, 14:46–15:10 UTC". It was completed and frozen at **14:46:45 UTC**, the authoritative time of its PROGRESS.md line. No P outcome existed or had been opened. The file was not edited after hashing.
- 2026-11-04 14:48 UTC — note on A's estimand flag (entry 8 above): PREREG_v2 resolves it prospectively. The unconditional ITT rate is primary for every arm on P's corpus, and the conditional rate is secondary (§3).

## PI entries for PREREG_v2

- 2026-11-04 15:27 UTC — **design addition, decided blind.** No P outcome has been computed, printed or opened by anyone; P's monitors report operational counts only, and production started at 15:25 UTC.
  - **What:** P's corpus is extended beyond the ~400 SWE-bench Verified tasks.
    - Additional tasks come from the SWE-bench full test split (non-Verified instances), from the same permissively licensed repositories. matplotlib and pylint stay excluded, and no instance already used in the Verified sample or the smoke test is reused.
    - Each extension task gets one S1 episode, with an identical harness, model, sampling, proxy and caps.
    - Extension episodes are appended after the planned 400 S1 + 100 S2 episodes and run until P's existing 07:45 UTC cutoff.
  - **Why:** §2's B1 target (600 first-edit states, at most 1 per episode) exceeds the 500 planned episodes. A2 (k_usable ≥ 4, at most 2 per episode) needs more episodes to avoid triggering the P6k shortfall rule.
  - **What is unchanged:**
    - pool definitions, caps, the per-repo cap, seed 20261105 and the ranking rule;
    - predictions and outcome rules.
  - **Analysis:**
    - Extension episodes carry `split = "swebench_test_ext"`.
    - Primary analysis is the full corpus: every episode generated under the identical protocol.
    - A pre-specified sensitivity analysis re-runs every confirmatory contrast on the Verified-only subset.
  - If the extension images are unavailable, the corpus stays Verified-only and the existing shortfall rules apply.
- 2026-11-04 15:40 UTC: two clerical items from A, recorded by the PI before any P data existed.
  - (a) PREREG_v2 §2's `turn_index` is A's CONTEXT_SCHEMA field `request_index`, the 0-based chat-request index within the episode. A maps turn_index := request_index and logs the mapping in POOLS_MANIFEST.json.
  - (b) The Holm family F1c uses one-sided bootstrap p-values: C1/C2 test H0: RD ≤ 0; C4/C5 test H0: removal ≤ 0.5. Two-sided intervals are reported alongside.
  - A's confirmatory scripts were frozen before any P data existed (experiments/contagion/out/confirmatory_script_hashes_v1.txt): sample_pools_v2.py 4cfc8e0f…, confirm_v2_analysis.py 34ea4647….

- 2026-11-04 15:51 UTC — copied by the PI from A (experiments/contagion/out/prereg_deviations_A.json, key prereg_v2). **design detail, decided blind (PI decision on observation masking)** (before (no P corpus data existed; only P's 4 smoke contexts, of which A read the manifest and the field names in P's builder code, no outcomes)).
  P's harness masks the oldest tool outputs once a prompt would exceed 22,000 tokens. The 2 most recent turns are never masked. A masked output is replaced by the fixed text '[This earlier tool output was removed to keep the conversation within the context limit.]', and the reasoning of that assistant turn is set to null. A's v1 pool and meta builders read a tool result's status from its text, so they would have scored every masked edit result as a success. PI decision, implemented in sample_pools_v2.py and build_contexts_P.py v1.1 (sha256 60025bef… and b7e1fb5d…, frozen 15:51:30Z beside the v1 hashes in out/confirmatory_script_hashes_v1.txt): (1) eligibility and k_usable use each context's history_tool_status (the status as executed), never the rendered text; (2) A1, A2 (and A1k2 under the shortfall rule) exclude every state in which an injection target's tool result is masked in the original context: the most recent prior edit for A1 (k = 1 arms) and the 2 or 4 most recent prior edits for A1k2 or A2 (P6k). Otherwise P0 and P1/P5/P6 would also differ in masked versus unmasked; (3) B1 is unchanged, because its eligibility uses no tool status; (4) POOLS_MANIFEST.json reports per pool the states eligible before rule 2 and the number rule 2 excludes. Same release: every accepted state records its split. The Verified-only subset of each accepted pool is written to pools/verified_only/ for the pre-specified Verified-only sensitivity analysis (PI entry 15:27). confirm_v2_analysis.py is unchanged and runs a second time on that subset. build_contexts_P.py now resolves a relative chat_template_path against the manifest directory. It also judges validity and cleanliness with the same PREREG_v2 malformed criterion as sample_pools_v2.py. Tested on a synthetic 70-context corpus (scripts/test_P_v11.py, PASS). On the unmodified contexts, v1.1 equals v1.

## D entries for PREREG_v2.1 / v2.2
- 2026-11-04 17:38 UTC — **premise correction to PREREG_v2.1** (sha256 bb3696da…), decided before any v2.1 output existed.
  v2.1 states that `enable_thinking=false` makes the model "emit the call with no thought". This is false: B's replays
  show the model still opens a thought (583/587 June-OFF, 584/588 July-OFF; median about 680 characters). v2.1 is run
  exactly as frozen, and its verdicts are read as "under the shipped thinking-off flag". The correction, a manipulation
  check, and a genuinely thought-suppressed arm set (S) are registered in PREREG_v2.2 (sha256 ec9164ff…).
- 2026-11-04 17:38 UTC — clerical, no content change: `PREREG_v2.2_thoughtSuppressed.md` says "Written: 17:37–17:50 UTC".
  It was frozen at **17:37:23 UTC**, per its PROGRESS.md line, and was not edited after hashing.

## A entries for PREREG_v2.1 / v2.2 (copied by the PI from experiments/contagion/out/prereg_deviations_A.json, key prereg_v2.1_v2.2)
- 2026-11-04 17:52 UTC — **operationalisation (S render), decided before any S output** (?). Arm set S renders with enable_thinking=false and appends the template's own closed empty thought '<|channel>thought\n<channel|>' right after the generation prompt. The four appended tokens are 100 <|channel>, 45518 'thought', 107 '\n' and 101 <channel|>; both channel tokens are real special tokens. Evidence: (a) both templates emit exactly this string only when thinking is disabled (June line 351, July line 385); (b) D's anchor no-thought replay (experiments/protocol/order_replay.py without --think) also renders with enable_thinking=False; (c) S is therefore v2.1's render plus the closed thought, i.e. the template's own thinking-disabled form applied at every turn start, including after tool responses, where both templates omit it. All 1,200 S prompts end at '<tool_response|>' before the append, and their last four tokens are the ones above (out/v21_v22_render_check.json). The alternative reading, enable_thinking=true plus the same closed thought, is available as run_cond.py --cond SON. It is not used unless the PI/D decide otherwise before S starts.
- 2026-11-04 17:52 UTC — **design fact found before data (v2.1 P5)** (?). The OFF prompt ends after a tool response in every P0, P1, P6 and P8a context, and in 112/300 P5 contexts. There the June template adds nothing, so the only OFF-vs-ON difference is the system token '<|think|>\n' (verified 1,500/1,500). In the other 188/300 P5 contexts the most recent edit call was the last message. P5 removes that call, the template restarts the model turn, and with the flag off it ends the prompt with its own closed empty thought, '<|turn>model\n<|channel>thought\n<channel|>'. v2.1 is run exactly as frozen. M-v2.1 for P5 is also reported split into template-closed and not template-closed; T4 may carry the 'mixed condition' label (next entry).
- 2026-11-04 17:52 UTC — **operationalisation (manipulation checks), before data** (?). A thought is 'opened' when the generated text before '<|tool_call>' (record field s1_text) contains '<|channel>'. Under S this is a re-opening. Thought length is the number of characters between '<|channel>thought\n' and the next '<channel|>' (or the end of the text). The 80% rule (v2.1) and the 10% rule (S) are applied both pooled and per arm: a verdict is labelled if the pooled share, or the share of any arm in its contrast, crosses the threshold. Labelled verdicts are also reported, descriptively, on the contexts where all arms of the contrast opened, or all did not open (S: did not re-open), a thought. One-sided bootstrap p = (1 + #{RD* <= 0})/(B + 1), with B = 2000 and an attempt-cluster bootstrap; Holm families are as registered.
- 2026-11-04 17:52 UTC — **fact from already-analysed discovery data (no v2.1 output)** (?). On these 300 gate contexts the thinking-ON runs' thoughts are short. Median characters: P0 80, P1 79, P6 228, P8a 188, P5 593; pooled 185. These mid-trajectory states follow a successful edit. D's 680-character prediction [450, 900] came from B's first-edit replays. The M-v2.1 length check is reported against the same-context ON median as registered; the prediction is unchanged.
- 2026-11-04 17:52 UTC — **design detail (H render), before data** (?). H removes reasoning_content and reasoning from every assistant message before rendering, including the corrupted call's own thought under P1. enable_thinking stays true. The June template renders the logged thoughts of the current task segment, so H prompts are much shorter than ON; in the first P1 context, 5,229 vs 13,214 tokens.
- 2026-11-04 17:52 UTC — **operational** (?). v2.1 runs on :8300, as the PI and PREREG_v2.2 state (v2.1's own text says :8302). S and H run on :8302. Both servers have the same non-default arguments as the discovery server (QAT-ct weights, gemma4 parsers, max_model_len 32768, prefix caching), and the generation_config defaults are T 1.0, top-k 64, top-p 0.95. The logged T and top-p are sent per context. Per-context seeds are the discovery ones, giving common random numbers with the ON runs. conc <= 24, --blind. If v2.1 is not finished at 20:30 UTC, its remaining jobs finish on :8302 by resuming the same output file after the :8300 runner stops; there is never more than one writer.
- 2026-11-04 18:01 UTC — **PI decision (S render approved) + four-token verification** (?). The PI approved S as implemented at 17:5x UTC: enable_thinking=false, with the template's own closed thought '<|channel>thought\n<channel|>' appended after the generation prompt. SON is skipped, and runs only as exploratory if :8302 has spare time after S and H. Four-token verification with the model's tokenizer: '<|channel>thought\n<channel|>' encodes as [100, 45518, 107, 101], i.e. ['<|channel>', 'thought', '\n', '<channel|>']. 100 and 101 are the registered special tokens <|channel> and <channel|>, so the thought closes with the real control token. All 1,200 S prompts end in exactly these four ids (out/v21_v22_render_check.json). Both templates emit this string verbatim for thinking-off (June line 351, July line 385). The model's own generated thoughts in the thinking-ON gate runs all open with '<|channel>thought\n' (646/646 P0 samples) and close with '<channel|>' (out/v22_thought_form_check.json). Template finding for C and the paper: out/template_thinking_off_gap.md (evidence in out/template_thinking_off_check.json).
- 2026-11-04 17:55 UTC — **operational** (?). v2.1 started on :8300 at 17:55 UTC (scope ap-ctg-31b-v21-*, conc 24, --blind). The server's non-default arguments were checked and are identical to the discovery server's.
- 2026-11-04 18:19 UTC — **operational interruption (data access), no outcome seen** (?). At ~18:12 UTC the user moved the main-track tree (/harness -> <competition-logs>). 780/1,500 v2.1 jobs failed at render (FileNotFoundError); nothing was sent to the server for them. A verified that the moved data are identical (1,500 + 720 prompt token counts re-rendered exactly) and resumed v2.1 and started S through a path shim at 18:16. At ~18:18 the PI put a HOLD until the user confirms access to the new location. Both runners were stopped at 18:18:23 and H never started. The 139 records generated from the new location are kept and flagged (out/moved_data_provenance.json). The 720 v2.1 jobs from before the move are intact and blind. No analysis has been run.
- 2026-11-04 18:27 UTC — **operational (data access approved; server change)** (?). The user approved read-only use of the moved tree: 'Continue to use it, <competition-logs> can be used, no issues' (relayed by the PI). The batteries resume via scripts/with_paths.py, sequentially on :8302 (GPU2, discovery-identical arguments): the v2.1 remainder, then S, then H. :8300 went to P's corpus lane. v2.1's first 787 records came from :8300 and its remainder comes from :8302; the analysis records each record's server.
- 2026-11-04 19:07 UTC — [prereg_v2] **pre-data change: shipped quarantine renderer v1 -> v2 (PI instruction), no P outcome seen** (?). E's verify-then-repair fix changed the shipped renderer endtoend/export/quarantine_renderer.py. A's confirmatory scripts froze v1 (sha256 13e28567...). The file was replaced at 18:48:10 UTC by 6b08b6e9..., the version the PI announced, and again at 19:05:22 UTC by 5ca5c62c..., the version on disk at the check. PI: the confirmatory runs use the shipped v2, so that what is tested is what is shipped. variants.py is unchanged and imports E's export file read-only. Equivalence check (scripts/check_renderer_v1_v2.py -> out/renderer_v1_v2_check.json): every one of A's discovery renders through E's renderer (unique context x arm: P8a 594, P8b 300, Q8b 300, Q8M 282; 1,476 in all) and the P8a/P8b renders of P's two eligible smoke contexts (S1 profile) were re-built with v1 and with each new version. The full prompts were byte-identical and the quarantine actions identical in 1,476/1,476 for both 6b08b6e9 and 5ca5c62c. The smoke renders were identical in 4/4 for both. There were 0 differences, so the discovery results carry over to the shipped renderer unchanged. All v2.1 and S runs loaded v1. Each runner loaded the module at process start, and every start (17:54, 18:16, 18:28, 18:44) preceded 18:48. Because the renders are identical, this has no consequence. Open item: E must declare a final frozen sha256. At the start of the confirmatory runs A will record the renderer sha256 and require it to equal that declared sha.

## PI entries for PREREG_v2.3
- 2026-11-05 07:10 UTC: **design restriction, decided before any v2.3 output existed.** Only the primary family runs: O0 vs O1, i.e. ADK + LiteLLM tool-result serialization, a property of the public stack.
  - The secondary arms O2 (main-track team system prompt) and O1r (reverse transplant on main-track discovery states) are **not run**.
  - Reason: the user directed (07:0x UTC) that the paper must not rely on the main-track competition work.
  - The primary Holm family is unaffected.

## A entries copied by the PI (Nov 5)
- 2026-11-05 07:06 UTC — [A, prereg_v2] **operationalisation of the Verified-only sensitivity (C3), decided on FAKE data before any real confirmatory analysis** (?). S1 pools (07:02:24 UTC): A1 300, A2 216, B1 600. A2 falls short of 300 only through the 2-per-episode cap; it has 351 eligible states, so the A2 < 150 shortfall rule does not apply. The Verified-only subset has A2 = 58. On that subset the frozen confirm_v2_analysis.py takes its shortfall branch, which crashes on the empty A1k2 pool (IndexError, shown with fake results in data/smoke_confirm_fake/). For the sensitivity run only, data/confirmatory/pools_verified_sensitivity/ sets S1_A1k2 := the 58 verified A2 states, so the script runs unchanged. Its 'k124_on_A2_underpowered' block is then C3 under the primary design (P6 at k = 1, 2, 4 on A2), restricted to Verified. A applies the C3 rule to that block. The full-corpus primary analysis is unaffected.
- 2026-11-05 10:46 UTC — [A, prereg_v2] **EXPLORATORY bf16 precision row: subset rule pre-declared before any bf16 output (PI constraint)** (?). The bf16 server (gemma-4-31b-bf16 on :8304) keeps about 17k tokens of KV cache, so every request needs prompt + max generation <= 16.4k. The bf16 row is restricted to the S1_A1 states whose longest arm prompt (max over P0/P1/P6/P8a of the QAT run's n_prompt; the bf16 render is identical) is <= 13,000 tokens: 50 of 300 states, 42 episodes (data/confirmatory/bf16_subset_ids.txt). The QAT comparison is restricted to the same 50 states. The runner uses --max_model_len 16400, so max_tokens = min(7168, 16392 - prompt) >= 3,392. On these 50 states, 0 of 200 QAT jobs had prompt + generation above 16.4k (the QAT p99 generation is 2,679 tokens), so the cap would not have bound under QAT. Cap hits are reported. Alternatives considered: full generation parity (prompt <= 9,224) leaves 23 states; thinking budget plus a 1k call (prompt <= 11,272) leaves 32. The A1 median prompt is 16.8k tokens, so most A1 states cannot fit this server at all.
- 2026-11-05 07:12 UTC — [A, prereg_v2.3] **PI decision before data, per user directive** (?). The optional arms O2 (system-prompt transplant from the main-track contexts) and O1r (reverse transplant on main-track discovery states) are NOT run. The user asked us not to rely on the competition (main-track) work. O1 tests a general property of the public ADK + LiteLLM stack; O2 and O1r would test the team's own setup. Only the primary family O0 vs O1 runs.
- 2026-11-05 07:12 UTC — [A, prereg_v2.3] **operationalisation, before data** (?). O1 construction: every role=tool content c becomes json.dumps({'result': c}, ensure_ascii=False). This is google-adk 1.36.1's own path for a text-returning tool: functions.py:1117 wraps a non-dict result as {'result': value}, and lite_llm._content_to_message_param sends _safe_json_serialize(response). Verified (out/onset_o1_verification.json): equal to the real ADK serializer on 9,211/9,211 tool results of the 600 states. Against C's library-faithful ADK -> LiteLLM 1.104 -> vLLM 0.19.1 pipeline (experiments/conformance/history/pipeline.py, read-only), both the wire tool contents and the rendered tool-response segments are byte-identical on 6/6 states (78 tool results). O0 renders reproduce the logged prompt_tokens on 600/600. Manipulation strength: tool results containing \" rise from 39/9,211 (0.4%) in O0 to 2,959/9,211 (32.1%) in O1, against C's 46.6% rendered and 44-48% logged in the main track. Mean prompt length rises from 13,872 to 14,827 tokens; the maximum is 24,072, so no state lacks room. The comparison with what the main-track pipeline produced uses C's library pipeline and C's documented rates; no main-track log was read (audit).
- 2026-11-05 07:12 UTC — [A, prereg_v2.3] **operationalisation, before data** (?). Outcomes: A's runner judges the FIRST call of the next turn, stopping at the first closed call as in every A battery, so 'the next turn contains an edit call whose value is closed by a look-alike closer' is read as 'the first call is an edit call whose string value contains a look-alike closer followed by ,<declared key>:' (judge closer != None). String-mode drift is measured per state: an edit's new or old string value contains a literal backslash-n or backslash-quote sequence that occurs nowhere in that state's native (O0) tool-result texts. This stands in for 'where the file has none', since file contents are not otherwise available. Each B1 state is its own episode, so the episode-cluster bootstrap resamples states (B = 2000). Scripts were frozen at 07:11:56Z (out/onset_v23_script_hashes.txt).
- 2026-11-05 11:08 UTC — clerical, no content change: `PREREG_v2.4_injectedSlipRepair.md` (sha256 e7af894b…) says "Written:
  2026-11-05, starting 11:10 UTC". It was written from about 11:05 and frozen at **11:07:17 UTC**, per its PROGRESS.md
  line. The file was not edited after hashing.

## B entries for PREREG_v2.4 (injected-slip repair battery): operationalisations, logged 2026-11-05 11:19 UTC, BEFORE any battery output exists
Re-checked first: PREREG_v2.4 sha256 e7af894ba355a03a5fb7b023c3c7ad860a5e8c3d666a4ab80e6ff6c7ea102090. Nothing in the
document is unimplementable. These entries pin choices the text leaves open; none changes a registered rule.
1. **Candidates.** One candidate per P S1 context, i.e. a request whose response's FIRST call is `edit_file` (P's contexts
   definition). An `edit_file` call that is not the first call of its response is not a candidate, because its
   teacher-forced prefix would contain another call.
   - "Strictly valid" is B's frozen reference (`confirm/gemma_protocol.is_valid`, sha b8dac830) on the logged raw call,
     which must be closed by `<tool_call|>`.
   - The delivered (vLLM-parsed) arguments must equal the strict parse.
   - The call's tool-result status in P's outcomes must be `ok`.
2. **Render.** P's manifest template (`chat_template.jinja`, md5 f016bd4b…), system content as parts. A state whose
   re-render does not reproduce the logged `prompt_tokens` is skipped at acceptance and counted. The logged thought and
   call text are teacher-forced as text, re-tokenized: P logged raw text, not token ids.
3. **Caps.** At most 2 per episode (episode = attempt_id, turn_index = request_index). "No repository above 40%" is
   implemented as in PREREG_v2 §2: a repository's further states are skipped once it holds 40% of the target (240).
4. **Strata.** For accepted rank r = 1…600, the stratum is ['BT','DQ','EQ','TB'][(r−1) mod 4]. Closers: `` ` ``, `"`, `\"`,
   ```` ``` ````.
5. **Seed.** One seed per state: s = int(sha256("PREREG_v2.4|20261105|seed|" + context_id)[:8], 16) mod 10^6.
   - The live continuation uses s.
   - Within B's frozen code: IPD resumes use s + 1000(round+1), grammar-CD uses s + 200 + round, and retry×2 uses
     s·1000 + 77 + try (the "new seeds").
   - Greedy runs at T = 0.
6. **Code.** The prereg names `experiments/intent_decoding/{arms,intent_decode,gemma_protocol}.py`. B uses the frozen
   copies in `experiments/intent_decoding/confirm/`:
   - gemma_protocol b8dac830 and arms 5a521ae8 are byte-identical to the named files;
   - intent_decode bda60a08 is the named file plus the top-k pass-through that P's sampling (top-k 64) requires.
   - Combined freeze sha 2ee89869….
7. **IPD timing.** IPD follows B's `rollback_resume`, as the prereg's §1 note says ("arm semantics follow that code"): it
   acts when the live continuation has ended. A strictly valid emission is returned unchanged. Otherwise it rolls back
   to the first violation (rules closer + opener; noisy-channel cut with the frozen closer prior), forces `<|"|>` and
   resumes, for at most 4 rounds. There is no interception mid-stream.
8. **Delivery policies** (as in B's PREREG_v2 analysis):
   - lenient, grammar-CD and greedy deliver leniently;
   - fail-loud, T1, IPD and retry×2 deliver only strictly valid calls, otherwise loud.
9. **Outcome order** (mutually exclusive):
   1. loud;
   2. exact (delivered arguments == gold);
   3. delivered-malformed (census judge: vLLM parse plus missing/unknown key, look-alike+declared-key leak or special
      token; also unfinished);
   4. silent corruption (slip damage, defined below);
   5. other valid.
   - Slip damage is (a) a look-alike `,<declared key>:` residue or special token, more often than in gold; (b) a lost,
     extra or misassigned argument; or (c) a `new_string` that differs from gold by look-alike characters at the cut
     (extension by a look-alike, truncation of look-alikes only, or look-alike-only remainders).
   - A census-clean delivered call from a lenient-delivery arm that is not strictly valid is judged on its delivered
     arguments.
10. **Mechanics.** These are judged on the live continuation after the injected closer:
    - doubling: it starts with `<|"|>`;
    - slip pattern: `[ws],[ws]<declared key ≠ new_string>[ws]:`, or `[ws]}`, or empty with the call closed;
    - content continuation: anything else.
    The detectable subset is "emission not strictly valid or not closed".
11. **Estimation.**
    - Strata weights are renormalised over the strata present in a subset.
    - Reweighted single rates: Wilson at Kish effective n. Per-stratum rates: plain Wilson.
    - Contrasts: episode-cluster bootstrap with B = 4,000, percentile CI, p = (1 + #{Δ* ≤ 0})/(B + 1).
    - "Pooled EQ + TB" = unweighted over the detectable EQ ∪ TB states.
    - If both the BEATS and the TIE condition hold, BEATS is reported.
    - The exact-intent ceiling, P(live old_string = gold), is reported descriptively as old_string-exact per arm.
12. **Token cap.** The live continuation and every arm generation are capped at 4,096 tokens with stop `<tool_call|>`.
    This will be confirmed against the gold call-length distribution before the GPU run.
13. (11:22 UTC, after the state selection, before any battery output) **Token cap confirmed.** The gold call lengths
    are median 132, p99 856, max 1,065 tokens; the post-slip remainder is max 508. The 4,096-token cap (entry 12) stands.
    Selection facts:
    - 3,292 eligible of 3,941 S1 contexts (excluded: 514 tool result not ok, 131 not strictly valid, 2 delivered ≠
      strict parse, 2 prompt > 24k); 0 render mismatches; caps skipped 89 (episode) and 75 (repo).
    - 600 accepted (4 × 150) from 458 episodes; django at the 240 cap.
    - Only 17/600 gold `new_string` values end in a look-alike character (BT 4, DQ 5, EQ 2, TB 6). Those are the states
      where a text-only cut is ambiguous, so the composite-closer contrast rests on few states.
    - Builder crash and fix: `build_battery.py` 5713140f… crashed before any output (Pair field name). Fixed as
      ba09d2c4…, logged in PROGRESS.md at 11:20.

## PREREG_v2.5_stackGain (frozen 14:00:57 UTC, sha256 50f8a395…)
- **2026-11-05 14:06 UTC — replay preconditions CONFIRMED by A (§3, §4). The switch rule is NOT triggered: R1 stays primary for F1, and
  the O0 replay stays primary for F2.**
  - Recorded before any v2.5 outcome was opened. A read only metadata and prompts.
  - Source: `experiments/contagion/out/confirmatory/v25_replay_preconditions.md` (sha256 7f901a73…), also logged in
    PROGRESS.md.
  - **Junction.** The prompt ends with `<|channel>thought\n`. s1_text runs up to the first `<|tool_call>`, which the model
    generated itself in the same request. s2_text runs to the stop token `<tool_call|>` (id 49), which is excluded.
  - **Stop semantics.** Stop id 49 only, with no stop strings. Every record stopped on 49; none was truncated at
    max_tokens.
  - **Prompt length.** Re-rendering with A's frozen builders (renderer 5ca5c62c…) gives len = n_prompt for P0, P1 and
    P8a (300/300 each) and for O0 and O1 (600/600 each). A per-record prompt-sha manifest is available.
  - **Server.** The same vLLM 0.19.1 process (QAT-ct W4A16, TP1, max_model_len 32768) served C1 and v2.3. T 1.0 and
    top-p 0.95 were sent. top-k was not sent, so the generation_config default of 64 applied, which matches the
    prereg. One md5-derived seed per state is shared across arms.
  - **Pre-declared handling of budget-forced records.** These are records whose thought hit 4,096 tokens: C1 P8a 1/300,
    O0 3/600, O1 5/600. A's runner inserted `<channel|>` and regenerated with seed+1/+2.
    - The replay applies IPD to the logged call text, with the logged forced prefix, exactly as A's runner produced
      it.
    - These records are flagged.
    - A sensitivity analysis excluding them is reported beside the primary. It is not a separate verdict.

## B entries for PREREG_v2.5 (stack gain), logged 2026-11-05 14:10 UTC, before any v2.5 generation or outcome
1. **Server.** The resumes, F3 and L1 run on :8300 (GPU0), because :8303 no longer exists. Its args equal A's :8303 list
   (vLLM 0.19.1, the same model, max-model-len 32768, gpu-memory-utilization 0.90, prefix caching, max-logprobs 20,
   max-num-seqs 64, gemma4 parsers). top_k 64 is sent explicitly; A's runs used the generation_config default, also 64.
2. **Seeds.** Each state's seed is A's seed_of (md5(context_id)) and is shared by F3's two arms and by L1. IPD resumes
   use B's frozen schedule: (seed mod 10^6) + 1000·(round+1).
3. **Budget-forced base records** (C1 P8a 1/300; O0 3/600; O1 5/600). IPD is applied to the logged call with the
   logged forced prefix. These records are flagged, and the sensitivity analysis excluding them is reported beside each
   primary (analyze_v25.py), as D and A pre-declared.
4. **L1 base decode.** B's frozen budget emulation, two requests (thought up to 4,096 tokens, `<channel|>` forced if the
   budget is hit, then the answer up to `<tool_call|>`). This is the prereg's "B's thinking-budget emulation"; A's
   runner did it in one request plus a post-hoc cut.
5. **Classification.**
   - A SLIPGUARD first call that is an edit by name and is refused by the strict parser is **loud**.
   - A refused or delivered non-edit first call is **no edit**.
   - SLIPGUARD drift is computed on the delivered strictly-valid call with v2.3's definition.
   - Parser disagreements (slipguard strict vs B's is_valid) are counted and never reclassify.
6. (15:05 UTC, operational bug fix; no v2.5 outcome opened) In the first replay pass, all 300 C1 P8a replays failed at
   prompt construction with `ValueError: signal only works in main thread`. The glue built A's prompts in a worker
   thread, and A's `parse_args` (used by the P1/P8a construction) sets `signal.alarm`. P0 and O0 do not use it, and
   their 900 replays completed.
   - Fix: build the prompt in the main thread. This is a one-line change with no algorithmic change.
   - New glue sha256: d3440af4c0d85c208e7aae921e9310d5eda3cfb38687735147f2bf98fcd6b872 (was 21db9d7d…).
   - The 300 error records were moved to `v25/out/replay_attempt1_errors.jsonl`. The lane was stopped (L1 had written
     0 records) and restarted.

## B entries for PREREG_v2.5b (E4B), logged 2026-11-05 21:14 UTC, BEFORE any v2.5b outcome is opened
Prereg sha256 re-checked: c78e7512485a6f3e98e2fd71f319638aa72ff10f2eb5f6deedc89415a94ffb7d.
1. **§2 preconditions on A's E4B run** (experiments/contagion/out/main/rCe4b_v2.jsonl). Only metadata was read
   (v25b/preconditions_e4b.py ca3278fd6fce478715a26dc4ea115000f3aa3d3bd90d81ef6a66da7e946d1f58; v25b/out/preconditions_e4b.json 3c422c2ca3d20ef468360050837619ebd0ddf5720d48fa0bb8e51d0eb31e10db).
   - Re-render with A's frozen builders gives len == n_prompt: P0 300/300, P1 300/300, P8a 300/300.
   - Errors: 0. Stop id 49 and finish 'stop': 300/300 in each arm.
   - Junction: the same runner (run_injection.py, A's log header "1aadb39d"), so the call opener `<|tool_call>` is
     model-generated, as in v2.5.
   - Budget-forced records: P1 1, P0 0, P8a 0. They are flagged and covered by the sensitivity analysis.
2. **Render identity and N1** (glue cpu mode; v25b/out/cpu_checks.json 2c4618080874e6053941b76a1c477d60d123327e930d5e0c2f480e2dc54ab358):
   - HistoryGuard(P1) == A's P8a context on 300/300;
   - N1: HistoryGuard on P0 leaves the messages and the rendered prompt identical on 300/300.
   - The tokenizer is byte-identical between the 31B and E4B directories (tokenizer.json md5 72b10445,
     tokenizer_config.json md5 3b43bf42).
3. **Server.** :8311 is the SAME process that served A's E4B run: unit ap-vllm-g1-2836398, active since 08:07:42 UTC;
   A's run was 08:10–09:30 on :8311.
   - Config: vLLM 0.19.1, model models/gemma-4-e4b-it-qat-w4a16-ct, max-model-len 32768,
     generation_config T 1.0, top-p 0.95, top-k 64; A's records show T 1.0 and top-p 0.95.
   - So no listed item differs, the "cross-server resume" flag does not apply, and the worst-case sensitivity is not
     triggered.
4. **Switch rules:** none is triggered; all checks hold on 100% of states.
5. **Code.** The glue is v25/stack_runner.py (d3440af4…) with paths only changed, as v25b/stack_runner_e4b.py (f3e4d7aeac1390ff95f04cd3c79118ea285f5eeb797328ceb51c84e97e8324ac):
   - the output directory is v25b/out;
   - the replay reads A's rCe4b_v2.jsonl only (no O23);
   - the server defaults are :8311, gemma-4-e4b.

   The analysis is v25/analyze_v25.py (b9cc42d2…) restricted to F1/R1, as v25b/analyze_v25b.py (c15699865013b7c790a1afeef14a5de78954bf3baba14ba77e26ff07f9c8ba36):
   - the E4B glue and the E4B C1 file;
   - no F2/F3;
   - H1-E4B alone at α 0.05;
   - the §5 labels and sentences.

   The diffs are documented in each file's docstring. In-flight cap: ≤ 8 (--conc 6, --workers 2).

## PREREG_v2.7_robustness — pre-data clarifications (2026-11-06 13:34 UTC, PI; no v2.7 job has run)
1. **Soak K1 proxy concurrency.** §5 does not fix the proxy's `--max-backend-conc`. It is set to **64** (the default is 24), so that with 48 requests in flight and 50/50 routing, the proxy's own semaphore never queues. Queueing would inflate K-c for reasons unrelated to per-request overhead. All other proxy flags are README task 3 defaults. Recorded in experiments/v27/soak.sh.
2. **Ports and cores.**
   - Servers: :8370+gpu.
   - Proxy: :8480.
   - CPU cores:
     - servers: tools/serve_vllm.sh blocks;
     - runners: 88+2g;
     - proxy: 96–101;
     - soak driver: 102–103.
   - Launch scripts: experiments/v27/{lane.sh, soak.sh}. Both gate every launch on the GPU (< 2 GB used, 0 apps).
3. **Lane order and GPU assignment (operational; 2026-11-06 15:33 UTC, before any v2.7 job).** The user freed GPU0 first (free >= 10 min at 15:32:22 UTC; GPUs 1-2 still hold the user's processes, GPU3 another user's). Lanes run through experiments/v27/dispatch.sh in priority order D (RD16), T (RT06 then RT00), S (RSA then RSB), K (soak), each on whichever GPU 0-3 passes the gate (a GPU not yet used by us must be free for 10 min). Ports and cores follow the GPU as in item 2. Runs, plans, seeds, analysis and verdict rules are unchanged; the analysis still runs once, after all five runners have a 'finished' line.
4. **Soak K1 restarted (operational, launch-script bug; 2026-11-06 17:07 UTC; no soak data analysed or inspected beyond liveness).** The first K1 started 16:57:52 on GPU2. At 17:04 the PI saw that experiments/v27/soak.sh resolved the stock server's systemd unit to the string "●". `systemctl list-units 'ap-vllm-g2-*'` also listed a stale *failed* record (ap-vllm-g2-1248725.scope, from Nov 5) first, with a bullet in column 1. So the monitor sampled the wrong scope for the stock server, which would have voided K-d, and K2's plugin scope would have resolved the same way. The PI stopped that K1 at 17:06 (its soak.sh, driver, proxy and server; nothing else). Its 7 minutes of output were moved unread to experiments/soak/out/aborted_K1_165752/ and are excluded. The PI fixed unit lookup to `--plain --state=active` plus a unit-name check that aborts on a bad name, ran `systemctl --user reset-failed` on the four stale failed ap-* records (ours, no processes), and restarted K1+K2 from the beginning on GPU2. The frozen driver and analysis (soak_drive.py e229d4e4, soak_analyze.py f4460929) are unchanged, as are the registered durations and gates.

## PREREG_v2.8_cli — deviations (none at freeze, 2026-11-06 17:30:46 UTC)
1. **Typo in the frozen header (pre-data, 17:30 UTC).** The document says 'Written 2026-11-06 ~17:45 UTC'. It was written 17:20–17:30 and frozen at 17:30:46 UTC (PROGRESS.md). The hand-typed time was wrong; the text is left unchanged because it is hashed.
2. **CLI bug fixed and run restarted (pre-data; 17:35 UTC).** The first attempt (17:30:53) failed before any generation. transcriptlab's `_interp()` resolved `--python /opt/envs/env_gemma/bin/python` through its venv symlink to /usr/bin/python3.12, which dropped the venv's packages, and run_injection.py died with ModuleNotFoundError: httpx. The analysis attempt found no gen.jsonl and wrote nothing. Fix: `Path(x).absolute()` instead of `.resolve()` in release/transcriptlab/src/transcriptlab/cli.py (new sha b600198853e5879a…; frozen measurement files untouched; `transcriptlab verify` 4/4). A regression test was added: tests/test_cli.py::test_interp_keeps_venv_symlink, 15/15 pass. The failed attempt's files went to experiments/transcriptlab_cli/run_v28_failed_1733/. experiments/v28/run_cli.sh, frozen at a5a913d9, was re-run unchanged. This is itself a practitioner finding: any user passing a venv interpreter would have hit it. It goes into the CHANGELOG and docs.

## PREREG_v2.9_gemma_coverage — deviations (none at freeze, 2026-11-06 17:56:22 UTC)

## PREREG_v2.10_audit_breadth — deviations (none at freeze, 2026-11-06 17:59:10 UTC)
5. **Analysis executed a second time (operational; 2026-11-06 19:10 UTC).** The registered run-once analysis ran at 18:36 UTC (PROGRESS.md). A Claude Code session restart (~18:15–19:07) lost the PI's working context, and at ~19:08 the PI ran analyze_v27_robustness.py (f68bc12d) again. The script is deterministic (fixed bootstrap seed 20261106, B = 2000, same inputs). The second output reproduces every verdict and number logged from the first run at 18:36: RT06 +18.7 [13.9, 23.8], removal 0.875 [0.75, 1.0]; RT00 +20.7 [16.0, 25.6], 0.92; D1 −7.7 [−11.4, −4.0], Holm p 5.8e-5; RSA 0.93 [0.84, 1.02]; RSB 0.86 [0.74, 0.96]. It overwrote the same file with identical content. No decision depended on the second run.
1. **unsloth bnb-4bit: 'NOT SERVABLE' is an environment limitation (19:36 UTC; no v2.10 audit number opened).** vLLM 0.19.1 in env_gemma raised ImportError: bitsandbytes>=0.48.1 is not installed. The checkpoint is not incompatible with vLLM or H100. bitsandbytes was NOT installed: env_gemma serves the running PREREG_E_ext servers, and changing it mid-campaign would risk their dependency set. The record stands as NOT SERVABLE, with the reason stated. An exploratory audit in a separate environment may follow after E_ext.
2. **unsloth NVFP4: NOT SERVABLE, error text not captured (19:37 UTC).** The server exited about 20 s after launch. Its log (logs/vllm/g6_8396.log) was overwritten by the next checkpoint's server before any error line was extracted, because run_audits.sh greps only for 'error|exception|not supported'. A diagnostic re-launch, operational only, will record the actual error after the v2.10 chain finishes. No audit number is involved.
   - Recaptured 19:54 UTC (diagnostic relaunch on GPU6 :8397, same flags): `ValueError: Unable to find matching target for model.layers.0.mlp.gate_up_proj in the compressed-tensors config` (vLLM compressed_tensors/utils.py find_matched_target). The checkpoint's quantization targets do not match vLLM 0.19.1's fused module names under the registered text-only override. It stays NOT SERVABLE; nothing patched.
6. **Registered descriptive quantity omitted by the frozen analysis (2026-11-06 20:48 UTC; after the outcomes were known; found by review R2, item M9).** PREREG_v2.7 §4 says: "Reported for every arm: the three rates (C1, RSA, RSB), the between-run SD, and the pooled 900-sample-per-arm estimate. Pooling is descriptive." analyze_v27_robustness.py (f68bc12d) reports the rates and the SD, but not the pooled estimate.
   - It was computed afterwards by experiments/contagion/scripts/v27_pooled_retest.py, using the frozen definitions copied verbatim (load, y, task-cluster bootstrap B = 2000, seed 20261106).
   - Output: experiments/contagion/out/confirmatory/v27_pooled_retest.json.
   - Pooled values: copying RD +19.1 pp [15.1, 23.3]; quarantine removal 0.924 [0.863, 0.983]; P0 0.9%, P1 20.0%, P6 9.8%, P8a 2.3% (900 per arm).

## PREREG_v2.11_masked_corpus — deviations (none at freeze, 2026-11-07 21:55:01 UTC)

## PREREG_v2.12_llama_family — deviations (none at freeze, 2026-11-08 00:14:11 UTC)

### PREREG_v2.11 deviation 1 (2026-11-08 04:09:31 UTC) — runner passed the corpus directory, not its manifest
- **What happened:** GPU4's gate opened 04:06:11. The frozen runner run_masked.sh started the QAT-ct server and at 04:08:21 called the released CLI with `--corpus release/package/pnc_v1.1_masked` (the directory). The CLI's `--corpus` takes the S1 manifest.json, as its help text says and as WP-pnc's validated dry run used. It raised IsADirectoryError in cmd_run before planning or generating anything. The resume pass, report and analysis then failed for lack of data, and the server was stopped.
- **Data:** 0 generations, no analysis output. The output dir (holding only ids.txt) was moved to experiments/transcriptlab_cli/discarded/run_v211_masked_failedstart_0408. No result was seen.
- **Fix:** run_masked_r2.sh (sha256 prefix 328aa8b8dd330dce) is identical except:
  - `--corpus <copy>/contexts/P-swebench-31b-S1-v1/manifest.json`, the path WP-pnc validated;
  - the GPU-free gate is 2 min instead of 10 min (the user's gate rule itself, < 2 GB and 0 apps, is unchanged).
- **Unchanged:** analysis script, verdict rule, server arguments, seeds and meta.
- **Pre-launch check:** a CLI dry run of the corrected arguments printed pool A1 with 300 states, 1,200 generations and frozen code 4/4, and its config reads the masked manifest and template.
- **Effect on v2.12:** its runner (waiting on v2.11's log line) was stopped while still waiting, before any GPU use. It is relaunched unchanged, chained after r2.
- **Release note (usability):** a user passing the dataset directory hits the same crash. Fix for the release: accept a directory (use <dir>/manifest.json) with a clear error otherwise; to be applied in the post-14:00 rebuild, with a test.

### PREREG_v2.12 deviation 1 (2026-11-08 05:25:21 UTC) — the released CLI 0.1.2 could not run a Llama-tokenizer hermes model; run with 0.1.3
- **What happened:** the run started 05:15:31 on GPU4. All 1,200 generations came back as server errors: vLLM rejected `stop_token_ids`, whose second entry was null.
  - Cause: X's frozen runner (run_ext.py) sets its stop ids to `<|im_end|>` and `<|endoftext|>`, Qwen's tokens. Hermes-3-Llama-3.1-8B's tokenizer has no `<|endoftext|>`.
  - The PI stopped the chain (05:17:30) after the first pass, before the resume pass, report and verdict, so no verdict was produced from error records.
  - The run dir was moved to experiments/transcriptlab_cli/discarded/run_v212_hermes3_cli012_allerrors_0517.
- **Why the pre-checks missed it:** they rendered prompts without a server; nothing exercised a request.
- **Diagnosis on the live server** (3-state pilots, 12 generations each, format inspected only; no rates computed; pilots kept in tmp/v212_pilots/). After the null stop id was fixed, two more Qwen-specific assumptions showed:
  - the rendered prompt already starts with `<|begin_of_text|>` and vLLM's default `add_special_tokens=true` added a second one (/tokenize: ids 128000, 128000);
  - Hermes-3 often ends its turn with `<|end_of_text|>` (128001), which was not a stop token, so it generated past its end.
- **Fix: transcriptlab 0.1.3.** The CLI bootstrap adds a request adapter for NEW models only:
  - stop ids = the model's end tokens (eos, `<|im_end|>`, `<|endoftext|>`, `<|end_of_text|>`, `<|eot_id|>` where present, plus generation_config eos ids); here [128001, 128009, 128040];
  - `add_special_tokens=false` when the prompt already starts with BOS.
  - The frozen runner is unchanged (16/16 pins). Registered models never take this path; the golden tests that reproduce the registered runs pass (21/21 tests).
  - The same release also lets `--corpus` take a directory (v2.11 deviation 1).
  - cli.py sha256 e5edb11c263fd2dbb4d4f70c9bee0ec2fda82863868148370e25d57365913c23.
- **Re-pilot with 0.1.3** (3 states): 12/12 well-formed generations stopping at the model's end tokens, 0 errors.
- **Runner:** run_llama_r2.sh (sha256 55af7961c94ef7ac84cf25bf34dbdf2ee9e1634b0dca73bd31a1213dda2ae73f), identical except no wait for v2.11 (done) and a 2-min GPU gate.
- **Unchanged:** model, revision, server arguments, arms, pool, seeds, analysis script, verdict rule.
- **Disclosure:** the leaderboard row will say it was run with CLI 0.1.3. The 0.1.2 failure is reported in the CHANGELOG and LIMITATIONS as a CLI generality bug found by this registration.

## PREREG_v2.11b_masked_replicate — deviations (none at freeze, 2026-11-08 05:38:41 UTC)

## PREREG_v2.13_llama3_hermes2pro — deviations (none at freeze, 2026-11-08 06:36:15 UTC)
### PREREG_v2.13 — NOT RUN (2026-11-08 07:08:09 UTC)
- **What happened:** vLLM refused to start Hermes-2-Pro-Llama-3-8B with the registered serve_vllm.sh defaults (max-model-len 32768). The model's max_position_embeddings is 8192 (Llama-3 base).
- **Why it cannot run:** the A1 states need up to ~18k prompt tokens with this tokenizer (Hermes-3 run: mean 10.9k, p95 15.1k, max 17.9k), plus up to 7,168 new tokens. Serving at 8k would truncate or reject almost every state. Extending the context by RoPE scaling would test a different model.
- The runner waited its 30 min and exited "server not ready" at 07:07:47. No generation was made and no verdict exists.
- **Lesson:** the pre-checks rendered prompts but did not compare their length with the model's context window.
- **CLI README:** now states the requirement (at least 32k tokens).
- The model (16 GB) will be deleted, and the deletion logged.

## PREREG_v2.14_bf16_cli — deviations (none at freeze, 2026-11-08 09:40:20 UTC)

## PREREG_v2.15_audit_predicts_copying — deviations (none at freeze, 2026-11-08 09:45:44 UTC)

## PREREG_v2.16_qat_weights — deviations (none at freeze, 2026-11-08 11:20:41 UTC)
### PREREG_v2.16 deviation 1 (2026-11-08 11:51:30 UTC) — placement only: qatunq started on GPUs 0+3 instead of waiting for GPUs 0+1
- **Why:** the E_audit nvidia NVFP4 lanes on GPUs 1 and 2 run slower than estimated (≈ 30/58 tasks after 1 h), so the registered trigger ("dispatcher (slots 0 1 2) done") would come at ~13:05. GPUs 0 and 3 have been free since LAST_START 11:30: their dispatcher slots reported "no lanes left", and slot 3's dispatcher is done.
- **What:** experiments/v216/run16.sh, unchanged, run by hand as `run16.sh qatunq 0+3 8387 108-109`. It uses the same port, server arguments, CLI arguments and output directory as the registered placement, and passes the user's gate on both GPUs.
- **The driver's own qatunq pass:** it still runs later on GPUs 0+1. It finds the complete run (CLI resume: nothing to do) and re-runs `report`. The analysis still runs once, after all branches end.
- **Unchanged:** analysis, verdict rules and data.
