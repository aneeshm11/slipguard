# Workstream F: quantization margins at structural tokens (Gemma-4-31B QAT-ct vs bf16)

**Question.** Does the served `gemma-4-31b-it-qat-w4a16-ct` checkpoint shrink the probability margin of the true string
delimiter `<|"|>` against look-alike closers (backtick, quote variants) at the decision points of the escape-free Gemma-4
tool-call format, compared with the bf16 original (`google/gemma-4-31b-it`)? And does that show up as more slips?

## TL;DR
1. **At the end of a code string, the served QAT-ct checkpoint closes with a look-alike about 3.7× more often than bf16.** Both were measured on identical real states.
   - Expected slip probability: **10.1% [8.6, 11.9] vs 2.7% [1.9, 3.9]**.
   - The probe reproduces the logged slip rate (9.2%) and the logged log-probs (median |Δ| 1e-5 nats).
2. **Behaviour agrees** (order replay, 556 contexts):
   - Onset, clean history: 10.5% vs 2.5% (bf16/QAT = 0.235, identical to the teacher-forced R_onset = 0.235 [0.19, 0.29]).
   - Once a corrupted call is in the history, the gap narrows: natural histories 64.8% vs 50.7% (0.78 [0.64, 0.93]); one injected call 45.7% vs 22.2% (0.49 [0.41, 0.57]; 396 contexts).
   - **Teacher-forced R (bf16/QAT-ct, importance-weighted): onset R = 0.256 [0.21, 0.31] vs post-slip R = 0.828 [0.78, 0.87]** (n = 440 / 289 states).
   - Against the pre-registered "≈ 1": after a corrupted call, bf16 imitates it almost as much as QAT-ct, but not entirely (the CI excludes 1). The honest reading is that the contagion is mostly, not entirely, history-borne.
3. **Decomposition (adopted wording).**
   - **4-bit Q4_0 weights raise the closer-slip probability at the decision point about 4× vs bf16. This holds for plain PTQ and for Google's QAT, in any export.**
     - PTQ-Q4_0 of the original: 11.6% [8.4, 15.2], 4.25×.
     - QAT checkpoint: 11.0% unquantized, 8.8% on the true Q4_0 grid, 10.1% as the -ct export.
   - **QAT recovers little:** greedy slips are about 45% lower than PTQ (6.4% vs 11.6%, −5.2 pp [−9.4, −1.3]), and the expected-probability difference is not significant (−2.9 pp [−6.4, 0.5]).
   - **The -ct export adds a small, non-attributable +1.4 pp** [0.1, 2.7].
   - **Google's "unquantized" QAT release already behaves quantized:** 61% of its weights sit on the Q4_0 grid, and its matrices are shrunk (norm ratio 0.60–0.87).
4. **Where this matters.** These numbers explain why the proxy/IPD guard matters most for quantized deployments.
   - 4-bit weights shrink the structural-token margin: at valid `new_string` ends the margin falls from a median of 12.2 nats (bf16) to 6.6–7.6 nats.
   - Closers within 2 nats of a look-alike: about 15–17% vs 3%.
   - The QAT embedding-norm equalisation is a secondary contributor (arm 6), neither necessary nor sufficient.

## Results (2026-11-04)

Unless stated otherwise, every number below is paired on identical states and token ids: 639 states, 1,037 decision positions. Brackets are 95% CIs.

### 1. The quantized checkpoint is about 3.7× more likely to close a code string with a look-alike
**Decision point: end of `new_string`, clean history, population-weighted.** This estimate is unbiased under the null "QAT = bf16".

| | QAT-ct (served) | bf16 original |
|---|---|---|
| Expected slip probability at the logged temperature | **10.1% [8.7, 11.8]** | **2.7% [1.9, 3.9]** |
| Greedy decision is a slip, this model only | 6.6% [5.4, 8.3] | 0.5% [0.0, 1.3] |

- The ratio QAT / bf16 is **3.7× [2.5, 5.4]**.
- Validation: the QAT estimate reproduces the observed slip rate of the same population in the logs, **9.2% [8.5, 10.0]** (534/5,808).
- The state sample is 440 onset-slip states and 186 valid closers, re-weighted to the 534 : 5,274 population frequencies within each temperature stratum.

### 2. Margins at valid closers are systematically smaller under QAT-ct
The margin is log P(`<|"|>`) − log P(best look-alike), in nats.

