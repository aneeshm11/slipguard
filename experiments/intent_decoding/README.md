# Workstream B — Intent-preserving decoding for Gemma-4 tool calls

Directory: `experiments/intent_decoding` · numbers: `results.json` · log: `progress.md`

## TL;DR (discovery set = main-track logs, Gemma-only, the June template that produced them; Wilson 95% CIs)
Discovery prompts are 1 token shorter than the logged prompts (one space; §3.1). The live proxy run on log-exact
prompts gives the same baseline (16.6% vs 16.5%).
- **Gate PASS, 31B-QAT, thinking ON.** 600 first-edit contexts gave 595 calls.
  - Closer slips: 104/595 = 17.5% [14.6, 20.7], which matches the logged Gemma-only onset of 17.1%. After IPD: 0.
  - Census-malformed: 18.7% → **1.2%** with IPD, a paired relative reduction of **93.7% [87.6, 96.9]**.
  - 0/480 valid calls were altered (upper bound 0.79%).
- **Gate PASS, thinking OFF.** 300 contexts × 2: census-malformed 21.0% → 0.85%, i.e. **95.9% [90.8, 98.3]**; 0/463
  valid calls altered.
- **Model-free.** 229,414 quote/backtick-rich VALID calls (gold-patch hunks plus adversarial literals) were changed
  **0** times (upper bound 0.0017%). Text-only splitters fire on up to 66.5% of the adversarial calls.
- **Head-to-head on the 104 slips** (clean / loud / delivered-malformed / silent corruption):

  | decoder | clean | loud | delivered-malformed | silent |
  |---|---|---|---|---|
  | IPD | 102 | 2 | 0 | 0 |
  | T1 text-only | 101 | 3 | 0 | 0 |
  | (ii) τ=2 | 100 | 4 | 0 | 0 |
  | retry ×2 | 25 | 79 | 0 | 0 |
  | greedy | 16 | 0 | 87 | 1 |
  | forbid-trigger (both variants) | 0 | 0 | 103 | 1 |
  | grammar-constrained | 3 | 0 | 103 | **101** |

  Retry with a lenient fallback delivers malformed calls 83/595 times, against 0/595 for IPD.
  - T1 text-only **ties** IPD on clean delivery (101 vs 102). It loses on exact intent: −3.3 pp on the gold set below.
  - IPD's distinct value is the byte-identity guarantee, abstention, composite closers with opener drift, and zero
    silent corruption.
- **Gold intent, 519 natural slips with known intent.** Intent comes from the model's own later clean retry.
  G1 = 229 logged base-31B slips replayed from the exact logged prefix; G1R = 290 natural slips re-sampled (k = 4)
  at the first 105 of the same states. 229 states in all.
  - IPD exact intent **507/519 = 97.7% [96.0, 98.7]** (state-cluster bootstrap [95.2, 99.6]): G1 227/229 = 99.1%,
    G1R 280/290 = 96.6%.
  - (ii) τ=2 97.1%, a tie with IPD (IPD − (ii) = +0.6 pp [−0.8, +2.4]). (i)-max 95.2%.
  - T1 94.4%; IPD − T1 = **+3.3 pp [+0.8, +6.1]**. T1 fails on composite closers. On G1 it is scored on an
    assumed tail, because the real tail was lost at serving time.
  - Retry ×2 12.3%; greedy 7.9%; forbid-trigger 0%; grammar-CD 0% (silent corruption on 229/229 G1 and 288/290 G1R).
  - False repairs on the 127 G1R samples that closed correctly: 0 for IPD and 0 for T1.
- **E4B** fails differently (mostly opener and kwarg drift). IPD cuts census-malformed by 81.6% [68.6, 90.0] with thinking ON
  (49 → 9 of 1,195) and by 61.4% [46.6, 74.3] with thinking OFF (44 → 17 of 1,196); 0 valid calls altered.
- **A2 service.** 300 MAP repairs were delivered (`out/a2_map_repairs.jsonl`): 282 repaired, 18 abstain.
- **The shipped proxy now behaves like the reference decoder (§8).**
  - Two pre-fix findings went to workstream E:
    - F1: slips written with a space after the comma were missed (1/104 gate; 1.6% of corpus slips).
    - F2: the proxy had no byte identity on adversarial valid calls: 278/1,200 = 23.2% were altered.
  - E's post-fix proxy is verify-then-repair on B's vendored library. On identical generations it agrees with B on
    104/104 slip cuts and changes 0/229,412 valid calls (0/1,200 adversarial).
  - On the 229 gold states it gets 227/229 exact intent, the same as B, with 0 discordant states.
  - Live on the 600 gate contexts, delivered malformed first edits fall from 67/600 to 1/600, a relative reduction of
    98.5% [95, 100]. The remaining difference is policy: a residual invalid call is delivered by the proxy and fails
    loud in B.
- **"Just add an exemplar" is not a fix (arm 11). It has a copying side effect.** One clean `edit_file` exemplar
  (`NOTES.md`; its `new_string` ends in a backtick) was inserted into the history.
  - Slip onset falls with thinking ON: 17.5% → 11.1% over 588 paired contexts, **−6.5 pp [−9.7, −3.4]**. On
    natural (unforced) calls alone it falls 16.0% → 9.5%, −6.6 pp [−10.3, −2.9] (349 contexts).
  - With thinking OFF it falls 19.9% → 15.6%, −4.3 pp [−8.5, −0.5] (299 contexts). On natural calls alone the change
    is −4.9 pp [−9.7, +0.0].
  - But the model **copies the exemplar**. When an edit is forced, **56/184 forced edits (30%) edit the exemplar's own
    file `NOTES.md`**, extending its note verbatim, instead of doing the task. With thinking OFF it is 42/151 (28%).
    No natural edit does this (0/408 ON, 0/439 OFF).
  - This fits the copy-from-history behaviour in workstream A's contagion study. An exemplar lowers onset only
    partially and adds a task-hijacking failure. IPD needs no change to the context.
- **The July template is not a fix either (arm 12).** Slip onset vs June, paired by context: thinking ON
  +2.9 pp [−0.3, +6.1] (588 contexts); thinking OFF +0.2 pp [−2.0, +2.3] (298 contexts).
- **Confirmatory run (PREREG_v2 §3.2) on workstream P's fresh public corpus, frozen `confirm/` package (§7.1).**
  S1 B1 has 600 states, run at P's T = 1.0.
  - C12: first-edit onset is only **2.2% [1.3, 3.7]**, LOWER than predicted (14% [6, 26]).
  - C13: IPD reduction **92.3% [66.7, 98.6] → REPLICATES** (13 → 1; verified-only 85.7% [48.7, 97.4] → ATTENUATED).
  - C14: **0/582 valid calls changed → REPLICATES**.
  - C15: IPD and T1 13/13 clean → REPLICATE. Retry ×2 FAILS (11/13 clean). Greedy FAILS (5/13 malformed). Grammar-CD
    ATTENUATED (10/13 silent).
  - C16: NOT_ESTIMABLE (0 eligible logged slips).
  - S2: 0 closer slips; its 4 malformed calls are other failure types, which IPD leaves alone and fails loud.

## 1. Problem
Gemma 4 writes tool calls as `<|tool_call>call:NAME{key:<|"|>value<|"|>,...}<tool_call|>`. Strings are delimited by
a single special token `<|"|>` and have **no escaping**. The chat template dict-sorts the parameters, so the model
writes `new_string` before `old_string`. It then often closes `new_string` with a **look-alike closer** instead of
`<|"|>` and immediately writes the next argument: `` `,old_string:<|"|>... ``. The closer is a backtick in 83% of
base-31B slips in the main-track logs, a quote variant in about 14%.

vLLM 0.19.1's lenient parser then silently **swallows the next argument**: the call parses with `old_string`
missing, and the template re-renders the corrupted call into history.

- In an escape-free format, a slip closer and literal content are **textually indistinguishable**. For example,
  `x = "a"` closed with `` ` `` and `x = "a` closed with `` "` `` emit the same bytes. So no text-only parser can
  recover the intent with certainty.
- The model's own distribution **can** recover it.

## 2. Method (model-agnostic, client-side, any OpenAI-compatible `/v1/completions` server, no engine change)

### 2.1 Reference grammar, guard and slip sites — `gemma_protocol.py`
- `parse_strict` is a strict parser for the call grammar (strings, nested objects and arrays, bare
  true/false/null/numbers, whitespace between structural tokens).
- `is_valid` = strict parse + schema check (declared tool, declared keys, no duplicates, required keys present,
  value types). **This is the guard: a strictly valid call is never altered.**
- A **slip site** is a maximal look-alike run `L` over the characters `` ` " ' \ `` (possibly empty) inside a
  top-level `<|"|>`-opened string, IMMEDIATELY followed by protocol structure. Two forms qualify:
  - `[ws] , [ws] KEY [ws] :` where KEY is declared for the tool, not yet emitted, not the current key, and the
    text after `:` opens a value of KEY's type. For a string-typed KEY, this opener must be exactly the strict
    closer of the current string.
  - `[ws] } <end>`, for the last argument of a finished call.
- The cut candidates are every position inside `L` plus the whitespace gap: content keeps `L[:k]`, and the
  closer is `L[k:]`.
- `repair_candidates` enumerates all complete parses of the relaxed grammar, in which a string may be closed by a
  look-alike run at a slip site. It keeps the schema-valid ones of minimal cost (cost = number of slips).
- `first_slip_site` returns the earliest cut among the minimal parses, falling back to the left-most locally
  inconsistent string.
- An extension, `first_opener_site`, flags a declared string argument whose value does not start with `<|"|>`.
  These are JSON/Python-style drifts such as `filepath: "x.py"`.

### 2.2 Algorithm (i): slip rollback / resume (decode time) — `intent_decode.rollback_resume`
1. Generate the call. **If it is strictly valid, return it byte-identical.**
2. Otherwise, take the first slip site and score every cut `k` with the **noisy-channel rule**:
   `score(k) = log P_model(L[:k] <|"|> <structural continuation> | context, call prefix) + log P_channel(L[k:])`.
   - The structural continuation is `,KEY:<|"|>` or `}<tool_call|>`.
   - The model term is exact. One cached `max_tokens=1` request is sent per scored token, with the token forced
     by `allowed_token_ids`. vLLM 0.19.1 computes raw logprobs **before** logits processors (`v1/sample/sampler.py`),
     so the forced token's logprob is the exact model logprob at any rank.
   - `P_channel` is the closer prior: how often the model writes a given look-alike run in place of `<|"|>`. It is
     estimated by add-½ smoothing from the 505 edit slips of the team's fine-tuned models, which is disjoint from
     the base-31B logs.
3. Truncate at the chosen cut, append the true delimiter `<|"|>`, and **resume generation** (one request).
4. Repeat up to 4 rounds.

Cost per intervention is the cut-scoring requests (cached, ~0–15 tokens each) plus one resumed generation.
Variant `max` cuts before the whole run (no model query). Variant (i+) also applies the opener rule.

### 2.3 Algorithm (ii): likelihood-scored repair (post hoc, text only) — `intent_decode.lik_repair`
1. Enumerate the minimal relaxed parses.
2. Re-render each canonically.
3. Score each candidate with **windowed cached teacher forcing (WCTF)**:
   - the exact log-likelihood of the tokens where candidates differ, plus K=12 tokens into their shared suffix,
     conditioned on the full context;
   - plus `log P_channel` of its closers.
4. Repair to the argmax if its margin over the runner-up is at least τ; otherwise **abstain** and fail loudly.
5. The guard applies first: valid calls are returned unchanged.

`prompt_logprobs` is **never** used on prompts over 1,024 tokens. vLLM 0.19.1 materialises an fp32
[chunk × 262k vocab] log_softmax for prompt logprobs, and doing so on a 16k-token prompt crashed a shared server.
The cap is hard-coded in `Server.complete`.

### 2.4 Guarantees
- **P1 (identity on valid calls).**
  - Claim: for every text `t`, if `is_valid(t)` then `(i)(t) = t` and `(ii)(t) = t`, byte-identical.
  - Proof: both procedures test `is_valid` first. `first_violation` and `repair_candidates` return
    nothing / [] for valid `t`.
  - Tests:
    - 20,000 random adversarial valid calls (`tests/test_protocol.py`);
    - all QuoteStorm valid calls (§4.2);
    - every valid call in the real-context replays (§4.1).
- **P2 (locality).**
  - Claim: (i) changes `t` only at a slip site. The bytes before the cut are preserved, and only the suffix is
    regenerated by the same model under the same sampling parameters.
  - Proof: by construction.
- **P3 (completeness for single slips).**
  - Claim: suppose `c` is valid and `t` is obtained from `c` by replacing the closing delimiter of one top-level
    string argument with any look-alike run (an end slip if it is the last argument). If `t` is invalid, then `c`
    is among the minimal candidates `repair_candidates(t)`.
  - Proof sketch: the minimal cost is 1; `c`'s reading has cost 1 and is recognised as a slip site, because the
    next key is declared and not yet emitted, and its opener `<|"|>` is the first delimiter after the run.
  - Tests:
    - 5,000 random property tests: 0 misses;
    - the synthetic QuoteStorm slips: 100% coverage (§4.2).
