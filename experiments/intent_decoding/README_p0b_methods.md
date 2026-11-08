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