| Closer (valid calls, n = 186 each) | QAT median | bf16 median | Share of states with smaller QAT margin | Margin < 2 nats, QAT vs bf16 |
|---|---|---|---|---|
| end of `new_string` | **6.6** | **12.2** | 95.4% [91.2, 97.7] | **15.1% [10.6, 20.9] vs 3.2% [1.5, 6.9]** (McNemar 23 vs 1, p = 3e-6) |
| end of `old_string` | 14.9 | 17.3 | 95.8% | 1.1% vs 0% |
| end of `filepath` | 14.5 | 18.8 | 100% | 0% vs 0% |

- Margin < 4 nats at the end of `new_string`: 30.6% [24.5, 37.6] vs 6.5% [3.7, 10.9] (McNemar 45 vs 0).
- P(look-alike) at the logged temperature at valid `new_string` ends: 2.8% [1.3, 4.6] vs 0.9% [0.0, 2.3].
- **Valid states were selected because QAT emitted `<|"|>`.** That bias works *against* finding QAT worse.

### 3. At the logged onset slips, bf16 usually would not have slipped
379 states where the closer is a whole token.
- The look-alike is the greedy top-1 in **80.5% [76.2, 84.2] for QAT vs 18.2% [14.6, 22.4] for bf16**. In 192 states QAT's top-1 is a look-alike while bf16's is `<|"|>`; the reverse happens once. McNemar for "top-1 is a look-alike": 238 vs 2, p = 3e-68.
- P(look-alike) at the logged temperature: 77.8% vs 19.5%.
- log P(logged slip token), QAT − bf16: **+4.11 [3.79, 4.44] nats**. The same quantity for `<|"|>` is −0.93.
- These differences are inflated by selection: the states were chosen because QAT slipped there. §1 is the unbiased summary.
- The slip states are still intrinsically risky for bf16. The AUC of [log P(look-alike) − log P(`<|"|>`)] for separating slip states from valid closers is **0.78 [0.75, 0.81]** for bf16. For QAT it is 0.985, but that value is tautological because QAT generated the samples.

### 3b. R_onset vs R_post (teacher-forced, PI P0-F)
R = E[s_bf16 / s_QATct | QAT-ct slipped] = Σ p(x) s_bf16(x) / Σ p(x) s_QATct(x). Here s is the slip probability under the logged sampler, and the slip states are the logged QAT-ct slips.

| States | n | R (bf16 / QAT-ct) | Whole-token closers only | Mean s_QAT-ct | Mean s_bf16 | Look-alike is top-1: QAT-ct vs bf16 | Δ log P(slip token) |
|---|---|---|---|---|---|---|---|
| onset (clean history) | 440 | **0.256 [0.21, 0.31]** | 0.235 [0.19, 0.29] | 0.78 | 0.22 | 80.5% vs 18.2% | +4.11 [3.79, 4.44] |
| post-slip (≥1 malformed edit in history) | 289 | **0.828 [0.78, 0.87]** | 0.812 [0.76, 0.86] | 0.98 | 0.82 | 99.1% vs 81.1% (McNemar 42 vs 0) | +0.64 [0.45, 0.85] |

- The QAT-ct post-slip probes ran on a dedicated QAT-ct server on GPU3 (:8303, same flags as :8300).
- Cross-server noise floor on 219 positions: top-1 agreement 97.3% [94.2, 98.7], |Δ log P| median 0.003, |Δ margin| median 0.13 nats, |Δ P(look-alike)| mean 0.015.
- D's `t5_quant_check.py` reproduces both values: onset 0.235 [0.19, 0.29], post-slip 0.812 [0.76, 0.86].
- The behavioural analogues agree: natural-history replay 0.78 [0.64, 0.93]; a single injected call 0.49 [0.41, 0.57] (396 contexts).

### 4. Mechanism: a generically heavier tail plus a look-alike-specific excess where code strings end
QAT-ct is less peaked at every structural position: its 20th-ranked log-prob is +3.9 to +6.0 nats higher. Paired shifts in log P (QAT − bf16):

| Position | Best look-alike | Best other non-`<|"|>` token | Look-alike excess |
|---|---|---|---|
| end of `new_string` (valid) | +5.31 | +2.29 | **+3.02 [2.40, 3.67]** |
| onset slips | +3.38 | +0.98 | **+2.40 [2.05, 2.75]** |
| end of `old_string` | +3.27 | +3.17 | +0.10 [−0.38, 0.61] (generic) |
| end of `filepath` | +4.86 | +7.64 | −2.78 (generic) |