- **P4 (delimiter ambiguity).**
  - Claim: there exist `c1 ≠ c2` and closers `L1, L2` with `slip(c1, L1) = slip(c2, L2)`.
  - Example: `x = "a"` + `` ` `` versus `x = "a` + `` "` ``.
  - Consequence: no text-only rule is correct on both. Under the generative model
    `P(c | ctx) · P_channel(y | c)`, the Bayes decision is the argmax that (ii) computes. Its two inputs are the
    model likelihood (WCTF) and the closer prior.

### 2.5 Engineering notes
- **Model-agnostic and engine-free.** The method uses only `/v1/completions` with `skip_special_tokens=false`,
  token-id prompts, `logprobs`, `allowed_token_ids` (a vLLM extension; any server that returns the forced token's
  logprob works) and `return_tokens_as_token_ids`.
- **Prefix pinning (`intent_decode.Pin`).**
  - While all arms of a sample run, a streaming request on the same prefix keeps its KV blocks in use. vLLM v1 shares
    computed blocks of running requests; the stream is closed when the arms are done.
  - On the shared 31B server this raised the prefix-cache hit rate from 36% to 75–97%.
  - It cut the amortized extra latency per edit call from about 25 s to about 1.2 s.
- **No `prompt_logprobs` on long prompts.** `Server.complete` refuses them above 1,024 tokens, after a 16k-token
  request OOM-crashed a shared server.
- **Bounded enumeration.**
  - Cut positions per site: the whole look-alike run plus the last 7 boundaries.
  - The relaxed-grammar search has a 20k-step budget. When it is exhausted the result is marked incomplete:
    (ii) abstains and (i) falls back to the left-to-right scan.
  - Reason: a pathological E4B output had exploded the search (17.8 GB, event loop blocked).
- **Drop-in API.** `intent_decode.generate_call(srv, tok, prompt_text, schema, prior=...)`.
- **A2 service.** `map_repair.py` produces MAP repairs of logged natural slips (noisy-channel cut + greedy resume).

## 3. Experiments (P0-B: Gemma-only contexts, decoder head-to-head, gold intent)

### 3.1 Data validity fixes (2026-11-04)
1. **Teacher contexts excluded.**
   - Runs `t1_qwen`, `t2_qwen_rebench`, `t3_qwen_rebench` and `dsprobe` served Qwen/DeepSeek *teacher* models under
     the Gemma alias.
   - Their 546 contexts are removed (records in `out/old_v1/teacher_records_*`).
   - The replay set is `data/replay_gemma_first_edit.jsonl`: 954 Gemma-only first-edit states. The first 600 cover
     396 tasks, ≤12 per task.
   - Logged Gemma-only first-edit malformation is 17.1%; the earlier 10.8% was diluted by teacher runs and is
     withdrawn.
2. **Log-faithful template.**
   - The main-track logs were produced with the **June-5** chat template.
   - The current HF template (**July 2026-07-09**) differs in two ways relevant here: it closes the model turn before
     the harness's "Please continue" user messages, and it forces `<|channel>thought\n` after tool responses when
     thinking is on.
   - The primary arms use June (`replay_utils.render_prompt(..., 'june')`). July is arm 12.
   - **Caveat (found 2026-11-04 18:45 UTC, during the proxy-equivalence check).** The discovery replays passed the
     system message content as a plain string. vLLM, and E's proxy, pass it as a list of text parts, and the template
     then emits one extra space before the `<|tool>` declarations. So every discovery replay prompt is **1 token
     shorter** than the logged prompt. That space is the only difference: E's proxy render matches the logged prompt
     length on 600/600 gate contexts, B's render on 0/600. The effect on onset is expected to be nil (gate onset 17.5%
     vs logged 17.1%), and the live proxy base arm (§8) measures it directly. The frozen confirmatory runner renders
     system content as parts and verifies `prompt_tokens`, so the confirmatory set is not affected.
   - E4B has no June template, so it uses its own shipped template.

### 3.2 Arms (paired on identical samples)
| # | decoder / policy | how it is run |
|---|---|---|
| 1 | lenient (status quo) | vLLM 0.19.1 `gemma4` parser on the emitted call |
| 2 | strict fail-loud | deliver only strictly valid calls, otherwise a loud error |
| 3 | T1 text-only longest-closer | model-free: cut every slip site before the whole look-alike run, if that yields a complete schema-valid parse |
| 4 | (i)-max | rollback/resume with the whole-run cut |
| 5 | **IPD (i+)** | rollback + noisy-channel cut + resume + opener rule; residual invalid → loud |
| 6 | (ii) τ = 2 | post-hoc WCTF likelihood + closer prior; abstain (loud) if the margin is < 2 nats |
| 7 | retry-on-invalid ×2 | resample the whole call at T = 0.2 (the replay T) |
| 8 | greedy | re-decode the call at T = 0 |
| 9 | forbid-trigger | exact emulation of a streaming logits rule: right after `<look-alike>,` inside a string, every token that can begin a declared `edit_file` key is banned for one step (`logit_bias −100`); repeated (≤4) |
| 9b | forbid-trigger, strict | as 9, but the ban sits where the key would start, after any whitespace, so a newline cannot sidestep it (≤6) |
| 10 | grammar-constrained | exact emulation: walk the schema grammar (`<|"|>` is the only closer; declared, non-duplicate keys; required keys before `}`; typed values), cut at the longest viable prefix, force the grammar's legal continuation, continue freely; repeated (≤6) |
| 11 | exemplar immunization | one synthetic CLEAN `edit_file` exchange (call + `ok` response; `new_string` ends with a backtick) inserted after the first user message; new samples on the same contexts |
| 12 | July template | the same contexts rendered with the July template; new samples |

Arms 1–10 act on the same baseline sample. 7–10 run inline, while the sample's prefix is pinned (`arms.py`). 11–12
are onset arms with their own samples, paired by context.

**Metrics.**
- *delivered-malformed*: the census criterion on what reaches the harness.
- *loud*: nothing delivered.
- *silent corruption*: delivered and accepted by the runtime (required keys, no unknown keys) but strictly invalid
  or carrying `<look-alike>,<declared key>:` text.
- *clean*: strictly valid and no leak.
- On gold sets, also:
  - *exact intent*: (filepath, old_string, new_string) equal to the gold;
  - *edit-applies*: `old_string` occurs exactly once in the pre-patch file;
  - *edit-correct*: applying the delivered edit yields the same file as the gold edit.

### 3.3 Experiments
| id | what | script → output |
|---|---|---|
| E1 | First-edit replays: 600 Gemma-only contexts with thinking ON (k = 1) and 300 with thinking OFF (k = 2), 31B-QAT, June template, T = 0.2 / top-p 0.95. The model's natural tool choice is used; if it is not `edit_file`, an `edit_file` call is forced in the same state (reported separately, together with the unforced natural-next-call analysis). E4B: 600 contexts × 2 for each of ON and OFF. | `replay.py` → `out/v3_r31_{on,off}_june.jsonl`, `out/v2_re4_{on,off}.jsonl` |
| E1-h2h | Arms 1–10 on the E1 samples | inline (`rec['h2h']`), `head2head_gen.py` → `out/h2h_*.jsonl` |
| E1-onset | Arms 11/12 | `replay.py --exemplar` → `out/v4_*_exm.jsonl`; `--template july` → `out/v2_r31_*_july.jsonl` |
| G1 | Gold: **real logged slips with retry-derived intent**. Workstream C's corpus has 279 records; 229 are base-31B (50 fine-tune records excluded). Each is replayed from the exact logged prefix: June template, logged thought, byte-exact raw call prefix up to the swallowing delimiter. T1/(ii) are scored on an explicitly assumed tail, because the real tail was lost at serving time. | `rs279.py` → `out/rs279_31b.jsonl` |
| G2 | Gold: **copy task**. 646 competition-snapshot hunks whose old block is unique in the real pre-patch file (edit-applies is checkable), plus 3,052 QuoteStorm payloads. 31B pilots: thinking OFF at T 0.7 and 0.2. E4B pilot: OFF at T 0.7. | `build_gold_copy.py`, `replay.py` → `out/gc_*.jsonl` |
| E2 | QuoteStorm model-free: 114,107 unique quote/backtick-rich gold-patch hunks plus 600 adversarial literals, × 2 key orders, as VALID calls → false repairs and text-only baselines | `quotestorm_free_big.py` → `out/quotestorm_free_big.json` |
| E3 | Synthetic slips with known intent, model-scored (E4B, `copy` context, n = 2,000) | `quotestorm_model.py` → `out/v2_qsm_e4b_copy.jsonl` |

## 4. Results (generated from results.json by render_results_md.py)

### 4.1 Data fix

- Teacher runs excluded: t1_qwen, t2_qwen_rebench, t3_qwen_rebench, dsprobe. 546 replay contexts removed; 954 Gemma-only contexts remain.
- Logged first-edit malformation, Gemma-only: **472/2753 = 17.1% [15.8, 18.6]**. At T=0.2 it is 215/1550; at T=0.7 it is 257/1203. The teacher runs have 0/1,620. The figure 10.8% (diluted by teacher runs) is withdrawn.

### 4.2 E1: first-edit replays, paired, Wilson 95% CIs

| replay | subset | contexts / edit calls (forced) | baseline census-malformed | after (i) | after IPD (i+) | after (ii) | rel. red. census, IPD | closer slips base→(i) | rel. red. slips (i) | valid calls changed (i)/(i+)/(ii) |
|---|---|---|---|---|---|---|---|---|---|---|
| v3_r31_on_june | all | 595 / 595 (189) | 111/595 = 18.7% [15.7, 22.0] | 8/595 = 1.3% [0.7, 2.6] | 7/595 = 1.2% [0.6, 2.4] | 11/595 = 1.8% [1.0, 3.3] | **93.7%** [87.6, 96.9] (n=111) | 104 → 0 | **100.0%** [96.4, 100.0] (n=104) | 0/0/0 of 480 |
| v3_r31_on_june | natural | 406 / 406 (0) | 67/406 = 16.5% [13.2, 20.4] | 5/406 = 1.2% [0.5, 2.9] | 4/406 = 1.0% [0.4, 2.5] | 6/406 = 1.5% [0.7, 3.2] | **94.0%** [85.6, 97.7] (n=67) | 63 → 0 | **100.0%** [94.3, 100.0] (n=63) | 0/0/0 of 336 |
| v3_r31_on_june | forced | 189 / 189 (189) | 44/189 = 23.3% [17.8, 29.8] | 3/189 = 1.6% [0.5, 4.6] | 3/189 = 1.6% [0.5, 4.6] | 5/189 = 2.6% [1.1, 6.0] | **93.2%** [81.8, 97.7] (n=44) | 41 → 0 | **100.0%** [91.4, 100.0] (n=41) | 0/0/0 of 144 |
| v3_r31_off_june | all | 299 / 587 (152) | 123/587 = 21.0% [17.9, 24.4] | 7/587 = 1.2% [0.6, 2.4] | 5/587 = 0.9% [0.4, 2.0] | 11/587 = 1.9% [1.0, 3.3] | **95.9%** [90.8, 98.3] (n=123) | 118 → 0 | **100.0%** [96.8, 100.0] (n=118) | 0/0/0 of 463 |
| v3_r31_off_june | natural | 252 / 435 (0) | 87/435 = 20.0% [16.5, 24.0] | 5/435 = 1.1% [0.5, 2.7] | 3/435 = 0.7% [0.2, 2.0] | 8/435 = 1.8% [0.9, 3.6] | **96.6%** [90.3, 98.8] (n=87) | 83 → 0 | **100.0%** [95.6, 100.0] (n=83) | 0/0/0 of 349 |
| v3_r31_off_june | forced | 110 / 152 (152) | 36/152 = 23.7% [17.6, 31.0] | 2/152 = 1.3% [0.4, 4.7] | 2/152 = 1.3% [0.4, 4.7] | 3/152 = 2.0% [0.7, 5.6] | **94.4%** [81.9, 98.5] (n=36) | 35 → 0 | **100.0%** [90.1, 100.0] (n=35) | 0/0/0 of 114 |
| v4_r31_on_june_exm | all | 592 / 592 (184) | 66/592 = 11.1% [8.9, 13.9] | 4/592 = 0.7% [0.3, 1.7] | 4/592 = 0.7% [0.3, 1.7] | n/a ((ii) not run on 61 invalid calls) | **93.9%** [85.4, 97.6] (n=66) | 65 → 0 | **100.0%** [94.4, 100.0] (n=65) | 0/0/n/a of 521 |
| v4_r31_on_june_exm | natural | 408 / 408 (0) | 45/408 = 11.0% [8.3, 14.4] | 3/408 = 0.7% [0.3, 2.1] | 3/408 = 0.7% [0.3, 2.1] | n/a ((ii) not run on 42 invalid calls) | **93.3%** [82.1, 97.7] (n=45) | 44 → 0 | **100.0%** [92.0, 100.0] (n=44) | 0/0/n/a of 361 |
| v4_r31_on_june_exm | forced | 184 / 184 (184) | 21/184 = 11.4% [7.6, 16.8] | 1/184 = 0.5% [0.1, 3.0] | 1/184 = 0.5% [0.1, 3.0] | n/a ((ii) not run on 19 invalid calls) | **95.2%** [77.3, 99.2] (n=21) | 21 → 0 | **100.0%** [84.5, 100.0] (n=21) | 0/0/n/a of 160 |
| v4_r31_off_june_exm | all | 299 / 590 (151) | 94/590 = 15.9% [13.2, 19.1] | 4/590 = 0.7% [0.3, 1.7] | 4/590 = 0.7% [0.3, 1.7] | n/a ((ii) not run on 95 invalid calls) | **95.7%** [89.6, 98.3] (n=94) | 93 → 0 | **100.0%** [96.0, 100.0] (n=93) | 0/0/n/a of 492 |
| v4_r31_off_june_exm | natural | 253 / 439 (0) | 67/439 = 15.3% [12.2, 18.9] | 2/439 = 0.5% [0.1, 1.6] | 2/439 = 0.5% [0.1, 1.6] | n/a ((ii) not run on 65 invalid calls) | **97.0%** [89.8, 99.2] (n=67) | 65 → 0 | **100.0%** [94.4, 100.0] (n=65) | 0/0/n/a of 371 |
| v4_r31_off_june_exm | forced | 106 / 151 (151) | 27/151 = 17.9% [12.6, 24.8] | 2/151 = 1.3% [0.4, 4.7] | 2/151 = 1.3% [0.4, 4.7] | n/a ((ii) not run on 30 invalid calls) | **92.6%** [76.6, 97.9] (n=27) | 28 → 0 | **100.0%** [87.9, 100.0] (n=28) | 0/0/n/a of 121 |
| v2_r31_on_july | all | 592 / 592 (193) | 125/592 = 21.1% [18.0, 24.6] | 7/592 = 1.2% [0.6, 2.4] | 6/592 = 1.0% [0.5, 2.2] | 12/592 = 2.0% [1.2, 3.5] | **95.2%** [89.9, 97.8] (n=125) | 121 → 0 | **100.0%** [96.9, 100.0] (n=121) | 0/0/0 of 463 |
| v2_r31_on_july | natural | 399 / 399 (0) | 73/399 = 18.3% [14.8, 22.4] | 2/399 = 0.5% [0.1, 1.8] | 2/399 = 0.5% [0.1, 1.8] | 4/399 = 1.0% [0.4, 2.5] | **97.3%** [90.5, 99.2] (n=73) | 74 → 0 | **100.0%** [95.1, 100.0] (n=74) | 0/0/0 of 324 |
| v2_r31_on_july | forced | 193 / 193 (193) | 52/193 = 26.9% [21.2, 33.6] | 5/193 = 2.6% [1.1, 5.9] | 4/193 = 2.1% [0.8, 5.2] | 8/193 = 4.1% [2.1, 8.0] | **92.3%** [81.8, 97.0] (n=52) | 47 → 0 | **100.0%** [92.4, 100.0] (n=47) | 0/0/0 of 139 |
| v2_r31_off_july | all | 299 / 588 (154) | 125/588 = 21.3% [18.1, 24.7] | 6/588 = 1.0% [0.5, 2.2] | 4/588 = 0.7% [0.3, 1.7] | n/a ((ii) not run on 95 invalid calls) | **96.8%** [92.1, 98.7] (n=125) | 120 → 0 | **100.0%** [96.9, 100.0] (n=120) | 0/0/n/a of 459 |
| v2_r31_off_july | natural | 252 / 434 (0) | 85/434 = 19.6% [16.1, 23.6] | 5/434 = 1.2% [0.5, 2.7] | 3/434 = 0.7% [0.2, 2.0] | n/a ((ii) not run on 62 invalid calls) | **96.5%** [90.1, 98.8] (n=85) | 80 → 0 | **100.0%** [95.4, 100.0] (n=80) | 0/0/n/a of 348 |
| v2_r31_off_july | forced | 112 / 154 (154) | 40/154 = 26.0% [19.7, 33.4] | 1/154 = 0.6% [0.1, 3.6] | 1/154 = 0.6% [0.1, 3.6] | n/a ((ii) not run on 33 invalid calls) | **97.5%** [87.1, 99.6] (n=40) | 40 → 0 | **100.0%** [91.2, 100.0] (n=40) | 0/0/n/a of 111 |
| v2_re4_on | all | 600 / 1195 (159) | 49/1195 = 4.1% [3.1, 5.4] | 45/1195 = 3.8% [2.8, 5.0] | 9/1195 = 0.8% [0.4, 1.4] | 45/1195 = 3.8% [2.8, 5.0] | **81.6%** [68.6, 90.0] (n=49) | 5 → 0 | **100.0%** [56.6, 100.0] (n=5) | 0/0/0 of 1139 |
| v2_re4_on | natural | 555 / 1036 (0) | 35/1036 = 3.4% [2.4, 4.7] | 32/1036 = 3.1% [2.2, 4.3] | 8/1036 = 0.8% [0.4, 1.5] | 32/1036 = 3.1% [2.2, 4.3] | **77.1%** [61.0, 87.9] (n=35) | 4 → 0 | **100.0%** [51.0, 100.0] (n=4) | 0/0/0 of 998 |
| v2_re4_on | forced | 117 / 159 (159) | 14/159 = 8.8% [5.3, 14.2] | 13/159 = 8.2% [4.8, 13.5] | 1/159 = 0.6% [0.1, 3.5] | 13/159 = 8.2% [4.8, 13.5] | **92.9%** [68.5, 98.7] (n=14) | 1 → 0 | **100.0%** [20.7, 100.0] (n=1) | 0/0/0 of 141 |
| v2_re4_off | all | 599 / 1196 (122) | 44/1196 = 3.7% [2.8, 4.9] | 35/1196 = 2.9% [2.1, 4.0] | 17/1196 = 1.4% [0.9, 2.3] | 37/1196 = 3.1% [2.3, 4.2] | **61.4%** [46.6, 74.3] (n=44) | 14 → 0 | **100.0%** [78.5, 100.0] (n=14) | 0/0/0 of 1146 |
| v2_re4_off | natural | 566 / 1074 (0) | 32/1074 = 3.0% [2.1, 4.2] | 25/1074 = 2.3% [1.6, 3.4] | 10/1074 = 0.9% [0.5, 1.7] | 26/1074 = 2.4% [1.7, 3.5] | **68.8%** [51.4, 82.0] (n=32) | 10 → 0 | **100.0%** [72.2, 100.0] (n=10) | 0/0/0 of 1037 |
| v2_re4_off | forced | 90 / 122 (122) | 12/122 = 9.8% [5.7, 16.4] | 10/122 = 8.2% [4.5, 14.4] | 7/122 = 5.7% [2.8, 11.4] | 11/122 = 9.0% [5.1, 15.4] | **41.7%** [19.3, 68.0] (n=12) | 4 → 0 | **100.0%** [51.0, 100.0] (n=4) | 0/0/0 of 109 |

