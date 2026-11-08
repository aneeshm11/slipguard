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