So the 4-bit checkpoint has a heavier tail everywhere (plain PTQ to Q4_0 reproduces the shift, §6). Where a code string ends, it additionally favours the look-alike closers. Only there are the bf16 margins small enough, a few nats in the lower tail, for the shift to flip decisions.

### 5. Behavioural replays (same contexts, each model generating its own trajectory)
**Order-replay natural arm.**
- 556 paired Gemma-authored contexts, July template, thinking on, T = 0.2, seed 0, two-stage think→call.
- QAT reference: `data/protocol/order_31b_think.jsonl`.
- Censored: 10 pairs (bf16 cap, or QAT total above the cap).

| History of the context | QAT-ct malformed | bf16 malformed | bf16 / QAT | McNemar (QAT-only vs bf16-only) |
|---|---|---|---|---|
| clean (n = 485) | 10.5% [8.1, 13.6] | 2.5% [1.4, 4.3] | **0.235 [0.12, 0.37]** | 42 vs 3, p = 9e-10 |
| ≥1 malformed edit already in history (n = 71) | 64.8% [53.2, 74.9] | 50.7% [39.3, 62.0] | **0.78 [0.64, 0.93]** | 12 vs 2, p = 0.013 |
| all (n = 556) | 17.4% [14.5, 20.8] | 8.6% [6.6, 11.3] | 0.50 [0.39, 0.61] | 54 vs 5, p = 2e-11 |

- At clean history, the behavioural bf16/QAT ratio equals the teacher-forced importance-weighted ratio R_onset = 0.235 [0.19, 0.29]. These are two independent measurements.
- Contagion ratio, P(bad | ≥1 bad in history) / P(bad | clean): **QAT 6.2× [4.5, 8.5], bf16 20.5× [12.1, 43.3]**.
- **Reading: the 4-bit checkpoint amplifies the onset (about 4×); once a corrupted call is in the history, both models imitate it at high rates (gap 0.78).** History drives most of the contagion, but the 4-bit checkpoint still adds to it (injection table below).
- Slip closers: backtick in 77 of 95 QAT slips and 39 of 46 bf16 slips.
- The QAT margin at the logged valid call predicts a slip in a fresh QAT replay of the same context with AUC 0.69 [0.53, 0.83] (n = 182, 14 slips). bf16 slipped only once in 195 replays, so its AUC is uninformative.

**Contagion injection, P0k0 (original history) vs P1k1 (one corrupted re-rendered edit plus the harness error).**
- Complete pairing: **all 396 contexts (322 attempts), both arms, both models; 0 censored.**
  - bf16 side: workstream A's script (snapshot), June template, logged temperatures.
  - QAT-ct side: A's rows from `r31b_heldout.jsonl` (202 contexts; P0/P1 rows only) and `r31b_old_*.jsonl` (194 contexts).