**Unforced: the natural next call, with no forcing.**

| replay | natural calls | tool distribution | census-malformed (any tool) | edit_file malformed | forced-edit share |
|---|---|---|---|---|---|
| v3_r31_on_june | 595 | edit_file:406, run_command:117, read_file:57, write_file:10, get_status:2 | 71/595 = 11.9% [9.6, 14.8] | 67/406 | 189/595 |
| v3_r31_off_june | 587 | edit_file:435, run_command:92, read_file:47, call edit_file:6, write_file:4 | 93/587 = 15.8% [13.1, 19.0] | 87/435 | 152/587 |
| v4_r31_on_june_exm | 592 | edit_file:408, run_command:103, read_file:63, write_file:7, submit_patch:6 | 48/592 = 8.1% [6.2, 10.6] | 45/408 | 184/592 |
| v4_r31_off_june_exm | 590 | edit_file:439, run_command:94, read_file:46, call edit_file:5, submit_patch:4 | 72/590 = 12.2% [9.8, 15.1] | 67/439 | 151/590 |
| v2_r31_on_july | 592 | edit_file:399, run_command:106, read_file:65, write_file:11, get_status:5 | 76/592 = 12.8% [10.4, 15.8] | 73/399 | 193/592 |
| v2_r31_off_july | 588 | edit_file:434, run_command:94, read_file:44, call edit_file:7, write_file:4 | 92/588 = 15.6% [12.9, 18.8] | 85/434 | 154/588 |
| v2_re4_on | 1195 | edit_file:1036, read_file:123, run_command:24, write_file:5, submit_patch:4 | 37/1195 = 3.1% [2.3, 4.2] | 35/1036 | 159/1195 |
| v2_re4_off | 1196 | edit_file:1074, read_file:88, run_command:27, write_file:5, submit_patch:2 | 33/1196 = 2.8% [2.0, 3.8] | 32/1074 | 122/1196 |

### 4.3 Decoder head-to-head on identical samples

**v3_r31_on_june [all]**: samples=595, contexts=595, slips=104, forced=189.

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 111/595 = 18.7% [15.7, 22.0] | 4/595 = 0.7% [0.3, 1.7] | 0/595 = 0.0% [0.0, 0.6] | 480/595 = 80.7% [77.3, 83.6] |
| 2_fail_loud | 0/595 = 0.0% [0.0, 0.6] | 0/595 = 0.0% [0.0, 0.6] | 115/595 = 19.3% [16.4, 22.7] | 480/595 = 80.7% [77.3, 83.6] |
| 3_T1_text_only | 0/595 = 0.0% [0.0, 0.6] | 0/595 = 0.0% [0.0, 0.6] | 14/595 = 2.4% [1.4, 3.9] | 581/595 = 97.6% [96.1, 98.6] |
| 4_i_max | 0/595 = 0.0% [0.0, 0.6] | 0/595 = 0.0% [0.0, 0.6] | 14/595 = 2.4% [1.4, 3.9] | 581/595 = 97.6% [96.1, 98.6] |
| 5_IPD | 0/595 = 0.0% [0.0, 0.6] | 0/595 = 0.0% [0.0, 0.6] | 12/595 = 2.0% [1.2, 3.5] | 583/595 = 98.0% [96.5, 98.8] |
| 6_ii_tau | 0/595 = 0.0% [0.0, 0.6] | 0/595 = 0.0% [0.0, 0.6] | 15/595 = 2.5% [1.5, 4.1] | 580/595 = 97.5% [95.9, 98.5] |
| 7_retry_x2 | 0/595 = 0.0% [0.0, 0.6] | 0/595 = 0.0% [0.0, 0.6] | 86/595 = 14.5% [11.9, 17.5] | 509/595 = 85.5% [82.5, 88.1] |
| 7b_retry_x2_lenient | 83/595 = 13.9% [11.4, 17.0] | 3/595 = 0.5% [0.2, 1.5] | 0/595 = 0.0% [0.0, 0.6] | 509/595 = 85.5% [82.5, 88.1] |
| 8_greedy | 108/595 = 18.2% [15.3, 21.4] | 6/595 = 1.0% [0.5, 2.2] | 0/595 = 0.0% [0.0, 0.6] | 481/595 = 80.8% [77.5, 83.8] |
| 9_forbid | 111/595 = 18.7% [15.7, 22.0] | 4/595 = 0.7% [0.3, 1.7] | 0/595 = 0.0% [0.0, 0.6] | 480/595 = 80.7% [77.3, 83.6] |
| 9b_forbid_strict | 111/595 = 18.7% [15.7, 22.0] | 4/595 = 0.7% [0.3, 1.7] | 0/595 = 0.0% [0.0, 0.6] | 480/595 = 80.7% [77.3, 83.6] |
| 10_grammar_CD | 104/595 = 17.5% [14.6, 20.7] | 102/595 = 17.1% [14.3, 20.4] | 0/595 = 0.0% [0.0, 0.6] | 493/595 = 82.9% [79.6, 85.7] |

**v3_r31_on_june [slips]**: samples=595, contexts=595, slips=104, forced=189.

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 103/104 = 99.0% [94.8, 99.8] | 1/104 = 1.0% [0.2, 5.2] | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] |
| 2_fail_loud | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] | 104/104 = 100.0% [96.4, 100.0] | 0/104 = 0.0% [0.0, 3.6] |
| 3_T1_text_only | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] | 3/104 = 2.9% [1.0, 8.1] | 101/104 = 97.1% [91.9, 99.0] |
| 4_i_max | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] | 3/104 = 2.9% [1.0, 8.1] | 101/104 = 97.1% [91.9, 99.0] |
| 5_IPD | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] | 2/104 = 1.9% [0.5, 6.7] | 102/104 = 98.1% [93.3, 99.5] |
| 6_ii_tau | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] | 4/104 = 3.8% [1.5, 9.5] | 100/104 = 96.2% [90.5, 98.5] |
| 7_retry_x2 | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] | 79/104 = 76.0% [66.9, 83.2] | 25/104 = 24.0% [16.8, 33.1] |
| 7b_retry_x2_lenient | 79/104 = 76.0% [66.9, 83.2] | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] | 25/104 = 24.0% [16.8, 33.1] |
| 8_greedy | 87/104 = 83.7% [75.4, 89.5] | 1/104 = 1.0% [0.2, 5.2] | 0/104 = 0.0% [0.0, 3.6] | 16/104 = 15.4% [9.7, 23.5] |
| 9_forbid | 103/104 = 99.0% [94.8, 99.8] | 1/104 = 1.0% [0.2, 5.2] | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] |
| 9b_forbid_strict | 103/104 = 99.0% [94.8, 99.8] | 1/104 = 1.0% [0.2, 5.2] | 0/104 = 0.0% [0.0, 3.6] | 0/104 = 0.0% [0.0, 3.6] |
| 10_grammar_CD | 103/104 = 99.0% [94.8, 99.8] | 101/104 = 97.1% [91.9, 99.0] | 0/104 = 0.0% [0.0, 3.6] | 3/104 = 2.9% [1.0, 8.1] |

**v3_r31_off_june [all]**: samples=587, contexts=299, slips=118, forced=152. Omitted because they ran on only part of the samples: 9b_forbid_strict (469/587).

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 123/587 = 21.0% [17.9, 24.4] | 3/587 = 0.5% [0.2, 1.5] | 0/587 = 0.0% [0.0, 0.7] | 462/587 = 78.7% [75.2, 81.8] |
| 2_fail_loud | 1/587 = 0.2% [0.0, 1.0] | 1/587 = 0.2% [0.0, 1.0] | 124/587 = 21.1% [18.0, 24.6] | 462/587 = 78.7% [75.2, 81.8] |
| 3_T1_text_only | 1/587 = 0.2% [0.0, 1.0] | 1/587 = 0.2% [0.0, 1.0] | 12/587 = 2.0% [1.2, 3.5] | 574/587 = 97.8% [96.2, 98.7] |
| 4_i_max | 1/587 = 0.2% [0.0, 1.0] | 1/587 = 0.2% [0.0, 1.0] | 14/587 = 2.4% [1.4, 4.0] | 572/587 = 97.4% [95.8, 98.4] |
| 5_IPD | 1/587 = 0.2% [0.0, 1.0] | 1/587 = 0.2% [0.0, 1.0] | 12/587 = 2.0% [1.2, 3.5] | 574/587 = 97.8% [96.2, 98.7] |
| 6_ii_tau | 1/587 = 0.2% [0.0, 1.0] | 1/587 = 0.2% [0.0, 1.0] | 13/587 = 2.2% [1.3, 3.8] | 573/587 = 97.6% [96.0, 98.6] |
| 7_retry_x2 | 1/587 = 0.2% [0.0, 1.0] | 1/587 = 0.2% [0.0, 1.0] | 94/587 = 16.0% [13.3, 19.2] | 492/587 = 83.8% [80.6, 86.6] |
| 7b_retry_x2_lenient | 95/587 = 16.2% [13.4, 19.4] | 1/587 = 0.2% [0.0, 1.0] | 0/587 = 0.0% [0.0, 0.7] | 492/587 = 83.8% [80.6, 86.6] |
| 8_greedy | 113/587 = 19.3% [16.3, 22.6] | 2/587 = 0.3% [0.1, 1.2] | 0/587 = 0.0% [0.0, 0.7] | 473/587 = 80.6% [77.2, 83.6] |
| 9_forbid | 122/587 = 20.8% [17.7, 24.3] | 4/587 = 0.7% [0.3, 1.7] | 0/587 = 0.0% [0.0, 0.7] | 462/587 = 78.7% [75.2, 81.8] |
| 10_grammar_CD | 123/587 = 21.0% [17.9, 24.4] | 121/587 = 20.6% [17.5, 24.1] | 0/587 = 0.0% [0.0, 0.7] | 466/587 = 79.4% [75.9, 82.5] |

**v3_r31_off_june [slips]**: samples=587, contexts=299, slips=118, forced=152. Omitted because they ran on only part of the samples: 9b_forbid_strict (469/587).

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 118/118 = 100.0% [96.8, 100.0] | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] |
| 2_fail_loud | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] | 118/118 = 100.0% [96.8, 100.0] | 0/118 = 0.0% [0.0, 3.2] |
| 3_T1_text_only | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] | 6/118 = 5.1% [2.4, 10.7] | 112/118 = 94.9% [89.3, 97.6] |
| 4_i_max | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] | 8/118 = 6.8% [3.5, 12.8] | 110/118 = 93.2% [87.2, 96.5] |
| 5_IPD | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] | 8/118 = 6.8% [3.5, 12.8] | 110/118 = 93.2% [87.2, 96.5] |
| 6_ii_tau | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] | 7/118 = 5.9% [2.9, 11.7] | 111/118 = 94.1% [88.3, 97.1] |
| 7_retry_x2 | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] | 90/118 = 76.3% [67.8, 83.0] | 28/118 = 23.7% [17.0, 32.2] |
| 7b_retry_x2_lenient | 90/118 = 76.3% [67.8, 83.0] | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] | 28/118 = 23.7% [17.0, 32.2] |
| 8_greedy | 98/118 = 83.1% [75.3, 88.8] | 2/118 = 1.7% [0.5, 6.0] | 0/118 = 0.0% [0.0, 3.2] | 19/118 = 16.1% [10.6, 23.8] |
| 9_forbid | 117/118 = 99.2% [95.4, 99.9] | 1/118 = 0.8% [0.1, 4.6] | 0/118 = 0.0% [0.0, 3.2] | 0/118 = 0.0% [0.0, 3.2] |
| 10_grammar_CD | 118/118 = 100.0% [96.8, 100.0] | 116/118 = 98.3% [94.0, 99.5] | 0/118 = 0.0% [0.0, 3.2] | 2/118 = 1.7% [0.5, 6.0] |

**v4_r31_on_june_exm [all]**: samples=592, contexts=592, slips=65, forced=184. Omitted because they ran on only part of the samples: 6_ii_tau (531/592), 7_retry_x2 (87/592), 7b_retry_x2_lenient (87/592), 8_greedy (87/592), 9_forbid (87/592), 9b_forbid_strict (80/592), 10_grammar_CD (87/592).

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 66/592 = 11.1% [8.9, 13.9] | 6/592 = 1.0% [0.5, 2.2] | 0/592 = 0.0% [0.0, 0.6] | 521/592 = 88.0% [85.1, 90.4] |
| 2_fail_loud | 0/592 = 0.0% [0.0, 0.6] | 0/592 = 0.0% [0.0, 0.6] | 71/592 = 12.0% [9.6, 14.9] | 521/592 = 88.0% [85.1, 90.4] |
| 3_T1_text_only | 1/592 = 0.2% [0.0, 1.0] | 1/592 = 0.2% [0.0, 1.0] | 9/592 = 1.5% [0.8, 2.9] | 582/592 = 98.3% [96.9, 99.1] |
| 4_i_max | 0/592 = 0.0% [0.0, 0.6] | 0/592 = 0.0% [0.0, 0.6] | 8/592 = 1.4% [0.7, 2.6] | 584/592 = 98.6% [97.4, 99.3] |
| 5_IPD | 0/592 = 0.0% [0.0, 0.6] | 0/592 = 0.0% [0.0, 0.6] | 8/592 = 1.4% [0.7, 2.6] | 584/592 = 98.6% [97.4, 99.3] |

**v4_r31_on_june_exm [slips]**: samples=592, contexts=592, slips=65, forced=184. Omitted because they ran on only part of the samples: 6_ii_tau (531/592), 7_retry_x2 (87/592), 7b_retry_x2_lenient (87/592), 8_greedy (87/592), 9_forbid (87/592), 9b_forbid_strict (80/592), 10_grammar_CD (87/592).

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 63/65 = 96.9% [89.5, 99.2] | 3/65 = 4.6% [1.6, 12.7] | 0/65 = 0.0% [0.0, 5.6] | 0/65 = 0.0% [0.0, 5.6] |
| 2_fail_loud | 0/65 = 0.0% [0.0, 5.6] | 0/65 = 0.0% [0.0, 5.6] | 65/65 = 100.0% [94.4, 100.0] | 0/65 = 0.0% [0.0, 5.6] |
| 3_T1_text_only | 1/65 = 1.5% [0.3, 8.2] | 1/65 = 1.5% [0.3, 8.2] | 3/65 = 4.6% [1.6, 12.7] | 61/65 = 93.8% [85.2, 97.6] |
| 4_i_max | 0/65 = 0.0% [0.0, 5.6] | 0/65 = 0.0% [0.0, 5.6] | 2/65 = 3.1% [0.8, 10.5] | 63/65 = 96.9% [89.5, 99.2] |
| 5_IPD | 0/65 = 0.0% [0.0, 5.6] | 0/65 = 0.0% [0.0, 5.6] | 2/65 = 3.1% [0.8, 10.5] | 63/65 = 96.9% [89.5, 99.2] |

**v4_r31_off_june_exm [all]**: samples=590, contexts=299, slips=93, forced=151. Omitted because they ran on only part of the samples: 6_ii_tau (495/590), 7_retry_x2 (27/590), 7b_retry_x2_lenient (27/590), 8_greedy (27/590), 9_forbid (27/590), 9b_forbid_strict (26/590), 10_grammar_CD (27/590).

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 94/590 = 15.9% [13.2, 19.1] | 6/590 = 1.0% [0.5, 2.2] | 0/590 = 0.0% [0.0, 0.6] | 491/590 = 83.2% [80.0, 86.0] |
| 2_fail_loud | 1/590 = 0.2% [0.0, 1.0] | 1/590 = 0.2% [0.0, 1.0] | 98/590 = 16.6% [13.8, 19.8] | 491/590 = 83.2% [80.0, 86.0] |
| 3_T1_text_only | 1/590 = 0.2% [0.0, 1.0] | 1/590 = 0.2% [0.0, 1.0] | 12/590 = 2.0% [1.2, 3.5] | 577/590 = 97.8% [96.3, 98.7] |
| 4_i_max | 1/590 = 0.2% [0.0, 1.0] | 1/590 = 0.2% [0.0, 1.0] | 7/590 = 1.2% [0.6, 2.4] | 582/590 = 98.6% [97.3, 99.3] |
| 5_IPD | 1/590 = 0.2% [0.0, 1.0] | 1/590 = 0.2% [0.0, 1.0] | 8/590 = 1.4% [0.7, 2.7] | 581/590 = 98.5% [97.1, 99.2] |

**v4_r31_off_june_exm [slips]**: samples=590, contexts=299, slips=93, forced=151. Omitted because they ran on only part of the samples: 6_ii_tau (495/590), 7_retry_x2 (27/590), 7b_retry_x2_lenient (27/590), 8_greedy (27/590), 9_forbid (27/590), 9b_forbid_strict (26/590), 10_grammar_CD (27/590).

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 92/93 = 98.9% [94.2, 99.8] | 1/93 = 1.1% [0.2, 5.8] | 0/93 = 0.0% [0.0, 4.0] | 0/93 = 0.0% [0.0, 4.0] |
| 2_fail_loud | 0/93 = 0.0% [0.0, 4.0] | 0/93 = 0.0% [0.0, 4.0] | 93/93 = 100.0% [96.0, 100.0] | 0/93 = 0.0% [0.0, 4.0] |
| 3_T1_text_only | 0/93 = 0.0% [0.0, 4.0] | 0/93 = 0.0% [0.0, 4.0] | 7/93 = 7.5% [3.7, 14.7] | 86/93 = 92.5% [85.3, 96.3] |
| 4_i_max | 0/93 = 0.0% [0.0, 4.0] | 0/93 = 0.0% [0.0, 4.0] | 2/93 = 2.2% [0.6, 7.5] | 91/93 = 97.8% [92.5, 99.4] |
| 5_IPD | 0/93 = 0.0% [0.0, 4.0] | 0/93 = 0.0% [0.0, 4.0] | 3/93 = 3.2% [1.1, 9.1] | 90/93 = 96.8% [90.9, 98.9] |

**v2_r31_on_july [all]**: samples=592, contexts=592, slips=121, forced=193.

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 125/592 = 21.1% [18.0, 24.6] | 4/592 = 0.7% [0.3, 1.7] | 0/592 = 0.0% [0.0, 0.6] | 463/592 = 78.2% [74.7, 81.3] |
| 2_fail_loud | 0/592 = 0.0% [0.0, 0.6] | 0/592 = 0.0% [0.0, 0.6] | 129/592 = 21.8% [18.7, 25.3] | 463/592 = 78.2% [74.7, 81.3] |
| 3_T1_text_only | 0/592 = 0.0% [0.0, 0.6] | 0/592 = 0.0% [0.0, 0.6] | 15/592 = 2.5% [1.5, 4.1] | 577/592 = 97.5% [95.9, 98.5] |
| 4_i_max | 0/592 = 0.0% [0.0, 0.6] | 0/592 = 0.0% [0.0, 0.6] | 14/592 = 2.4% [1.4, 3.9] | 578/592 = 97.6% [96.1, 98.6] |
| 5_IPD | 0/592 = 0.0% [0.0, 0.6] | 0/592 = 0.0% [0.0, 0.6] | 12/592 = 2.0% [1.2, 3.5] | 580/592 = 98.0% [96.5, 98.8] |
| 6_ii_tau | 0/592 = 0.0% [0.0, 0.6] | 0/592 = 0.0% [0.0, 0.6] | 15/592 = 2.5% [1.5, 4.1] | 577/592 = 97.5% [95.9, 98.5] |

**v2_r31_on_july [slips]**: samples=592, contexts=592, slips=121, forced=193.

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 120/121 = 99.2% [95.5, 99.9] | 1/121 = 0.8% [0.1, 4.5] | 0/121 = 0.0% [0.0, 3.1] | 0/121 = 0.0% [0.0, 3.1] |
| 2_fail_loud | 0/121 = 0.0% [0.0, 3.1] | 0/121 = 0.0% [0.0, 3.1] | 121/121 = 100.0% [96.9, 100.0] | 0/121 = 0.0% [0.0, 3.1] |
| 3_T1_text_only | 0/121 = 0.0% [0.0, 3.1] | 0/121 = 0.0% [0.0, 3.1] | 7/121 = 5.8% [2.8, 11.5] | 114/121 = 94.2% [88.5, 97.2] |
| 4_i_max | 0/121 = 0.0% [0.0, 3.1] | 0/121 = 0.0% [0.0, 3.1] | 6/121 = 5.0% [2.3, 10.4] | 115/121 = 95.0% [89.6, 97.7] |
| 5_IPD | 0/121 = 0.0% [0.0, 3.1] | 0/121 = 0.0% [0.0, 3.1] | 6/121 = 5.0% [2.3, 10.4] | 115/121 = 95.0% [89.6, 97.7] |
| 6_ii_tau | 0/121 = 0.0% [0.0, 3.1] | 0/121 = 0.0% [0.0, 3.1] | 7/121 = 5.8% [2.8, 11.5] | 114/121 = 94.2% [88.5, 97.2] |

**v2_r31_off_july [all]**: samples=588, contexts=299, slips=120, forced=154. Omitted because they ran on only part of the samples: 6_ii_tau (493/588).

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 125/588 = 21.3% [18.1, 24.7] | 7/588 = 1.2% [0.6, 2.4] | 0/588 = 0.0% [0.0, 0.6] | 458/588 = 77.9% [74.4, 81.1] |
| 2_fail_loud | 1/588 = 0.2% [0.0, 1.0] | 1/588 = 0.2% [0.0, 1.0] | 129/588 = 21.9% [18.8, 25.5] | 458/588 = 77.9% [74.4, 81.1] |
| 3_T1_text_only | 1/588 = 0.2% [0.0, 1.0] | 1/588 = 0.2% [0.0, 1.0] | 15/588 = 2.6% [1.6, 4.2] | 572/588 = 97.3% [95.6, 98.3] |
| 4_i_max | 1/588 = 0.2% [0.0, 1.0] | 1/588 = 0.2% [0.0, 1.0] | 15/588 = 2.6% [1.6, 4.2] | 572/588 = 97.3% [95.6, 98.3] |
| 5_IPD | 1/588 = 0.2% [0.0, 1.0] | 1/588 = 0.2% [0.0, 1.0] | 12/588 = 2.0% [1.2, 3.5] | 575/588 = 97.8% [96.3, 98.7] |

**v2_r31_off_july [slips]**: samples=588, contexts=299, slips=120, forced=154. Omitted because they ran on only part of the samples: 6_ii_tau (493/588).

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 120/120 = 100.0% [96.9, 100.0] | 0/120 = 0.0% [0.0, 3.1] | 0/120 = 0.0% [0.0, 3.1] | 0/120 = 0.0% [0.0, 3.1] |
| 2_fail_loud | 0/120 = 0.0% [0.0, 3.1] | 0/120 = 0.0% [0.0, 3.1] | 120/120 = 100.0% [96.9, 100.0] | 0/120 = 0.0% [0.0, 3.1] |
| 3_T1_text_only | 0/120 = 0.0% [0.0, 3.1] | 0/120 = 0.0% [0.0, 3.1] | 6/120 = 5.0% [2.3, 10.5] | 114/120 = 95.0% [89.5, 97.7] |
| 4_i_max | 0/120 = 0.0% [0.0, 3.1] | 0/120 = 0.0% [0.0, 3.1] | 6/120 = 5.0% [2.3, 10.5] | 114/120 = 95.0% [89.5, 97.7] |
| 5_IPD | 0/120 = 0.0% [0.0, 3.1] | 0/120 = 0.0% [0.0, 3.1] | 6/120 = 5.0% [2.3, 10.5] | 114/120 = 95.0% [89.5, 97.7] |

**v2_re4_on [all]**: samples=1195, contexts=600, slips=5, forced=159.

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 49/1195 = 4.1% [3.1, 5.4] | 7/1195 = 0.6% [0.3, 1.2] | 0/1195 = 0.0% [0.0, 0.3] | 1139/1195 = 95.3% [94.0, 96.4] |
| 2_fail_loud | 0/1195 = 0.0% [0.0, 0.3] | 0/1195 = 0.0% [0.0, 0.3] | 56/1195 = 4.7% [3.6, 6.0] | 1139/1195 = 95.3% [94.0, 96.4] |
| 3_T1_text_only | 0/1195 = 0.0% [0.0, 0.3] | 0/1195 = 0.0% [0.0, 0.3] | 52/1195 = 4.4% [3.3, 5.7] | 1143/1195 = 95.6% [94.3, 96.7] |
| 4_i_max | 0/1195 = 0.0% [0.0, 0.3] | 0/1195 = 0.0% [0.0, 0.3] | 52/1195 = 4.4% [3.3, 5.7] | 1143/1195 = 95.6% [94.3, 96.7] |
| 5_IPD | 0/1195 = 0.0% [0.0, 0.3] | 0/1195 = 0.0% [0.0, 0.3] | 11/1195 = 0.9% [0.5, 1.6] | 1184/1195 = 99.1% [98.4, 99.5] |
| 6_ii_tau | 0/1195 = 0.0% [0.0, 0.3] | 0/1195 = 0.0% [0.0, 0.3] | 53/1195 = 4.4% [3.4, 5.8] | 1142/1195 = 95.6% [94.2, 96.6] |
| 7_retry_x2 | 0/1195 = 0.0% [0.0, 0.3] | 0/1195 = 0.0% [0.0, 0.3] | 37/1195 = 3.1% [2.3, 4.2] | 1158/1195 = 96.9% [95.8, 97.7] |
| 7b_retry_x2_lenient | 31/1195 = 2.6% [1.8, 3.7] | 6/1195 = 0.5% [0.2, 1.1] | 0/1195 = 0.0% [0.0, 0.3] | 1158/1195 = 96.9% [95.8, 97.7] |
| 8_greedy | 44/1195 = 3.7% [2.8, 4.9] | 8/1195 = 0.7% [0.3, 1.3] | 0/1195 = 0.0% [0.0, 0.3] | 1144/1195 = 95.7% [94.4, 96.7] |
| 9_forbid | 49/1195 = 4.1% [3.1, 5.4] | 7/1195 = 0.6% [0.3, 1.2] | 0/1195 = 0.0% [0.0, 0.3] | 1139/1195 = 95.3% [94.0, 96.4] |
| 9b_forbid_strict | 49/1195 = 4.1% [3.1, 5.4] | 7/1195 = 0.6% [0.3, 1.2] | 0/1195 = 0.0% [0.0, 0.3] | 1139/1195 = 95.3% [94.0, 96.4] |
| 10_grammar_CD | 6/1195 = 0.5% [0.2, 1.1] | 6/1195 = 0.5% [0.2, 1.1] | 0/1195 = 0.0% [0.0, 0.3] | 1189/1195 = 99.5% [98.9, 99.8] |

**v2_re4_on [slips]**: samples=1195, contexts=600, slips=5, forced=159.

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 5/5 = 100.0% [56.6, 100.0] | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] |
| 2_fail_loud | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 5/5 = 100.0% [56.6, 100.0] | 0/5 = 0.0% [0.0, 43.4] |
| 3_T1_text_only | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 1/5 = 20.0% [3.6, 62.4] | 4/5 = 80.0% [37.6, 96.4] |
| 4_i_max | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 1/5 = 20.0% [3.6, 62.4] | 4/5 = 80.0% [37.6, 96.4] |
| 5_IPD | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 1/5 = 20.0% [3.6, 62.4] | 4/5 = 80.0% [37.6, 96.4] |
| 6_ii_tau | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 2/5 = 40.0% [11.8, 76.9] | 3/5 = 60.0% [23.1, 88.2] |
| 7_retry_x2 | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 3/5 = 60.0% [23.1, 88.2] | 2/5 = 40.0% [11.8, 76.9] |
| 7b_retry_x2_lenient | 3/5 = 60.0% [23.1, 88.2] | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 2/5 = 40.0% [11.8, 76.9] |
| 8_greedy | 4/5 = 80.0% [37.6, 96.4] | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 1/5 = 20.0% [3.6, 62.4] |
| 9_forbid | 5/5 = 100.0% [56.6, 100.0] | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] |
| 9b_forbid_strict | 5/5 = 100.0% [56.6, 100.0] | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] | 0/5 = 0.0% [0.0, 43.4] |
| 10_grammar_CD | 4/5 = 80.0% [37.6, 96.4] | 4/5 = 80.0% [37.6, 96.4] | 0/5 = 0.0% [0.0, 43.4] | 1/5 = 20.0% [3.6, 62.4] |