- The pairing is exact: every one of the 792 (context, arm) pairs has the same seed and the same prompt length in both models.
  - One judge (A's current `gemma_protocol.judge`) re-scores all 1,584 rows and reproduces the stored outcome in 792/792 rows per model.
  - 43 (context, arm) keys exist in two of A's files. All agree on the outcome; the `r31b_heldout` row is used.
- Outcome (primary, ITT): the next call is a malformed `edit_file`, over all contexts.
- Statistics: Wilson CIs for rates; attempt-cluster bootstrap (4,000 resamples) for differences and ratios; exact McNemar.

| Arm (n = 396) | QAT-ct | bf16 | RD bf16 − QAT | bf16 / QAT | McNemar (QAT-only vs bf16-only) |
|---|---|---|---|---|---|
| P0k0 | 3.8% [2.3, 6.2] (15) | 1.3% [0.5, 2.9] (5) | −2.5 pp [−4.6, −0.5] | 0.33 [0.08, 0.75] | 13 vs 3, p = 0.021 |
| P1k1 | **45.7% [40.9, 50.6]** (181) | **22.2% [18.4, 26.6]** (88) | **−23.5 pp [−28.3, −18.8]** | **0.49 [0.41, 0.57]** | 101 vs 8, p = 1e-21 |
| contagion effect P1 − P0 | **+41.9 pp [36.7, 47.0]** | **+21.0 pp [16.5, 25.4]** | DiD −21.0 pp [−25.8, −16.2] | | |
| ratio P1 / P0 | 12.1× [7.9, 21.6] | 17.6× [8.5, 86] | | | |

- Conditional on both models emitting `edit_file` (secondary):
  - P0k0: 4.5% vs 1.6% (n = 313).
  - P1k1: 52.5% vs 26.6% (n = 320); bf16/QAT 0.51 [0.42, 0.58].
- P(next call is `edit_file`): P0k0 87.1% vs 83.8%; P1k1 90.2% vs 83.3%.
- Stability across A's halves (P1k1 bf16/QAT; DiD):
  - gate half (194 contexts): 0.52 [0.41, 0.65]; −17.5 pp [−24.5, −10.5].
  - frozen held-out half (202 contexts; A analysed it once at 15:21 UTC before this pairing): 0.46 [0.35, 0.56]; −24.3 pp [−31.1, −17.7].
- The P1/P0 ratios have wide, overlapping CIs (bf16's P0 has only 5 events; on the held-out half its upper bound is unbounded). Report the risk differences, not the ratios.

**Reading.**
- After one injected corrupted call both models copy it heavily: relative contagion P1/P0 is 12× for QAT-ct and 18× for bf16.
- **QAT-ct is about 2× more susceptible in absolute terms:** +41.9 vs +21.0 pp; bf16/QAT 0.49 [0.41, 0.57] at P1k1.
- In natural histories, which often hold several corrupted calls, the gap narrows to 0.78 [0.64, 0.93]. At the logged post-slip states the teacher-forced R_post is 0.83 [0.78, 0.87].
- So contagion is mostly history-driven in relative terms. The pre-registered "R_post ≈ 1" is not supported: all three measurements exclude 1, and the 4-bit checkpoint still about doubles the slip rate after a single exposure.

### 6. QAT decomposition: training vs Q4_0 grid vs -ct export
**Arms.** All arms are probed on the same states.
1. bf16 original.
2. `google/gemma-4-31b-it-qat-q4_0-unquantized` (bf16).
3. Arm 2 fake-quantized to the true llama.cpp Q4_0 grid by `fakeq4_0.py`. It is unit-tested bit-exact against the ggml reference.
4. QAT-ct as served.
5. Optional: the bf16 original fake-quantized to the same Q4_0 grid, i.e. plain post-training quantization (PTQ).

**Contrasts.**
- 2 − 1: training.
- 3 − 2: Q4_0 grid.
- 4 − 3: -ct export vs grid.
- 3 − 5: QAT vs PTQ at the same grid.

**Weight-space facts** (`weight_grid_diag.py`; all 410 quantized Linear modules, 29.3B weights).
- The -ct export is a plain round-to-nearest (RTN) of the QAT-unquantized weights onto *its own* symmetric grid:
  - q_ct = round(W / scale_ct) for 98.8% of weights;
  - scale_ct / |d_Q4_0| = 1.067 = 8/7.5, i.e. absmax/7.5 instead of Q4_0's signed-max/−8.
- 61.2% of the QAT-unquantized weights sit exactly on the Q4_0 grid the QAT targeted. Only 11.7% sit on the -ct grid.
- Relative RMS error against the QAT weights: Q4_0 5.0%, -ct 6.7%; -ct against Q4_0, 8.2%.
- In short, the served export discards the grid the model was trained for.

**Results** (`out/results_decomp.json`; 1,037 identical positions; 440 onset-slip and 186 valid decision states; paired stratified bootstrap with 4,000 resamples).

| Arm | Expected slip probability (logged T) | Same at shipped default T = 1 | Greedy slip rate | Valid `new_string` closer: median margin; margin < 2 nats | Onset-slip states: look-alike is top-1 |
|---|---|---|---|---|---|
| (1) bf16 original | **2.7% [1.9, 3.9]** | 3.0% [2.2, 4.1] | 2.3% [1.7, 3.4] | 12.2; 3.2% | 18.2% |
| (2) QAT-unquantized (bf16 weights) | **11.0% [8.9, 13.4]** | 12.5% [10.5, 14.8] | 10.1% [7.6, 13.2] | 5.9; 17.7% | 69.1% |
| (3) QAT → true Q4_0 grid | **8.8% [7.1, 10.6]** | 10.7% [8.9, 12.7] | 6.4% [5.1, 8.2] | 6.6; 15.1% | 58.0% |
| (4) QAT-ct, as served | **10.1% [8.6, 11.9]** | 11.5% [9.9, 13.3] | 8.5% [7.3, 10.3] | 6.6; 15.1% | 80.5% |
| (5) bf16 → same Q4_0 grid (plain PTQ) | **11.6% [8.4, 15.2]** | 12.4% [9.2, 15.9] | 11.6% [8.2, 15.5] | 7.6; 17.2% | 42.7% |
| (6) bf16 + QAT embedding table only (mechanism) | 6.1% [3.8, 8.6] | 6.3% [4.3, 8.4] | 5.5% [3.1, 8.3] | 4.5; 30.1% | 17.2% |

| Contrast (expected slip probability, logged T) | Difference | Ratio | Share of the onset log-odds increase (4−1) | Attributable? (≥50%, CI excluding 0) |
|---|---|---|---|---|
| **training (2 − 1)** | **+8.3 pp [6.1, 10.8]** | **4.0× [2.7, 5.9]** | **1.07 [0.96, 1.20]** | **yes** |
| Q4_0 grid (3 − 2) | −2.3 pp [−3.8, −0.8] | 0.79× [0.69, 0.91] | −0.19 [−0.31, −0.07] | no |
| -ct export vs grid (4 − 3) | +1.4 pp [0.0, 2.7] | 1.16× [1.00, 1.34] | +0.12 [0.005, 0.23] | no |
| total (4 − 1) | +7.4 pp [5.5, 9.3] | 3.7× [2.5, 5.4] | total Δlogit 1.39 [0.98, 1.78] | |
| PTQ Q4_0 on original (5 − 1) | +8.9 pp [5.8, 12.3] | 4.25× [2.95, 6.23] | | |
| QAT vs PTQ at the same grid (3 − 5) | −2.9 pp [−6.4, 0.5] | 0.75× [0.56, 1.06] | (greedy slip rate: −5.2 pp [−9.4, −1.3]) | |
| QAT embedding table alone (6 − 1) | +3.3 pp [1.4, 5.6] | 2.2× [1.5, 3.3] | | |
| rest of the QAT weights given that embedding (2 − 6) | +4.9 pp [1.8, 8.0] | 1.8× [1.2, 2.9] | | |

Paired per-state shift of log-odds(look-alike vs `<|"|>`), in nats:

| Stage | Valid `new_string` closers | Onset slips |
|---|---|---|
| training | **+5.38 [4.95, 5.81]** | **+4.42 [4.15, 4.72]** |
| Q4_0 grid | −0.50 [−0.63, −0.38] | −0.64 [−0.71, −0.57] |
| -ct export | +0.10 [−0.12, 0.32] | +0.56 [0.44, 0.69] |
| PTQ Q4_0 on the original (5 − 1) | +4.40 [4.0, 4.8] | +3.44 [3.14, 3.72] |

**Behavioural check** (order-replay natural arm, 299 contexts where all four arms are available):

| History | (1) bf16 | (2) QAT-unq | (3) QAT→Q4_0 | (4) QAT-ct | Training 2 − 1 | Grid 3 − 2 | Export 4 − 3 |
|---|---|---|---|---|---|---|---|
| all | 9.0% [6.3, 12.8] | 19.1% [15.0, 23.9] | 17.1% [13.2, 21.7] | 17.4% [13.5, 22.1] | **+10.0 pp [6.4, 13.7]** (McNemar 32 vs 2, p = 7e-8) | −2.0 [−5.0, 0.7] (p = 0.26) | +0.3 [−3.0, 3.7] (p = 1) |
| clean history (n = 263) | 3.4% | 12.9% | 11.0% | 11.4% | +9.5 pp [5.7, 13.3] | −1.9 | +0.4 |
| ≥1 malformed in history (n = 36) | 50.0% | 63.9% | 61.1% | 61.1% | +13.9 pp [2.8, 25.0] | −2.8 | 0.0 |

**Conclusion (adopted wording, PI 2026-11-04).**
- **4-bit Q4_0 weights raise the closer-slip probability at the decision point about 4× vs bf16. This holds for plain PTQ and for Google's QAT, in any export.**
- **QAT recovers little:** greedy slips are about 45% lower than PTQ, and the expected-probability difference is not significant.
- **The -ct export adds a small, non-attributable +1.4 pp.**
- **Google's "unquantized" QAT release already behaves quantized** (61% of its weights on the Q4_0 grid; matrices shrunk). Within the 1→2→3→4 path, its "training" contrast therefore carries the whole increase under the pre-registered rule.
- Mechanism (arm 6):
  - QAT equalised the norms of the tied (un)embedding rows (all about 0.98; `<|"|>` ×0.84 vs `` `, `` ×0.97).
  - Swapping only that table into bf16 doubles the slip probability (2.2× [1.5, 3.3]).
  - The transplant is crude: closer margins elsewhere fall by 10–11 nats.
  - PTQ keeps the bf16 embedding and still reaches 4.25×, so the embedding is a contributor, neither necessary nor sufficient.
- For the paper: the "4-bit weights shrink the structural-token margin" section motivates the proxy/IPD guard, which matters most for quantized deployments.
<!-- DECOMP_RESULTS -->

## Method

**States.** These are real agent states from the main-track logs, which were read-only (`/harness/work/runs`).
- Gemma-generated runs only: `scan_logs.py` builds `data/edit_index.jsonl` (13,620 edit_file calls).
- The runs `t1_qwen`, `t2_qwen_rebench`, `t3_qwen_rebench` and `dsprobe` are excluded. They were generated by the Qwen3.8 and DeepSeek teacher models, which were served under the Gemma alias (§Validity).
- Thinking was on and each response held a single tool call.
- `build_dataset.py` writes `data/items_prio.jsonl`, 1,887 states:
  - **454 onset slips**: the first malformed edit of an attempt with a clean history, where `new_string` was closed by a look-alike followed by `,old_string:`.
  - **289 post-slip slips.**
  - **1,144 valid calls**: 1,121 with a clean history. 520 of them are exactly the logged calls at the replay contexts in `data/protocol/contexts.jsonl`.
- Prompts are rendered with the **main-track June-5 chat template** (`data/chat_template_maintrack.jinja`). The logs were produced with it; the downloaded models ship the 2026-07-09 template.
- Responses:
  - 183 states use the exact sampled token ids logged in `blp` (run `run-41`).
  - The rest use a canonical re-tokenisation of the parsed response. On blp lines, 94% of responses re-tokenise identically, and divergences are local.

**Decision points** (`positions` in the items file):
- the token that ends each string value (`close:filepath`, `close:new_string`, `close:old_string`), where the logged token is `<|"|>`;
- for slips, the position where the look-alike closer was emitted (`slip`). `boundary=False` marks the 12% of slips whose closer is merged into a token with preceding code;
- pass 2 (cancelled by the PI; probed only for a few early items): the next-key position (`key#1`, `key#2`) and the separator after each closer (`sep:*`).

**Teacher forcing without `prompt_logprobs`** (`probe_margins.py`):
- For every decision point the request is: prompt = context ids + response ids up to the position, `max_tokens=1`, `temperature=0`, `logprobs=20` (generation-mode log-probs), `return_tokens_as_token_ids`.
- Both models receive **identical token ids**.
- vLLM 0.19.1's `prompt_logprobs` path materialises an fp32 `[≤8192 × 262144]` log-softmax per chunk and bypasses the prefix cache. It crashed the E4B server, so it is not used.
- Prefix sharing:
  - bf16 (dedicated server): the first position of an item warms the prefix, then the remaining positions are sent together.
  - QAT (shared, queued servers): all positions are sent together, so they sit adjacent in the queue and share prefix blocks.
- Sampling distributions are rebuilt from the top-20 with the main-track settings: temperature (logged T = 0.2 or 0.7) → top-k 64 → top-p 0.95. They are exact whenever the nucleus lies inside the top-20; the residual mass is reported.
- **Look-alike set**: the 80 vocabulary tokens made only of backtick, quote and backslash characters, optionally with a leading `▁` or a trailing `,` (`qm_common.lookalike_ids`). Examples: `` `, `` (8347), `` ` ``, `",`, `"`, `\",`, `',`, `""",`.

**Servers.**
- QAT-ct: `:8300` and `:8302` (vLLM 0.19.1, shared).
- bf16: `:8304`, text-only (`Gemma4ForCausalLM`), util 0.97, **KV cache 17,408 tokens**.
  - Every bf16 request is kept at or below 16,400 tokens. 1,854 of 1,887 states fit.
  - vLLM never schedules a request that cannot fit, and that request head-of-line-blocks the whole first-come-first-served queue. This was observed at 10:11 UTC on the first bf16 instance, which had 13,136 tokens of KV.
- The same 16,400 cap is applied to the QAT side, so every comparison is **paired on identical (item, position) states**.

**Behavioural replays (bf16 vs QAT on identical contexts).**
- Order-replay natural arm (`order_replay_capped.py`, a capped copy of `experiments/protocol/order_replay.py`):
  - same July template, T = 0.2, top-p 0.95, seed 0, two-stage think→call;
  - 633 Gemma-authored contexts;
  - QAT reference: `data/protocol/order_31b_think.jsonl`.
- Contagion injection P0k0 (original history) vs P1k1 (one corrupted, re-rendered edit plus the harness error):
  - run with workstream A's script (snapshot `snapshots/contagion_scripts_1020/`) on the 396 of its 600 contexts with a logged prompt of at most 12.2k tokens;
  - QAT reference: A's `experiments/contagion/out/main/r31b_old_*.jsonl` and `r31b_heldout.jsonl` (P0/P1 rows only).
- Censoring is symmetric: a pair is dropped if the QAT generation would not have fitted under the bf16 cap, or if the cap truncated the bf16 generation.

**Statistics.**
- Wilson 95% CIs for proportions.
- Cluster bootstrap over attempts (2,000 resamples) for means and differences.
- Exact McNemar for paired binary outcomes.
- AUCs with bootstrap CIs.
- **Selection caveat.** Slip states were selected *because QAT sampled a look-alike there*. That inflates QAT-minus-bf16 differences at those states (winner's curse on the QAT-ct vs bf16 difference). Valid closers are biased the other way.
- The **population-weighted decision-point estimate** handles this. It takes P(look-alike) at the logged temperature at the end-of-`new_string` decision of clean-history edit calls, with valid and slip states re-weighted to their population frequencies in the logs. It is unbiased under the null "QAT = bf16". For QAT it must reproduce the observed slip rate, which validates the probe.

## Validity checks
- **Serving noise floor.** The same 219 bf16 positions were re-probed after five server restarts with other arms served in between.
  - Top-1 agreement: 99.5% [97.5, 99.9].
  - |Δ log P(logged token)|: median 0.00, p95 0.38 nats.
  - |Δ P(look-alike)|: mean 0.0016.
  - |Δ margin|: median 0.00, p95 0.46 nats.
  - This is negligible next to the 4–5-nat shifts and the 8-pp probability differences reported.
- **Probe fidelity.** The teacher-forced QAT log-prob of the logged token matches the generation-time log-prob logged by the main track (`blp`) to a median |Δ| of about 1e-5 nats (see results). The reconstructed states are therefore the logged ones.
- **Tokenisation parity.** The same prompt string yields the same token count and a single `<bos>` on `:8302` (QAT) and `:8304` (bf16). Strings and ids give identical log-probs.
- **One-token rendering difference (documented; it does not affect the comparisons).**
  - vLLM's chat path passes the system message as content parts, and the template renders those as `text | trim + ' '`. Our item prompts render the system content as a string, so they lack that one trailing-space token.
  - Rendering the system content as parts reproduces the logged `prompt_tokens` in 40/40 cases; rendering it as a string matches in 0/40.
  - The probe-fidelity check above shows that the difference is immaterial at the decision points.
  - Every model arm receives identical token ids.
- **Non-Gemma logs.** The main-track runs `t1_qwen`, `t2_qwen_rebench`, `t3_qwen_rebench` (Qwen3.8 teacher) and `dsprobe` (DeepSeek-V4 teacher) log `model=openai/gemma-4-31b-it-qat-w4a16-ct`. They are excluded here: 4,190 of 13,620 "base" edit calls, 0.4% of them malformed.
  - Gemma-only base 31B-QAT edit malformation: **3,296/9,430 = 35.0%**.
  - 138 of 771 contexts in `data/protocol/contexts.jsonl` come from these runs.
- **Template.** The main-track logs used the June-5 template; the July template appends `<|channel>thought\n` after tool responses. Probes use June-5. The order replay used July for both models, and the contagion replays use June-5 for both.

## Pending / open issues
- **Not done (cancelled or skipped by PI decision):**
  - QAT pass 2 (key and separator positions);
  - QAT-ct probes of the remaining valid states;
  - bf16 probes of the states that QAT-ct never received.
  - So key-position margins are reported only for the few states probed in the first run.
- **Scope of the states.** All states are logged 31B trajectories under the June-5 template with thinking on. Prompt + response is capped at 16,400 tokens (1,854/1,887 states fit).
  - The order replay uses the July template; the contagion replay uses June-5.
  - The decision-point estimate covers the end-of-`new_string` decision. Slips at other positions (e.g. `filepath`, ~2%) are not modelled.
- **R estimator.** R is a valid importance-sampling estimator only for arms whose slip mass lies inside QAT-ct's. That holds for bf16. For arms 2/3/5/6, use the decision-point estimate instead: those arms put slip mass on states where QAT-ct has about 0 probability, and R is then unstable.
- **What arm 2 is.** Arm 2 is Google's released "unquantized" QAT checkpoint. It is not a no-quantization control: 61% of its weights are on-grid and its matrices are globally shrunk.
- **Arm 6 is a crude transplant.** Mixing the embedding with a non-matching transformer moves all closer margins. It shows only that the embedding change contributes.

## Release (CPU reproducible)
- `make_release.py` writes `out/release/per_position_records.jsonl.gz`: one record per (arm, state, decision position) with the top-20 token ids and log-probs, the logged token, and item metadata. No context text is included.
- It also writes `out/release/meta.json`: look-alike token ids, population counts, arm map.
- `reproduce_quant_section.py` recomputes the decision-point table, the T = 1 variant, greedy rates, margins and R from those two files alone. It runs on CPU in seconds and needs no model and no tokenizer. Output: `out/release/reproduced.json`.

## Files
- **Data build:**
  - `scan_logs.py` → `data/edit_index.jsonl` (per-edit-call index, no message bodies).
  - `build_dataset.py` → `data/items_all.jsonl` and `data/items_prio.jsonl` (states, token ids).
  - `qm_common.py` (shared helpers).
  - `verify_render.py`.
- **Probes:**
  - `probe_margins.py`: generation-mode teacher forcing, top-20; options `--no-warm`, `--items-conc`, `--max-total`, `--shard-by-id`, `--done-glob`.
  - Outputs: `out/probe_qat_s{0,1}.jsonl` and `out/probe_qat_postg3.jsonl` (QAT-ct); `out/probe_bf16_s0.jsonl` (bf16); `out/probe_qatunq_s0.jsonl` (arm 2); `out/probe_fakeq4_s0.jsonl` (arm 3); `out/probe_bf16fakeq4_s0.jsonl` (arm 5); `out/probe_bf16qatemb_s0.jsonl` (arm 6); `out/probe_bf16_retest.jsonl` and `out/probe_qatg3_retest.jsonl` (noise floors).
- **Checkpoints:**
  - `fakeq4_0.py` (true Q4_0 fake quantization, unit-tested against the ggml reference) → `models/gemma-4-31b-it-qat-fakeq4_0/` (PI-designated) and `models_tmp/gemma-4-31b-it-fakeq4_0/`.
  - `hybrid_embed.py` → `models_tmp/gemma-4-31b-it-bf16-qatemb/`.
- **Weight space:** `weight_grid_diag.py` → `out/weight_grid_diag.json`; `weight_shift_diag.py` → `out/weight_shift_diag.json`.
- **Replays:**
  - `order_replay_capped.py` → `out/order_{bf16,qatunq,fakeq4}_think.jsonl`.
  - Contagion bf16 via `snapshots/contagion_scripts_1020/run_injection.py` → `out/contagion_bf16.jsonl`.
- **Analyses:**
  - `analyze.py` → `out/results_margins.json` and `out/states_paired.csv`.
  - `analyze_replay.py` → `out/results_replay.json`.
  - `analyze_decomp.py` → `out/results_decomp.json`.
  - D's `t5_quant_check.py` (read-only) → `out/t5_quant_check.json`.
  - `make_results.py` → `results.json`.
  - `finalize.sh` re-runs everything.
- **Release:** `make_release.py` and `reproduce_quant_section.py` → `out/release/`.
- **Drivers:** `bf16_chain.sh`, `bf16_chain2.sh`, `decomp_chain.sh`, `decomp_chain2.sh`, `prep_decomp.sh`, `prep_arm5.sh`, `rpost_g3.sh`, `stop_after_postslip.sh`, `qat_resume.sh` and `qat_postslip_2300.sh` (both cancelled by the PI).
- **Logs:** `logs/` (server logs of every arm are copied as `logs/g3_8304_*.log`). `progress.md` is the running log.
- **Re-run everything:** `cd experiments/quant_margins && QN=VLLM:Worker_D3 NAME=qmfinal tools/limited.sh ./finalize.sh`