**v2_re4_off [all]**: samples=1196, contexts=599, slips=14, forced=122.

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 44/1196 = 3.7% [2.8, 4.9] | 8/1196 = 0.7% [0.3, 1.3] | 0/1196 = 0.0% [0.0, 0.3] | 1146/1196 = 95.8% [94.5, 96.8] |
| 2_fail_loud | 0/1196 = 0.0% [0.0, 0.3] | 0/1196 = 0.0% [0.0, 0.3] | 50/1196 = 4.2% [3.2, 5.5] | 1146/1196 = 95.8% [94.5, 96.8] |
| 3_T1_text_only | 0/1196 = 0.0% [0.0, 0.3] | 0/1196 = 0.0% [0.0, 0.3] | 43/1196 = 3.6% [2.7, 4.8] | 1153/1196 = 96.4% [95.2, 97.3] |
| 4_i_max | 0/1196 = 0.0% [0.0, 0.3] | 0/1196 = 0.0% [0.0, 0.3] | 41/1196 = 3.4% [2.5, 4.6] | 1155/1196 = 96.6% [95.4, 97.5] |
| 5_IPD | 0/1196 = 0.0% [0.0, 0.3] | 0/1196 = 0.0% [0.0, 0.3] | 20/1196 = 1.7% [1.1, 2.6] | 1176/1196 = 98.3% [97.4, 98.9] |
| 6_ii_tau | 0/1196 = 0.0% [0.0, 0.3] | 0/1196 = 0.0% [0.0, 0.3] | 45/1196 = 3.8% [2.8, 5.0] | 1151/1196 = 96.2% [95.0, 97.2] |
| 7_retry_x2 | 0/1196 = 0.0% [0.0, 0.3] | 0/1196 = 0.0% [0.0, 0.3] | 31/1196 = 2.6% [1.8, 3.7] | 1165/1196 = 97.4% [96.3, 98.2] |
| 7b_retry_x2_lenient | 28/1196 = 2.3% [1.6, 3.4] | 3/1196 = 0.3% [0.1, 0.7] | 0/1196 = 0.0% [0.0, 0.3] | 1165/1196 = 97.4% [96.3, 98.2] |
| 8_greedy | 50/1196 = 4.2% [3.2, 5.5] | 7/1196 = 0.6% [0.3, 1.2] | 0/1196 = 0.0% [0.0, 0.3] | 1139/1196 = 95.2% [93.9, 96.3] |
| 9_forbid | 43/1196 = 3.6% [2.7, 4.8] | 8/1196 = 0.7% [0.3, 1.3] | 0/1196 = 0.0% [0.0, 0.3] | 1146/1196 = 95.8% [94.5, 96.8] |
| 9b_forbid_strict | 43/1196 = 3.6% [2.7, 4.8] | 8/1196 = 0.7% [0.3, 1.3] | 0/1196 = 0.0% [0.0, 0.3] | 1146/1196 = 95.8% [94.5, 96.8] |
| 10_grammar_CD | 11/1196 = 0.9% [0.5, 1.6] | 11/1196 = 0.9% [0.5, 1.6] | 0/1196 = 0.0% [0.0, 0.3] | 1185/1196 = 99.1% [98.4, 99.5] |

**v2_re4_off [slips]**: samples=1196, contexts=599, slips=14, forced=122.

| arm | delivered-malformed | silent corruption | loud | clean |
|---|---|---|---|---|
| 1_lenient | 14/14 = 100.0% [78.5, 100.0] | 2/14 = 14.3% [4.0, 39.9] | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] |
| 2_fail_loud | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] | 14/14 = 100.0% [78.5, 100.0] | 0/14 = 0.0% [0.0, 21.5] |
| 3_T1_text_only | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] | 7/14 = 50.0% [26.8, 73.2] | 7/14 = 50.0% [26.8, 73.2] |
| 4_i_max | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] | 5/14 = 35.7% [16.3, 61.2] | 9/14 = 64.3% [38.8, 83.7] |
| 5_IPD | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] | 5/14 = 35.7% [16.3, 61.2] | 9/14 = 64.3% [38.8, 83.7] |
| 6_ii_tau | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] | 9/14 = 64.3% [38.8, 83.7] | 5/14 = 35.7% [16.3, 61.2] |
| 7_retry_x2 | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] | 9/14 = 64.3% [38.8, 83.7] | 5/14 = 35.7% [16.3, 61.2] |
| 7b_retry_x2_lenient | 9/14 = 64.3% [38.8, 83.7] | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] | 5/14 = 35.7% [16.3, 61.2] |
| 8_greedy | 10/14 = 71.4% [45.4, 88.3] | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] | 4/14 = 28.6% [11.7, 54.6] |
| 9_forbid | 13/14 = 92.9% [68.5, 98.7] | 2/14 = 14.3% [4.0, 39.9] | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] |
| 9b_forbid_strict | 13/14 = 92.9% [68.5, 98.7] | 2/14 = 14.3% [4.0, 39.9] | 0/14 = 0.0% [0.0, 21.5] | 0/14 = 0.0% [0.0, 21.5] |
| 10_grammar_CD | 11/14 = 78.6% [52.4, 92.4] | 11/14 = 78.6% [52.4, 92.4] | 0/14 = 0.0% [0.0, 21.5] | 3/14 = 21.4% [7.6, 47.6] |

### 4.4 Onset arms vs June: exemplar immunization (arm 11) and July template (arm 12), paired by context

| comparison | outcome | contexts | June (samples, Wilson 95%) | arm (samples, Wilson 95%) | difference of per-context rates (context bootstrap 95%) |
|---|---|---|---|---|---|
| arm11_exemplar_on | slip | 588 | 103/588 = 17.5% [14.7, 20.8] | 65/588 = 11.1% [8.8, 13.8] | -6.5 pp [-9.7, -3.4] |
| arm11_exemplar_on | census_malformed | 588 | 110/588 = 18.7% [15.8, 22.1] | 66/588 = 11.2% [8.9, 14.0] | -7.5 pp [-10.7, -4.4] |
| arm11_exemplar_on | slip_natural_only | 349 | 56/349 = 16.0% [12.6, 20.3] | 33/349 = 9.5% [6.8, 13.0] | -6.6 pp [-10.3, -2.9] |
| arm11_exemplar_on | census_malformed_natural_only | 349 | 59/349 = 16.9% [13.3, 21.2] | 34/349 = 9.7% [7.1, 13.3] | -7.2 pp [-11.2, -3.4] |
| arm11_exemplar_off | slip | 299 | 118/587 = 20.1% [17.1, 23.5] | 93/590 = 15.8% [13.0, 18.9] | -4.3 pp [-8.5, -0.5] |
| arm11_exemplar_off | census_malformed | 299 | 123/587 = 21.0% [17.9, 24.4] | 94/590 = 15.9% [13.2, 19.1] | -5.0 pp [-9.2, -1.2] |
| arm11_exemplar_off | slip_natural_only | 233 | 81/410 = 19.8% [16.2, 23.9] | 63/417 = 15.1% [12.0, 18.9] | -4.9 pp [-9.7, +0.0] |
| arm11_exemplar_off | census_malformed_natural_only | 233 | 85/410 = 20.7% [17.1, 24.9] | 65/417 = 15.6% [12.4, 19.4] | -5.4 pp [-10.3, -0.4] |
| arm12_july_on | slip | 588 | 104/588 = 17.7% [14.8, 21.0] | 121/588 = 20.6% [17.5, 24.0] | +2.9 pp [-0.3, +6.1] |
| arm12_july_on | census_malformed | 588 | 111/588 = 18.9% [15.9, 22.2] | 125/588 = 21.3% [18.1, 24.7] | +2.4 pp [-1.0, +5.6] |
| arm12_july_on | slip_natural_only | 333 | 52/333 = 15.6% [12.1, 19.9] | 63/333 = 18.9% [15.1, 23.5] | +3.3 pp [-0.3, +6.6] |
| arm12_july_on | census_malformed_natural_only | 333 | 55/333 = 16.5% [12.9, 20.9] | 62/333 = 18.6% [14.8, 23.1] | +2.1 pp [-1.2, +5.7] |
| arm12_july_off | slip | 298 | 118/585 = 20.2% [17.1, 23.6] | 120/587 = 20.4% [17.4, 23.9] | +0.2 pp [-2.0, +2.3] |
| arm12_july_off | census_malformed | 298 | 123/585 = 21.0% [17.9, 24.5] | 125/587 = 21.3% [18.2, 24.8] | +0.2 pp [-2.0, +2.3] |
| arm12_july_off | slip_natural_only | 240 | 80/423 = 18.9% [15.5, 22.9] | 79/421 = 18.8% [15.3, 22.8] | -0.4 pp [-2.7, +1.9] |
| arm12_july_off | census_malformed_natural_only | 240 | 84/423 = 19.9% [16.3, 23.9] | 83/421 = 19.7% [16.2, 23.8] | -0.4 pp [-2.7, +1.9] |

- arm11_exemplar_on: edit calls to the exemplar's own file `NOTES.md` (they extend the exemplar's note): forced 56/184, natural 0/408; slips among them 0.
- arm11_exemplar_off: edit calls to the exemplar's own file `NOTES.md` (they extend the exemplar's note): forced 42/151, natural 0/439; slips among them 3.

### 4.5 Gold intent: real logged slips with retry-derived intent (base 31B)

229 records; slip site found in 229/229.

| arm | exact intent | new_string exact | old_string exact | strictly valid | silent corruption |
|---|---|---|---|---|---|
| i_nc | 227/229 = 99.1% [96.9, 99.8] | 229/229 = 100.0% [98.4, 100.0] | 227/229 = 99.1% [96.9, 99.8] | 229/229 = 100.0% [98.4, 100.0] | 0/229 = 0.0% [0.0, 1.6] |
| i_max | 217/229 = 94.8% [91.1, 97.0] | 219/229 = 95.6% [92.1, 97.6] | 223/229 = 97.4% [94.4, 98.8] | 229/229 = 100.0% [98.4, 100.0] | 0/229 = 0.0% [0.0, 1.6] |
| retry_x2 | 45/229 = 19.7% [15.0, 25.3] | 46/229 = 20.1% [15.4, 25.8] | 47/229 = 20.5% [15.8, 26.2] | 69/229 = 30.1% [24.6, 36.4] | 0/229 = 0.0% [0.0, 1.6] |
| greedy | 30/229 = 13.1% [9.3, 18.1] | 30/229 = 13.1% [9.3, 18.1] | 31/229 = 13.5% [9.7, 18.6] | 47/229 = 20.5% [15.8, 26.2] | 0/229 = 0.0% [0.0, 1.6] |
| forbid_strict | 0/229 = 0.0% [0.0, 1.6] | 0/229 = 0.0% [0.0, 1.6] | 2/229 = 0.9% [0.2, 3.1] | 2/229 = 0.9% [0.2, 3.1] | 2/229 = 0.9% [0.2, 3.1] |
| grammar | 0/229 = 0.0% [0.0, 1.6] | 0/229 = 0.0% [0.0, 1.6] | 171/229 = 74.7% [68.7, 79.9] | 229/229 = 100.0% [98.4, 100.0] | 229/229 = 100.0% [98.4, 100.0] |
| T1_assumed_tail | 219/229 = 95.6% [92.1, 97.6] | 219/229 = 95.6% [92.1, 97.6] | 229/229 = 100.0% [98.4, 100.0] | 229/229 = 100.0% [98.4, 100.0] | 0/229 = 0.0% [0.0, 1.6] |
| ii_assumed_tail | 229/229 = 100.0% [98.4, 100.0] | 229/229 = 100.0% [98.4, 100.0] | 229/229 = 100.0% [98.4, 100.0] | 229/229 = 100.0% [98.4, 100.0] | 0/229 = 0.0% [0.0, 1.6] |

### 4.5b Gold intent: natural closures re-sampled at the 229 real slip-prone states (G1R, k=4)

417 samples from 105 states. Natural slip rate 290/417 = 69.5% [65.0, 73.8]; slip runs: [['`', 275], ['\\"', 9], ['""`', 4], ['', 2]]. False repairs on clean closures: IPD changed 0/127 = 0.0% [0.0, 2.9], T1 changed 0/127 = 0.0% [0.0, 2.9].

**[slips]**

| arm | exact intent | new_string exact | old_string exact | strictly valid | silent corruption |
|---|---|---|---|---|---|
| 1_lenient_or_failloud | 0/290 = 0.0% [0.0, 1.3] | 0/290 = 0.0% [0.0, 1.3] | 0/290 = 0.0% [0.0, 1.3] | 0/290 = 0.0% [0.0, 1.3] | 0/290 = 0.0% [0.0, 1.3] |
| 3_T1_text_only | 271/290 = 93.4% [90.0, 95.8] | 282/290 = 97.2% [94.7, 98.6] | 277/290 = 95.5% [92.5, 97.4] | 290/290 = 100.0% [98.7, 100.0] | 0/290 = 0.0% [0.0, 1.3] |
| 4_i_max | 277/290 = 95.5% [92.5, 97.4] | 282/290 = 97.2% [94.7, 98.6] | 277/290 = 95.5% [92.5, 97.4] | 290/290 = 100.0% [98.7, 100.0] | 0/290 = 0.0% [0.0, 1.3] |
| 5_IPD | 280/290 = 96.6% [93.8, 98.1] | 285/290 = 98.3% [96.0, 99.3] | 280/290 = 96.6% [93.8, 98.1] | 289/290 = 99.7% [98.1, 99.9] | 0/290 = 0.0% [0.0, 1.3] |
| 6_ii_tau0.0 | 275/290 = 94.8% [91.6, 96.8] | 286/290 = 98.6% [96.5, 99.5] | 277/290 = 95.5% [92.5, 97.4] | 290/290 = 100.0% [98.7, 100.0] | 0/290 = 0.0% [0.0, 1.3] |
| 6_ii_tau2.0 | 275/290 = 94.8% [91.6, 96.8] | 286/290 = 98.6% [96.5, 99.5] | 277/290 = 95.5% [92.5, 97.4] | 290/290 = 100.0% [98.7, 100.0] | 0/290 = 0.0% [0.0, 1.3] |
| 7_retry_x2 | 19/290 = 6.6% [4.2, 10.0] | 19/290 = 6.6% [4.2, 10.0] | 19/290 = 6.6% [4.2, 10.0] | 46/290 = 15.9% [12.1, 20.5] | 0/290 = 0.0% [0.0, 1.3] |
| 8_greedy | 11/290 = 3.8% [2.1, 6.7] | 11/290 = 3.8% [2.1, 6.7] | 11/290 = 3.8% [2.1, 6.7] | 33/290 = 11.4% [8.2, 15.6] | 0/290 = 0.0% [0.0, 1.3] |
| 9b_forbid_strict | 0/290 = 0.0% [0.0, 1.3] | 0/290 = 0.0% [0.0, 1.3] | 2/290 = 0.7% [0.2, 2.5] | 2/290 = 0.7% [0.2, 2.5] | 0/290 = 0.0% [0.0, 1.3] |
| 10_grammar_CD | 0/290 = 0.0% [0.0, 1.3] | 0/290 = 0.0% [0.0, 1.3] | 228/290 = 78.6% [73.5, 82.9] | 290/290 = 100.0% [98.7, 100.0] | 288/290 = 99.3% [97.5, 99.8] |

**[clean_closures]**

| arm | exact intent | new_string exact | old_string exact | strictly valid | silent corruption |
|---|---|---|---|---|---|
| 1_lenient_or_failloud | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |
| 3_T1_text_only | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |
| 4_i_max | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |
| 5_IPD | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |
| 6_ii_tau0.0 | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |
| 6_ii_tau2.0 | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |
| 7_retry_x2 | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |
| 8_greedy | 33/127 = 26.0% [19.1, 34.2] | 33/127 = 26.0% [19.1, 34.2] | 33/127 = 26.0% [19.1, 34.2] | 37/127 = 29.1% [21.9, 37.6] | 0/127 = 0.0% [0.0, 2.9] |
| 9b_forbid_strict | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |
| 10_grammar_CD | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 120/127 = 94.5% [89.1, 97.3] | 127/127 = 100.0% [97.1, 100.0] | 0/127 = 0.0% [0.0, 2.9] |

### 4.5c Gold intent, combined natural slips: G1 (229) + G1R (290) = 519 slips from 229 states

G1 = logged slips replayed from the exact logged prefix (229 base-31B); G1R = natural slips of the model re-sampled (k=4, T=0.2) at the first 105 of the same states. T1 and (ii) use an ASSUMED tail on G1 (the emitted tail was lost at serving time) and the real emitted tail on G1R. CI: Wilson on items and a state-cluster bootstrap (B=2000).

| arm | exact intent (Wilson 95%) | state-cluster bootstrap 95% |
|---|---|---|
| IPD | 507/519 = 97.7% [96.0, 98.7] | [95.2, 99.6] |
| i_max | 494/519 = 95.2% [93.0, 96.7] | [91.7, 97.9] |
| T1_text_only | 490/519 = 94.4% [92.1, 96.1] | [90.8, 97.4] |
| ii_tau2 | 504/519 = 97.1% [95.3, 98.2] | [94.4, 99.3] |
| retry_x2 | 64/519 = 12.3% [9.8, 15.4] | [8.9, 16.1] |
| greedy | 41/519 = 7.9% [5.9, 10.5] | [5.0, 11.5] |
| forbid_strict | 0/519 = 0.0% [0.0, 0.7] | [0.0, 0.0] |
| grammar_CD | 0/519 = 0.0% [0.0, 0.7] | [0.0, 0.0] |

Paired, same slips: IPD minus arm (exact intent), state-cluster bootstrap 95%:

| arm | IPD − arm | IPD right, arm wrong | arm right, IPD wrong |
|---|---|---|---|
| i_max | +2.5 pp [+0.7, +4.9] | 14 | 1 |
| T1_text_only | +3.3 pp [+0.8, +6.1] | 20 | 3 |
| ii_tau2 | +0.6 pp [-0.8, +2.4] | 6 | 3 |
| retry_x2 | +85.4 pp [+81.1, +89.1] | 443 | 0 |
| greedy | +89.8 pp [+85.8, +93.2] | 466 | 0 |

### 4.6 Gold copy task: gc_31b_off_t07.jsonl (samples 67, slips 0)

**[all]**

| arm | delivered-malformed | silent | loud | exact_intent | edit_applies | edit_correct |
|---|---|---|---|---|---|---|
| 1_lenient | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 2_fail_loud | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 3_T1_text_only | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 4_i_max | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 5_IPD | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 6_ii_tau | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 7_retry_x2 | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 7b_retry_x2_lenient | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 8_greedy | 3/67 = 4.5% [1.5, 12.4] | 3/67 = 4.5% [1.5, 12.4] | 0/67 = 0.0% [0.0, 5.4] | 59/67 = 88.1% [78.2, 93.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 9_forbid | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 9b_forbid_strict | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |
| 10_grammar_CD | 2/67 = 3.0% [0.8, 10.2] | 2/67 = 3.0% [0.8, 10.2] | 0/67 = 0.0% [0.0, 5.4] | 58/67 = 86.6% [76.4, 92.8] | 8/67 = 11.9% [6.2, 21.8] | 8/67 = 11.9% [6.2, 21.8] |

### 4.6 Gold copy task: gc_e4b_off_t07.jsonl (samples 257, slips 0)

**[all]**

| arm | delivered-malformed | silent | loud | exact_intent | edit_applies | edit_correct |
|---|---|---|---|---|---|---|
| 1_lenient | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 2_fail_loud | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 3_T1_text_only | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 4_i_max | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 5_IPD | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 6_ii_tau | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 7_retry_x2 | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 7b_retry_x2_lenient | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 8_greedy | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 211/257 = 82.1% [77.0, 86.3] | 254/257 = 98.8% [96.6, 99.6] | 249/257 = 96.9% [94.0, 98.4] |
| 9_forbid | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 9b_forbid_strict | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |
| 10_grammar_CD | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 0/257 = 0.0% [0.0, 1.5] | 202/257 = 78.6% [73.2, 83.2] | 253/257 = 98.4% [96.1, 99.4] | 248/257 = 96.5% [93.5, 98.1] |

### 4.7 QuoteStorm, model-free, all valid calls

| set | valid calls | (i)/(ii) changed | pattern-only detector fires | regex splitter fires | census flags | synthetic slips: detected / GT in candidates / whole-run cut correct |
|---|---|---|---|---|---|---|
| all | 229414 | 0 / 0 (Wilson upper 0.0017%) | 120 | 808 | 826 | 100.00% / 100.00% / 74.5% |
| natural | 228214 | 0 / 0 (Wilson upper 0.0017%) | 0 | 10 | 28 | 100.00% / 100.00% / 74.5% |
| adversarial | 1200 | 0 / 0 (Wilson upper 0.3191%) | 120 | 798 | 798 | 100.00% / 100.00% / 72.2% |

### 4.8 Synthetic slips with known intent, model-scored

| file | n | GT among candidates | (ii) argmax: no prior / disjoint prior / matched prior | (ii) disjoint prior τ=2: correct / wrong / abstain | (i) cut: noisy-channel / likelihood / whole-run |
|---|---|---|---|---|---|
| v2_qsm_e4b_copy.jsonl | 2000 | 2000/2000 = 100.0% [99.8, 100.0] | 1967/2000 = 98.4% [97.7, 98.8] / 1989/2000 = 99.5% [99.0, 99.7] / 1988/2000 = 99.4% [99.0, 99.7] | 1986/2000 = 99.3% [98.8, 99.6] / 7/2000 = 0.4% [0.2, 0.7] / 7/2000 = 0.4% [0.2, 0.7] | 1989/2000 = 99.5% [99.0, 99.7] / 1966/2000 = 98.3% [97.6, 98.8] / 1256/2000 = 62.8% [60.7, 64.9] |

## 5. Files
- **Library**
  - `gemma_protocol.py`: grammar, guard, slip/opener/kwarg/qkey sites, bounded repair candidates, grammar-state
    emulation, `runtime_view` (delivered / silent corruption), census judge.
  - `intent_decode.py`: `Server` (prompt_logprobs guard), `Pin` (prefix pinning), exact forced-token scoring, WCTF,
    `ChannelPrior`, `rollback_resume` (i), `lik_repair` (ii), `generate_call`.
  - `arms.py`: retry, greedy, forbid-trigger (both variants), grammar-CD.
  - `replay_utils.py`: message fixing, June/July templates, exemplar.
- **Tests**
  - `tests/test_protocol.py`: unit, property and pathological-run tests.
  - `tests/test_decode_pure.py`: prior, cut rules, continuations, prompt_logprobs guard, opt-in rules.
  - `tests/smoke_server.py`: live smoke test.
- **Data**
  - `mine_logs.py` builds `data/first_edit_contexts.jsonl` and `data/log_slips.jsonl`.
  - `data/replay_gemma_first_edit.jsonl`: Gemma-only E1 contexts.
  - `build_gold_copy.py` builds `data/gold_copy_*`, `data/gold_copy_files/` and `data/gold_all_ctx*.jsonl`.
  - `mine_payloads.py` builds `data/quotestorm.jsonl`.
  - `data/tools_official.json`
- **Experiments**: `replay.py` (E1, inline arms, G2), `head2head_gen.py`, `rs279.py` (G1), `quotestorm_free*.py`
  (E2), `quotestorm_model.py` (E3), `selfslip.py`, `retry_baseline.py`, `bench_latency.py`, `extend_residual.py`,
  `map_repair.py` (A2 service), lane scripts `lane_*.sh`.
- **Analysis**: `analyze_replay.py` (gate metrics, natural-next-call), `analyze_h2h.py` (head-to-head, gold
  metrics), `analyze_rs279.py`, `analyze_quotestorm.py`, `gate_summary.py`, `make_results.py` (writes
  `results.json`), `render_results_md.py` (writes the §4 tables), `stats.py`.
- **Outputs**: `out/v3_*_june.jsonl` (primary), `out/v2_*` (July arm 12, E4B, E3), `out/v4_*_exm.jsonl` (arm 11),
  `out/h2h_*.jsonl`, `out/rs279_31b.jsonl`, `out/gc_*.jsonl`, `out/quotestorm_free*.json`, `results.json`.
  `out/old_v1/` holds superseded or contaminated outputs and is not used.
- **Run everything** via `tools/limited.sh` with QN=VLLM:Worker_D<gpu>, using
  `/opt/envs/env_gemma/bin/python`.
- **Proxy equivalence (§8)**: `proxy_equivalence.py` (offline / quotestorm / p1 / p1e / tf / live / analyze),
  `proxy_vendor/` (read-only, hash-verified copy of E's frozen-candidate proxy), `data/proxy_modeldir_june/`
  (tokenizer links + the June-5 template, md5 d6c5bd0d…), `out/proxy_eq/`, `out/proxy_equivalence.json`.
- **Path shim**: `paths_override.py` (main-track tree moved to <competition-logs> template md5 verified).

## 6. Open issues and limitations (honest list)
1. **Structure, not content.**
   - IPD restores the intended protocol structure; it does not fix JSON-string-mode content (literal `\n` / `\"`
     escapes inside raw strings).
   - The harness's "unescaped" fallback sometimes applies such edits anyway.
   - Forcing `<|"|>` at a drifted opener ((i+)) does pull the regenerated value back to raw mode.
2. **(i) regenerates the suffix.** The re-emitted arguments can differ from the original suffix, which was produced
   in a corrupted state. It can occasionally add a benign duplicate key, which is census-clean but strict-invalid.
3. **Forced edits.** Where the model chose another tool, E1 forces `edit_file`. Natural-only results and the unforced
   natural-next-call analysis are reported separately.
4. **E4B fails differently.**
   - Its failures are mostly opener drift, Python-kwarg drift (`filepath="x"`), JSON quoted-key slips and runaway
     strings; it has few closer slips.
   - IPD's census reduction on E4B is therefore lower than on 31B. Opt-in `kwarg`/`qkey` rules exist (`(i++)`,
     `extend_residual.py`) but are not part of the deployed default.
   - E4B makes essentially no copy-task slips (0/262).
5. **G1 selection.**
   - The retry-derived intent matches retry.new_string == payload-without-closer. The gold cut is the whole run for
     219/229 records and partial for 10 (composite runs).
   - T1/(ii) on G1 use an assumed tail; only resuming decoders are evaluated on the real lost tail.
6. **12B not run.** :8301 is workstream A's lane; the gold slips come from 31B (E4B rarely slips).
7. **Composite closers are intrinsically ambiguous** (P4). The disjoint prior has never seen some of them, and
   τ-abstention trades coverage for precision.
8. **Concurrency budget.** Prefix pins count toward the ≤32 in-flight cap per server, which limited throughput.
9. **E4B ON** has 1,197 of 1,200 samples: 3 contexts lost their second sample at a restart.
10. **Arms 11/12 are onset comparisons.**
    - Exemplar ON: the first 87 records carry the full inline head-to-head; after the 15:53 restart the rest carry
      onset + (i) only.
    - Exemplar OFF: the first 27 records carry the full inline head-to-head; the rest are onset-only.
    - The July runs never had the inline head-to-head; they have (i)/(ii).
    - All four arms completed before the lane hand-back (18:13 UTC): exemplar ON 600/600, exemplar OFF 599/600,
      July ON 600/600, July OFF 595/600 samples. Missing samples are second samples lost at restarts (item 14).
11. **Guard trigger.** At 15:52 UTC the :8302 guard (KV > 90% twice) stopped three jobs. They resumed at ≤32 in
    flight, and no sample was lost beyond in-flight work.
12. **G1R stopping rule.** G1R was stopped at 417 samples (about 105 of 229 states) once the gold set reached
    ≥ 500 natural slips: G1 229 + G1R 290 = 519. These are the first states in corpus order, not a random subset.
13. **"Thinking OFF" still produces a thought.** With `enable_thinking=False` (June template), the 31B still opens a
    thought channel in 583/587 OFF call samples. The median thought is 682 characters, against 952 with thinking ON.
    So ON and OFF differ in the template's thinking flag and in thought length, not in whether a thought is present.
    The replayed histories come from thinking-ON runs: 298/300 OFF contexts render earlier thoughts into the history
    (the OFF prompt itself has no `<|think|>` flag). The model emits a thought in 579/583 samples of those contexts,
    and in 4/4 samples of the two contexts without one.
    The July template behaves the same way with thinking OFF: 584/588 call samples, median 685 characters. PREREG_v2.1
    describes A's thinking-OFF battery as emitting the call with no thought. In B's replays, `enable_thinking=False`
    alone did not suppress the thought.
14. **Lost samples.** The June OFF and July OFF replays each have 595 of 600 samples (300 contexts × 2). A restart
    resumes by (context, seed), so a context whose first sample was already written loses its in-flight second
    sample. The paired onset comparisons use per-context rates over the samples present.
15. **Discovery prompts are 1 token short of the logged prompts.** System content was passed as a string instead
    of text parts, which drops one space before the tool declarations (§3.1). This holds for all 600 gate contexts.
    It affects every June-template discovery replay (E1, arms 11/12, G1, G1R). It does not affect the confirmatory
    runner.
16. **G1 seeds are not reproducible.** `rs279.py` drew each record's seed from Python's salted `hash(id)`, so the
    exact G1 samples cannot be regenerated. The statistics stand. The proxy-equivalence replay of G1 (§8.3) uses
    sha256-based seeds and reproduces the 227/229 exact-intent result.
17. **vLLM parser hang.** vLLM 0.19.1's `_parse_gemma4_array` can loop forever on some malformed arrays. One fresh live
    proxy sample triggered it inside B's census judge. The proxy-equivalence analysis installs the same no-progress
    patch that workstreams A and E use. The discovery analyses completed without hitting it.

## 7. Confirmatory run on workstream P's fresh corpus (PREREG_v2 §3.2: C12–C16)
Everything above uses the main-track logs: that is the **discovery** set. The confirmatory run uses workstream P's
fresh corpus (SWE-bench tasks, our harness, Gemma-4-31B-QAT, thinking ON). B has not opened P's data. It is read
only by the frozen scripts below, after PREREG_v2 is frozen.

- **Frozen package `confirm/`.** Frozen 2026-11-04 15:45 UTC, before the pools existed. Combined sha256 (= sha256
  of `confirm/FREEZE_MANIFEST.txt`): `2ee89869735ea76514908f0a3626c362bfd58ec93de40ab608536cee4a84e2b0`. Per-file
  hashes are in `confirm/FREEZE_MANIFEST.txt`. The package imports only its own frozen copies of the library, plus the
  frozen closer prior `prior_ft_edit.json` (505 main-track fine-tune slips, add-½).
- **States.** Pool B1 of stratum S1 (A's `POOLS_MANIFEST.json` → `S1_B1.jsonl`), in rank order, the first 600.
  One sample per state.
- **Rendering.** The corpus manifest's chat template and kwargs, with system content as text parts when declared.
  The token count must equal the logged `prompt_tokens`; otherwise the state is recorded as `render_mismatch`.
- **Sampling.** P's: T = 1.0, top-p 0.95, top-k 64. The thinking budget is emulated. If the natural next call is not
  the edit tool, an edit call is forced and flagged, as in discovery.
- **Arms**, on the same baseline sample with the prefix pinned: IPD (i+), retry ×2, greedy, grammar-CD. T1,
  lenient and fail-loud are computed offline.
- **Claims and rules** (abridged from PREREG_v2 §3.2; the PREREG text governs):

  | # | claim | discovery | prediction | rule |
  |---|---|---|---|---|
  | C12 | natural first-edit census-malformed under base decoding | 18.7% (closer slips 17.5%) | 14% [6, 26] | descriptive |
  | C13 | IPD relative reduction of delivered-malformed first edits | 93.7% [87.6, 96.9] | 90% [75, 98] | REPLICATES iff CI_lo ≥ 0.50 and point ≥ 0.75; ATTENUATED iff CI_lo > 0 and point < 0.75; FAILS iff CI_lo ≤ 0 |
  | C14 | byte identity: IPD changes 0 valid calls | 0/480; 0/229,414 model-free | 0 | any changed valid call FAILS |
  | C15 | head-to-head on slips | IPD 98% clean; T1 97%; retry×2 24% clean, 76% loud; greedy 84% malformed; grammar-CD 97% silent | IPD clean ≥ 0.90; T1 clean ≥ 0.90 and \|IPD − T1\| ≤ 5 pp; retry×2 loud ≥ 0.50; greedy malformed ≥ 0.60; grammar-CD silent ≥ 0.80 | per decoder: REPLICATES iff the point satisfies it and the 95% CI excludes the opposite side of 0.5 |
  | C16 | IPD exact intent on P's real slips (gold from a later clean retry) | PREREG: 97.7% (interim 44/229); final discovery 507/519 = 97.7% (§4.5c) | ≥ 0.90 | REPLICATES iff CI_lo ≥ 0.80; NOT_ESTIMABLE if P yields no such slip |

- **F3c family (Holm).** C13 vs base, plus IPD vs each baseline (lenient, T1, retry ×2 lenient, greedy, grammar-CD)
  on delivered-malformed: exact McNemar, Holm-adjusted. Halves H1 and H2 are reported beside the full sample. S2 is
  a separate stratum if `S2_B1.jsonl` exists.
- **Schedule.** Run on Nov 5 after the user's green light (S1 07:05–08:42 UTC, S2 08:44–08:53 UTC). Outputs:
  `out/confirm_S1_B1.jsonl`, `out/confirm_S1_B1_analysis.json` and `out/confirm_gold_S1.jsonl`. They are reported as
  an addendum to this README and to `results.json`, with no change to the frozen code.
- **Run log.** PREREG_v2 pools applied 2026-11-05 07:02:24 UTC (A's `POOLS_MANIFEST.json`, script sha256 60025bef…):
  - S1 B1 has 600 states (236 verified, 364 extended); S2 B1 has 82.
  - The confirm/ hashes were re-verified before launch (combined sha256 2ee89869…, unchanged).
  - S1 started 07:05 UTC on :8302, with --conc 22 --workers 10 (≤32 requests in flight, prefix pins included).
  - P's manifest gives the chat template path relative to the manifest (`chat_template.jinja`, md5 f016bd4b…, the
    July template that P's server used). The frozen runner opens that path as given, so it runs with the manifest
    directory as working directory, as P's manifest note prescribes. No code was changed.
  - Rendering: the first states render to exactly the logged `prompt_tokens`, with system content as parts.
- **Verified-only analysis.** `confirm_subset.py` restricts the runner output to `verified_only/S1_B1.jsonl`, and the
  frozen `confirm_analyze.py` is applied to it unchanged.
- **Operational.** S1 was restarted once at 172/600 records (07:27 UTC) to raise workers from 10 to 14. The runner
  resumes by context, and in-flight states were re-run with the same per-context seeds. All 600 S1 states and 82 S2
  states rendered to exactly the logged `prompt_tokens`, with 0 errors and 0 preemptions.

### 7.1 Confirmatory results (FINAL; `results.json` → `confirmatory_PREREG_v2`)
**S1 B1, all 600 states** (600 edit calls, 239 forced; P's sampling at T = 1.0):

| claim | result | verdict |
|---|---|---|
| C12 census-malformed first edits | 13/600 = **2.2% [1.3, 3.7]**: natural 3/361 = 0.8%, forced 10/239 = 4.2%; closer slips 13/600 | **LOWER** than predicted (80% PI 14% [6, 26]; §4 descriptive rule) |
| C13 IPD relative reduction | 13 → 1 census-malformed (the 1 is not a slip): **92.3% [66.7, 98.6]** | **REPLICATES** |
| C14 byte identity | **0/582** valid calls changed | **REPLICATES** |
| C15 IPD clean on slips | 13/13 | REPLICATES |
| C15 T1 clean on slips | 13/13; IPD − T1 = 0 | REPLICATES (within 5 pp) |
| C15 retry ×2 loud | 2/13 (11/13 clean) | **FAILS**: at T = 1.0 most retries succeed |
| C15 greedy delivered-malformed | 5/13 | **FAILS** (prediction ≥ 0.60) |
| C15 grammar-CD silent corruption | 10/13 = 77% | **ATTENUATED** (prediction ≥ 0.80) |
| C16 IPD exact intent on P's real slips | 0 eligible slips | **NOT_ESTIMABLE** (see below) |

- **F3c, delivered-malformed over all 600 calls, IPD 0/600** (exact McNemar, Holm):
  - vs lenient 13/600: p_Holm = 0.0012;
  - vs grammar-CD 12/600: 0.0020;
  - vs greedy 7/600: 0.047;
  - vs retry ×2 with lenient fallback 3/600: 0.50 (n.s.);
  - vs T1 0/600: 1.0.
- **Verified-only sub-population (236 states):**
  - C12 7/236 = 3.0% [1.4, 6.0].
  - C13 85.7% [48.7, 97.4] → ATTENUATED: the lower bound just misses 0.50, with 7 events.
  - C14 0/228 changed → REPLICATES.
  - C15 verdicts are the same as on the full set.
- **Post-hoc split** (the PREREG defines halves for A1 only), ranks 1–300 / 301–600:
  - C13 100% [70.1, 100] (9 events) → REPLICATES, vs 75% [30.1, 95.4] (4 events) → ATTENUATED;
  - C14 0/289 and 0/293 changed.
- **S2 B1** (separate stratum, `str_replace_editor`, 82 states):
  - C12 4/82 = 4.9% [1.9, 11.9], with **0 closer slips**. The four malformed calls are a YAML-style argument block
    inside `command`, `// comments` between arguments (2), and a bash command sent as `command`.
  - IPD has no slip site to repair in any of them, so C13 = 0% → FAILS by rule. Under IPD's strict policy these four
    fail loud: 0/82 delivered malformed vs 4/82 lenient (Holm p = 0.63).
  - C14 0/78 changed; C15 is NOT_ESTIMABLE (no slips).
- **C16 NOT_ESTIMABLE.** The frozen `confirm_gold.py` found **0** S1 B1 states whose logged first edit is a
  `new_string` closer slip with a later clean retry that matches the registered G1 rule (same `file_path`,
  `new_string` equal to the payload).
  - The documentation says this is not a missing-field artifact. CONTEXT_SCHEMA §3 lists `outcomes.raw_response_text`.
    P's `build_contexts.py` writes it from `raw_completion`, and P's `integrity.py` requires that field to be
    non-empty. `outcomes.jsonl` exists (17.5 MB).
  - Field presence was not checked by opening outcomes, per the PI's instruction (documentation and file existence
    only).
  - With base onset at 2.2%, only about 13 slips are expected before the retry-match filter.
- **Reading.**
  - On P's fresh public corpus the first-edit closer slip is about 8× rarer than in the main-track logs (2.2% vs
    17.5–18.7%). It is lower than D's transported prediction.
  - Where slips occur, IPD repairs all 13 and never alters a valid call (0/582).
  - The decoder-ranking claims about the baselines do not transport to T = 1.0. Retry mostly succeeds, greedy mostly
    repairs, and grammar-constrained decoding still silently corrupts 77% of slips.
  - B's part of "the fixes replicate" (C13 and C14) holds on the full sample. C5/C4 are A's.

## 8. Proxy equivalence: the SHIPPED proxy vs the reference decoder (PI job, 2026-11-04 18:15 UTC)
Workstream E ships IPD inside its OpenAI-compatible proxy (`experiments/endtoend/proxy/e2e_proxy.py`, cfgs `ipd`
and `fullp`). E's implementation is a **decode-time** variant. It stops generation at look-alike-closer stop
strings (`<closer>[\n],<key>:`, `<closer>[\n]}<tool_call|>`), confirms the slip with one sampled token (the opener of
the next value), and picks the cut with B's noisy-channel rule (pinned copy of the closer prior). It then inserts
`<|"|>`, keeps the model's `,KEY:` and resumes. A post-hoc text-only repair (`intent_parse_args`) handles calls that
are still malformed. B's reference is **post hoc**: generate the whole call, return it unchanged if it is strictly
valid, and otherwise roll back to the first slip site. All numbers: `out/proxy_equivalence.json`; code:
`proxy_equivalence.py`. E's code is used read-only from a hash-verified copy (`proxy_vendor/VENDOR_MANIFEST.txt`;
pre-fix `e2e_proxy.py` sha256 `0c2a5278…`).

### 8.1 Identical generations, CPU (pre-fix code)
The proxy's logic was replayed on the 595 identical gate generations of §4.2. The logged next token stands in for
the proxy's confirmation sample. The cut decision uses B's logged likelihoods.
- **Valid calls:** 480/480 pass byte-identical.
- **Closer slips (104):**
  - 100 are cut at decode time. On all 100 the slip site, candidate cut set, closer-prior values and chosen cut
    agree with B.
  - 2 slips with no visible closer are repaired post hoc, with arguments byte-identical to B's IPD output.
  - 1 unterminated last argument is delivered by vLLM's lenient parse with the same arguments as B's repair.
  - **1 is missed (finding F1):** the slip is written `<closer>, old_string:`, with a space after the comma. No stop
    string matches it. The post-hoc repair then delivers `old_string` with the leaked text `` `, new_string: `` and
    no `new_string`. In C's corpus 50/3,209 base-31B edit slips with a closer pattern (1.6%) have this whitespace
    form. B's relaxed grammar accepts `[ws] , [ws] KEY [ws] :`.
- **Prompt rendering:** the proxy's render matches the logged prompt length on 600/600 gate contexts. B's discovery
  render matches on 0/600; see §3.1.

### 8.2 P1 byte identity on valid calls (finding F2)
Each of the 229,414 valid QuoteStorm calls (§4.7; both key orders; 1,200 adversarial literals) was replayed through
E's **real request path**, `Proxy.engine_chat`, with a teacher-forced stub backend. A call counts as changed if the
proxy's raw text or the delivered arguments differ.

| code | cfg | natural calls changed | adversarial calls changed |
|---|---|---|---|
| reference (B) | — | 0/228,212 | 0/1,200 |
| proxy pre-fix | ipd | 0/228,212 (Wilson upper 0.0017%) | **278/1,200 = 23.2% [20.9, 25.6]** |
| proxy pre-fix | fullp | 0/228,212 | **278/1,200 = 23.2% [20.9, 25.6]** |
| proxy post-fix (final files) | ipd | 0/228,212 | **0/1,200** (Wilson upper 0.32%) |
| proxy post-fix (final files) | fullp | 0/228,212 | **0/1,200** (Wilson upper 0.32%) |

- 184 of the 278 changes are decode-time cuts. A literal value that ends in `` `,old_string: `` right before the
  true closer looks exactly like a slip at decode time, because the next token `<|"|>` reads as the next value's
  opener (P4).
- The other 94 come from the post-hoc path. `classify_args` flags the literal as a leak, and `intent_parse_args`
  then splits a valid call.
- **E's fix is verify-then-repair, mirroring (i+).** There are no decode-time stops. Every call runs to its end and
  goes through B's `is_valid` (vendored byte-identical, `vendor_b_gemma_protocol.py` = B's frozen
  `gemma_protocol.py`). A strictly valid call is delivered byte-identical. Otherwise the proxy applies B's
  `first_violation` (rules closer + opener; sites in undeclared keys are skipped), the noisy-channel cut, truncation,
  `<|"|>` and resume, for up to 4 rounds. The same guard sits in front of the post-hoc repair and of quarantine.
- **Post-fix files**, sha256: `e2e_proxy.py` a7e62cc1…, `gemma_protocol.py` 7ee13396…,
  `vendor_b_gemma_protocol.py` b8dac830…, `quarantine_renderer.py` 5ca5c62c…, `configs.json` 329f0bcf…,
  `channel_prior.json` bb48bb9a…. They are listed in `proxy_vendor_fix/VENDOR_MANIFEST.txt` and equal E's
  `acceptance/final_code_sha256.txt`. An intermediate renderer, 6b08b6e9…, also gave 0/229,412.
- **Post-fix CPU plan check on the 595 identical gate generations:**
  - valid calls → 0 plans (480/480);
  - slips → 104/104 planned, with the same violation kind and the same candidate cuts as B; the chosen cut on B's
    logged likelihoods is the same in 101/101 multi-cut cases, with the same prior;
  - the whitespace slip (F1) is now caught;
  - the opener-drift call is planned as in B, and the undeclared-key call is left alone.

### 8.3 Identical generations with the model in the loop (31B on :8302)
`proxy_equivalence.py tfe` sends each state through E's real `Proxy.engine_chat`, using a hybrid backend:
- requests whose token prefix matches the logged generation are answered from the log, so the proxy sees exactly
  the generation B's reference saw;
- likelihood scoring and every resumed generation after a cut go live to the 31B server;
- the proxy's seed is the request seed (0 on the gate). B's resume used seed + 1000, so regenerated suffixes are
  independent samples.

| set | code | valid calls byte-identical | slips intervened | cut = B's cut | delivered clean on slips (B) | all calls: delivered malformed (B loud) |
|---|---|---|---|---|---|---|
| gate, 595 calls / 104 slips | pre-fix | 480/480 | 102/104 | 100/100 decode-time | 103/104 (102/104) | 5/595 (12/595) |
| gate, 595 calls / 104 slips | post-fix | 480/480 | 104/104 | **104/104** | 101/104 (102/104) | 5/595 (12/595) |

| set | code | exact intent, proxy | exact intent, B's IPD (same states) | discordant states |
|---|---|---|---|---|
| G1, 229 gold states | pre-fix | 227/229 | 227/229 | 0 |
| G1, 229 gold states | post-fix | **227/229** | 227/229 | 0 |

- **Post-fix residuals on gate slips (3):**
  - 2 resumed generations degenerated into a run of `<|"|>` tokens under heavy server load, so no call was
    delivered. Re-running the same 2 states (same seed, lighter load) delivered calls byte-identical to B's repairs.
    The difference is vLLM batch nondeterminism.
  - 1 sample closed the call without `old_string` after the cut. B's sample of the same state wrote it.
  - A second post-fix pass, stopped at 20/104 slips to protect the server's KV cache, reproduced the first pass
    exactly: same cut, same delivered arguments 20/20.
- **Policy difference.** A residual invalid call is delivered leniently (malformed) by the proxy and fails loud in B.
  Over all 595 gate calls this gives 5 delivered-malformed calls for the proxy versus 12 loud errors for B.
- **Pre-fix only:** the whitespace slip (F1) is delivered malformed.

### 8.4 Live HTTP runs (600 gate contexts through the running proxy)
Post-fix proxy on port 8461, June template, backend :8302. Cfgs base, ipd and fullp. Seed 0, T 0.2, top-p 0.95,
max_tokens 6,144, no thinking budget, as in the gate. All three cfgs completed 600/600 contexts between 20:01 and
21:49 UTC. The proxy renders the log-faithful prompt, so the base arm also measures the render caveat of §3.1.

| arm (first call of the turn) | edit calls | closer slips (B detector, raw) | census-malformed delivered (B criterion) | contexts with an IPD repair |
|---|---|---|---|---|
| gate, B reference, natural calls (for comparison) | 406 | 63/406 = 15.5% | base 67/406 = 16.5% [13.2, 20.4] → after B's IPD 4/406 = 1.0% [0.4, 2.5] | — |
| proxy `base` | 404/600 | 65/404 = 16.1% [12.8, 20.0] | 67/404 = **16.6% [13.3, 20.5]** | — |
| proxy `ipd` | 410/600 | 0/410 | **1/410 = 0.2% [0.0, 1.4]** | 72 (75 repairs) |
| proxy `fullp` | 403/600 | 0/403 | **1/403 = 0.2% [0.0, 1.4]** | 64 (66 repairs) |

- **The baseline matches the gate.** The live base arm has 16.6% census-malformed first edits on log-faithful
  prompts, against 16.5% in B's natural-call gate on prompts 1 token short. So the render caveat has no measurable
  effect.
- **Delivered malformed edits, unconditional per context:** 67/600 = 11.2% under `base` and 1/600 = 0.2% under `ipd`
  or `fullp`. That is a relative reduction of **98.5%** (context bootstrap 95% [95, 100]). B's reference gives 94.0%
  [85.6, 97.7] on the gate's natural calls, and the intervals overlap.
- **The one residual** (the same context in `ipd` and `fullp`) has a quote followed by the key with **no comma**:
  `click.echo(", "old_string:`. That is not a slip site under B's grammar either, and in B's gate replay the same
  context failed loud.
- **Byte identity live.** `base` and `ipd` share the seed and the prompt, but only 267/528 (50.6%) of the
  intervention-free pairs are byte-identical. vLLM's seeded sampling is not batch-invariant over multi-thousand-token
  thinking generations, so live pairing cannot test P1. P1 is established by the teacher-forced tests in §8.2
  (0/229,412) and §8.3 (480/480).

### 8.5 Verdict
- On identical generations, the shipped post-fix proxy makes the same decisions as the reference decoder on every
  gate slip: site, candidates, prior and chosen cut agree on 104/104. It leaves all valid calls byte-identical: 480/480
  gate calls and 0/229,412 QuoteStorm calls changed, including 0/1,200 adversarial ones.
- On the 229 gold states it recovers exactly the same intents: 227/229, with 0 discordant states.
- Live, it removes 98.5% of delivered malformed first edits, matching the reference's discovery effect.
- The remaining difference is a policy, not a decoder difference: a residual invalid call is delivered leniently by
  the proxy and fails loud in the reference.
- Both pre-fix findings (F1 whitespace variant; F2 no byte identity on adversarial literals, 23.2%) are fixed in the
  post-fix files listed above.

## 9. PREREG_v2.4: injected-slip repair battery on public states (gold known by construction)
The prereg is `paper/protocol_theory/prereg/PREREG_v2.4_injectedSlipRepair.md` (sha256 e7af894b…). B's pre-data
operationalisations are entries 1–13 of `PREREG_DEVIATIONS.md`. The frozen package is
`v24/FREEZE_MANIFEST.txt` (sha256 7c18f256…), with analysis 25a5d20c… and runner 08bf695d….

**Design.**
- **Calls:** 600 strictly valid `edit_file` calls from P's public S1 corpus, each with tool result `ok`, from 458
  episodes. They were taken in sha256 rank order with seed 20261105, at most 2 per episode and at most 40% per repo.
- **Injection:** the logged thought and call are teacher-forced up to the closing `<|"|>` of `new_string`. That
  delimiter is replaced by one of four closers, 150 states each: BT `` ` ``, DQ `"`, EQ `\"`, TB ```` ``` ````. The
  31B QAT-ct then continues live at P's sampling (T 1.0, top-p 0.95, top-k 64), with one seed per state.
- **Arms:** seven decoders run on the identical slipped prefix, using B's frozen code (`confirm/`).
- **Run:** :8300 (GPU0), 2026-11-05 12:42–14:38 UTC, 600/600 states, 0 errors. `v24/run_manifest.json` records
  `/v1/models` and the server's command line.
- **Estimates:** strata are reweighted to the natural closer mix (BT 0.865, DQ 0.082, EQ 0.037, TB 0.016). Single rates
  use Wilson at the Kish effective n; contrasts use an episode-cluster bootstrap with B = 4,000.

**Injection mechanics** (ITT, reweighted), i.e. what the model wrote right after the injected closer:
- **slip pattern** (the closer is followed by the next key): 81.6% [75.6, 86.4];
- **doubling** (the model also writes `<|"|>`): 14.6% [10.3, 20.1];
- **content continuation** (the model keeps writing `new_string` content): 3.8% [1.9, 7.5].

EQ (`\"`) is mostly undetectable: 70 doubling and 57 continuation out of 150. The detectable subset (the emission is
strictly invalid) is 393/600 states: BT 136, DQ 73, EQ 60, TB 124.

**Detectable subset, reweighted.** Outcomes are judged against gold. Each cell is the share of detectable slips.

| arm | exact intent | silent corruption | delivered-malformed | loud | other valid | `new_string` exact |
|---|---|---|---|---|---|---|
| **IPD (i+)** | **90.6% [85.4, 94.1]** | 6.9% [4.0, 11.6] | 0.1% | 0.8% | 1.6% | 92.8% |
| T1 text-only | 83.6% [77.4, 88.3] | 9.1% | 0.0% | 2.4% | 4.9% | 88.5% |
| lenient | 0.0% | 1.1% | 98.9% | 0 | 0 | 0.0% |
| fail-loud | 0 | 0 | 0 | 100% | 0 | 0 |
| grammar-CD | 0.0% | 3.1% | 96.9% | 0 | 0 | 0.0% |
| retry ×2 (T 1.0) | 65.3% | 4.5% | 0 | 0.8% | 29.5% | 66.8% |
| greedy | 69.0% | 4.1% | 0.7% | 0 | 26.2% | 69.1% |

- **IPD vs T1:** **IPD BEATS T1**. Exact intent is +7.0 pp [+3.2, +11.2] higher, Holm p = 0.003. The secondary,
  unadjusted contrasts point the same way:
  - composite closers (EQ + TB): +10.3 pp [+5.7, +15.4];
  - `new_string` exact on composite closers: +4.3 pp [+1.2, +7.8];
  - BT: +6.6 pp [+2.2, +11.5].
- **Holm family F-R** (12 tests):
  - IPD has higher exact intent than each of the 6 baselines (all Holm p = 0.003).
  - None of the 6 "IPD has less silent corruption" tests is significant. Under the pre-declared outcome order, the
    baselines' damaged calls count as delivered-malformed or loud rather than silent.
- **Rules R1–R8:**
  - R1 (IPD exact ≥ 0.85, CI_lo ≥ 0.75), R2, R5 and R6 **REPLICATE**.
  - **R3 FAILS:** IPD's silent corruption is 6.9%, against ≤ 2%. In 27 of the 28 cases one injected look-alike
    character is left at the end of `new_string`.
  - **R4 FAILS:** grammar-CD's silent share is 3.1%, against ≥ 0.80. This follows from B's pre-declared order, which
    checks "malformed under A's/E's judge" before "silent".
    - Exploratory: 393/393 grammar-CD outputs on detectable slips are strictly valid but wrong, with the look-alike
      `,key:` residue inside the value. Under a silent-first order they would all be silent corruption, as in discovery.
  - **R7 and R8 FAIL:** retry ×2 reaches 65.3% exact and greedy 69.0%. The injected states were valid originally, so
    resampling from the call head often reproduces the gold call.
- **ITT** (all 600):
  - IPD exact intent 77.8%, T1 71.9%.
  - Every parser-based arm carries 15–22% silent corruption, driven by doubling and continuation, which no decoder can
    detect.
- **Cost per state:**

  | arm | tokens | latency |
  |---|---|---|
  | IPD | 139 | 63 s |
  | the live emission alone (T1, lenient and fail-loud add nothing to it) | 94 | 29 s |
  | retry ×2 | 219 | 67 s |
  | greedy | 200 | 59 s |
- **Files:**
  - `v24/battery_inputs.jsonl` (f5c7839e…) and `v24/battery_manifest.json` (366ab3da…);
  - `v24/battery_run.jsonl` (ce230afc…);
  - `v24/battery_run_analysis.json` (8c97e05f…) and `v24/battery_run_analysis_states.jsonl` (16af4c7a…).

## 10. PREREG_v2.5: the full slipguard stack vs the stock stack on public states
The prereg is `paper/protocol_theory/prereg/PREREG_v2.5_stackGain.md` (sha256 50f8a395…). B's deviations are entries
1–6 of `PREREG_DEVIATIONS.md`.

**What was frozen.** `v25/FREEZE_MANIFEST_v25.txt` (2f0c667b…) holds:
- the glue `v25/stack_runner.py`: 21db9d7d…, replaced by d3440af4… after an operational fix (deviation 6: the P8a
  replay built A's prompts in a worker thread);
- the analysis `v25/analyze_v25.py` (b9cc42d2…), run once;
- slipguard and A's scripts, with hashes as registered.

**Pre-run CPU checks** (all passed):
- N1: HistoryGuard leaves the P0 histories unchanged on 300/300.
- HistoryGuard(P1) renders identically to A's P8a context on 300/300.
- I2: the native-results inverse of O1 renders identically to O0 on 600/600.
- Template check: 300/300. With thinking on the two templates are identical. With thinking off the guarded template
  equals the official one plus `<|channel>thought\n<channel|>` (ids 100, 45518, 107, 101).

**Run.** A confirmed the replay preconditions, so the switch rule was not triggered. Everything ran on :8300 (GPU0),
2026-11-05 14:40–15:44 UTC: F3, then the replays of C1 P8a, C1 P0 and v2.3 O0, then L1 live, then F2 live.

| family | STOCK | SLIPGUARD | test (Holm) | verdict |
|---|---|---|---|---|
| **F1** contaminated history (A1, 300; R1 replay primary) | harmful 59/300 = **19.7%** [15.6, 24.5] | **0/300** [0, 1.3]; loud 5/300 = 1.7% | McNemar 59–0, p_Holm 5e-18; reduction **100%** [100, 100]; RD −19.7 pp [−24.5, −15.2] | **GAIN WITH HARM** (the N2 rule fails on 1 case; see below) |
| F1, L1 live (secondary) | — | 0/300; loud 6/300 = 2.0% | consistent with R1 | — |
| **F2** ADK/LiteLLM serialization (600; O0 replay primary) | drift 19/350 edits (5.4%); closer slips 6/600 | drift **0/348** edits; closer slips **0/600**; loud 6/600 | H2a: 19–0, p_Holm 4e-6. H2b: 6–0, p_Holm 0.016 | **DRIFT REMOVED**; closer slips **REMOVED** |
| F2, live first 100 (secondary) | — | drift 0/56 edits; closer slips 0; loud 1 | — | — |
| **F3** thinking-off leak (300) | thought opened 296/300 = **98.7%** | guarded **1/300 = 0.3%** [0.1, 1.9] | McNemar 295–0, p_Holm 6e-89 | **THINKING-OFF HONOURED** |

**No-harm checks:**
- N1: 300/300.
- N3: SLIPGUARD P0 harmful 0/300 vs STOCK 4/300. RD −1.3 pp [−2.7, −0.3] → holds.
- N4: P0 loud 4/300 = 1.3% [0.5, 3.4], below 2%.
- Parser disagreements (slipguard strict vs B's `is_valid`): 0.
- **N2: 1 violation in 1,500 samples.** It is in the F2 O0 replay, `sphinx-doc__sphinx-8595__S1:12`.
  - The base call's last argument is closed by a backtick: `old_string:<|"|>…if not self.__all__:` followed by
    `` ` `` and `}`. vLLM's lenient parse would deliver `old_string` with a stray backtick, and A's judge does not flag
    that.
  - IPD repaired it to the strictly valid intended call.
  - The registered rule allows interventions only at calls A's judge flags, so N2 fails and the frozen F1 verdict is
    **GAIN WITH HARM**. That means no gain sentence under the prereg.
  - Substantively this is a true end-slip that the judge cannot see. It is not an alteration of a valid call: the base
    call was strictly invalid.

**Sensitivity analyses:**
- Excluding the budget-forced records (C1 P8a 1; O0/O1 8) changes nothing: F1 59→0 of 299; F2 drift 19→0 and closer
  slips 6→0 of 592.
- Live and replay agree: L1 at 0/300 lies inside R1's CI.

**Files** (all under `v25/out/`):
- `cpu_checks.json` 2c461808…;
- `f3.jsonl` 56e58214…;
- `replay.jsonl` 46e57811…;
- `live_l1.jsonl` 556b0af6…;
- `live_f2.jsonl` 81b98c6e…;
- `analysis_v25.json` d0a6f6e2…;
- `replay_attempt1_errors.jsonl` 984879ca…, the 300 failed first-pass P8a records, kept for the audit.

## 11. PREREG_v2.5b: the same stack on Gemma-4-E4B (F1, R1 replay only)
The prereg is `paper/protocol_theory/prereg/PREREG_v2.5b_stackGainE4B.md` (sha256 c78e7512…). B's entries 1–5 are in
`PREREG_DEVIATIONS.md`.

**Code.**
- Glue: `v25b/stack_runner_e4b.py` (f3e4d7ae…), the v2.5 glue with paths only changed.
- Analysis: `v25b/analyze_v25b.py` (c1569986…), the v2.5 analysis restricted to F1/R1, with H1-E4B alone at α = 0.05.
- Both were frozen before any outcome was opened.

**Preconditions** (all held, so no switch rule fired):
- Re-render length equals the logged length for P0, P1 and P8a, 300/300 each.
- Stop id 49 only. One budget-forced record, in P1.
- HistoryGuard(P1) renders identically to A's E4B P8a context, 300/300.
- N1 holds, 300/300.
- :8311 is the same server process that served A's E4B run, so no record is a cross-server resume.

**Run.** The IPD resumes ran on :8311 (≤ 8 requests in flight) at about 21:14 UTC: 600 replays, 17 IPD interventions,
about 1 GPU-minute.

**F1 on E4B (300 states):**
- Harmful next edits fall from 21/300 = **7.0%** [4.6, 10.5] to **0/300** [0, 1.3].
- Exact McNemar 21–0, p = 4.8e-7. Relative reduction **100%** [100, 100]; RD −7.0 pp [−10.0, −4.3].
- Loud refusals: 2/300 = 0.7%.
- The sensitivity analysis excluding the budget-forced record gives the same result.

**No-harm checks:**
- N1 holds.
- N3 holds: P0 harmful falls from 7/300 to 0/300, RD −2.3 pp [−4.1, −0.7].
- N4: P0 loud is 3/300 = 1.0%.
- Parser disagreements: 0.
- **N2 fails: 3 violations in 600 samples.** Each is an IPD intervention on a strictly invalid call that A's judge
  does not flag:
  - `pydata__xarray-3976__S1:37` (P0): `old_string` opened with a Python `"""`;
  - `pytest-dev__pytest-7186__S1:8` (P8a): both strings opened and closed with `"""`;
  - `sympy__sympy-13840__S1:28` (P8a): the last argument is closed by `}` with no delimiter.

  In every case IPD's output is strictly valid and carries the intended content. No valid call was altered.

**Verdict, as frozen: GAIN WITH HARM.** No cross-size claim is made, and the result goes to the limitations. As in
v2.5, the gain itself is unambiguous. The verdict is set by the N2 rule, which counts any repair of a protocol
violation that the registered judge does not see (opener drift, unterminated last argument) as a violation.

**Files:**
- `v25b/out/analysis_v25b.json` 49f19530…
- `v25b/out/replay.jsonl` b695c6cb…
- `v25b/out/cpu_checks.json` 2c461808…
- `v25b/out/preconditions_e4b.json` 3c422c2c…
