# Limitations

This page lists everything we know the evidence does **not** show, including failed registered predictions. Every
number comes from a frozen analysis or from an exploratory one that is labelled as such; `RESULTS.md` gives the file
for each. If you find a limitation that is missing here, please open an issue.

**Status labels.**
- *Registered*: decided by an analysis frozen (sha256 and UTC time) before the data existed. See `PREREGISTRATIONS.md`.
- *Exploratory*: computed afterwards with the frozen code reused unchanged. It is reported, never used as a verdict.
- *Pre-specified descriptive*: named in a registration but not tested (e.g. the pooled quarantine removal of §5).
- *Frozen suite*: a deterministic test of the conformance suite (e.g. the 218 known-intent turns of §15), not a
  statistical registration.

---

## 1. Scope of the evidence

- **One model family, one harness, one task source.** PNC histories come from the 4-bit QAT Gemma-4-31B (thinking on,
  temperature 1.0) running a small generic harness on SWE-bench tasks. The end-to-end test uses the agent harness
  released with the challenge (ADK, vLLM 0.19.1). TranscriptLab states are real agent states, but all of them come
  from this one model's histories, including when other models are scored on them.
- **End-to-end tasks come from four repositories.** The 113 eligible tasks are fastapi 61, rich 46, requests 5 and
  httpx 1 (`experiments/endtoend/configs/eligible_113.txt`); 107 of them come from two repositories. Every end-to-end
  result, including resolve non-inferiority, is conditional on that mix.
- **slipguard is Gemma-only by design.** Its parser, template and history guard implement Gemma 4's tool-call
  notation. TranscriptLab is template-agnostic (14 configurations, 5 tool formats); slipguard is not.
  - Every state, and the injected corruption itself, comes from the histories of the 4-bit QAT Gemma-4-31B. Every
    other configuration is therefore scored off-policy: 31B bf16, E2B, E4B and 12B as well as the AWQ checkpoint of
    §6. Non-Gemma rows measure sensitivity to a foreign corruption on off-policy histories, not whether those models
    launder their own calls.
- **The serving stack is vLLM.** The end-to-end and repair results use vLLM 0.19.1. The parser plugin is tested in
  vLLM 0.19.1, 0.24.0 and 0.31–0.33. IPD needs a vLLM backend, because it uses token-level completions. Other
  OpenAI-compatible servers can use quarantine only.
- **Sampling temperature.** The end-to-end runs use the challenge harness's own sampling: temperature 0.2, top-p 0.95,
  thinking on with a 4,096-token budget (experiments/endtoend/configs/client_request_params.json; every logged request).
  PNC and TranscriptLab use temperature 1.0. Contagion was registered at 1.0 and re-tested (PREREG_v2.7):
  - copying persists at T = 0.6 (+18.7 pp [13.9, 23.8]) and under greedy decoding (+20.7 [16.0, 25.6]);
  - quarantine removes 88% [75, 100] at T = 0.6 (verdict: works, attenuated) and 92% [83, 100] under greedy.
  - The end-to-end gain is measured only at the harness's 0.2.

## 2. End-to-end results (challenge harness, 31B)

- **The mean is driven by runaway loops** (exploratory; PREREG_E's two replicates). Malformed calls per episode fall
  2.47 → 0.27 (registered co-primary, 0.11× [0.06, 0.22]).
  - Most of that gain is the ending of runaway imitation loops. The 14 of 226 base episodes that got stuck (≥5
    consecutive malformed calls) hold ~78% of all base malformed calls. In these two replicates no proxy episode got
    stuck (stuck 14 → 0); in the eight fresh replicates, 3 of 904 did (next bullet).
  - The share of episodes with at least one malformed call falls much less: 30.5% → 21.7% (−8.9 pp [−15.5, −2.2]).
  - Excluding the 14 stuck pairs (212 of 226 pairs remain), malformed calls per episode fall 0.58 → 0.26 (task means,
    as registered; ratio 0.46 [0.33, 0.62], `EXPLORATORY_ext_replicates.json#r1_r2/excluding_base_stuck_pairs`).
    Averaged over episodes instead of tasks, the same pairs give 0.57 → 0.27 (0.48×;
    `EXPLORATORY_distributions.json#population/31B/Y1_excluding_base_stuck_pairs`).
  - slipguard does not prevent first slips; the onset is the model's own. It stops their propagation.
  - At E4B there are no loops, and the gain is not loop-driven: episodes with any malformed call fall 18 → 2 of 113.
  - Source: `experiments/endtoend/analysis/EXPLORATORY_distributions.md`.
- **Fresh replication: the cut replicates, but smaller** (PREREG_E_ext, registered; 8 fresh replicates r3–r10, 904
  episode pairs, 0 excluded; `experiments/endtoend/analysis/prereg_E_ext.json`).
  - Malformed calls per episode (S1, Y1): 1.76 → 0.37, ratio 0.21 [0.13, 0.35], difference −1.39 [−1.93, −0.90]
    (`#secondary/Y1`). The registered rule (ratio ≤ 0.30 and a CI excluding 0) holds: **REPLICATES**.
  - The cut is smaller than PREREG_E's (0.11× [0.06, 0.22]) and outside the predicted 0.11 [0.07, 0.18] (§14, row n).
  - Wasted calls (S2, Y2): 1.82 → 0.42, ratio 0.23 [0.15, 0.37] (`#secondary/Y2`).
  - Stuck episodes (S3): 49 → 3 of 904, McNemar p < 1e-4 (the file prints 0.0; `#secondary/stuck`). The proxy does
    not end every loop.
- **Resolve rate: non-inferior; no gain claimed** (PREREG_E_ext primary, registered).
  - Resolved: base 393 of 904, proxy 394 of 904. The task-mean difference is +0.11 pp [−2.21, +2.43]. The lower bound
    is above −3 pp, so the verdict is **RESOLVE NON-INFERIOR** (`#primary_resolve`, `#primary_verdict`).
  - What this shows: non-inferiority at −3 pp (the CI's lower bound is above −3 pp; one-sided α = 0.025). It does not
    show a gain, and the CI still allows a drop of up to 2.2 points.
  - The test is over all episode pairs. In most episodes the proxy has nothing to change: in PREREG_E's two
    replicates only 69 of 226 stock episodes delivered any malformed call (`EXPLORATORY_distributions.json`). A drop
    confined to the affected episodes would be diluted in this average.
  - The CI half-width, about 2.3 pp, is tighter than the predicted 3–4 pp (§14, row n).
  - Descriptive, sequential, all 10 replicates (r1–r10): +0.09 pp [−2.04, +2.30], 494 vs 495 of 1,130
    (`#descriptive_all_replicates/resolve`).
  - History: in PREREG_E's two replicates, resolve stayed at 43–46% in both arms, and the same test at −3 pp was not
    met in either (rep1 +1.8 pp [−4.4, +8.0], rep2 −1.8 [−8.9, +5.3]; declared underpowered). Until PREREG_E_ext we
    therefore claimed neither benefit nor no-harm on resolve.
  - On PREREG_E's 14 stuck pairs, resolve goes 5 → 6. Generated tokens fall 57k → 8.3k per episode and calls
    66 → 36 (exploratory). The rescued episodes are hard tasks: the gain there is cost, not resolve rate.
- **Serving the audit's pick end to end** (PREREG_E_awq, registered; `experiments/endtoend/analysis/prereg_E_awq.json`).
  - Under stock vLLM (the base arm), the cyankiwi AWQ checkpoint, served in bf16, delivered 0.41 malformed calls per
    episode, against 1.91 for Google's QAT checkpoint: ratio 0.22 [0.11, 0.39], difference −1.49 [−2.06, −1.00].
    Verdict: **AUDIT PICK REDUCES MALFORMED CALLS END TO END** (`#primary_awq_base_vs_qat_base`).
  - **Caveats.**
    - 2 AWQ replicates (226 episodes) against 10 QAT replicates (1,130 episodes: PREREG_E's r1–r2 and PREREG_E_ext's
      r3–r10).
    - The comparison is task-paired across different runs, not CRN-paired: different weights give different
      generations, so episodes are paired only by task.
    - The predicted AWQ-base level, about 1.2–1.8 (ratio 0.5–0.7), was missed: the cut is larger than predicted
      (§14, row o).
  - **The proxy on top of AWQ (S-a): the prediction failed.** 0.41 → 0.32, ratio 0.77 [0.44, 1.47], difference −0.09
    [−0.39, +0.11], p 0.54 (`#S_a_awq_fullp_vs_awq_base`). The predicted ratio ≤ 0.3 failed (§14, row o). Two
    replicates could not show a benefit; PREREG_E_awq2 registered six fresh ones to test it (next bullet).
  - AWQ-fullp vs QAT-fullp (S-b, descriptive): 0.32 vs 0.35, ratio 0.90 [0.57, 1.36]; about equal, as predicted (the
    predicted level was about 0.2–0.3).
  - Stuck episodes (S-c): AWQ base 1 of 226, fullp 0 of 226; QAT base 63 of 1,130, fullp 3 of 1,130.
  - Resolved (S-d, descriptive; with 2 AWQ replicates there is no NI claim): AWQ 106 and 105 of 226 (base, fullp);
    QAT 494 and 495 of 1,130.
- **The proxy on the audit's pick, six fresh replicates** (PREREG_E_awq2, registered; r3–r8, 678 episode pairs, 0
  excluded; `experiments/endtoend/analysis/prereg_E_awq2.json`).
  - Primary (P2), AWQ-fullp vs AWQ-base: 0.50 → 0.29 malformed calls per episode, ratio 0.59 [0.36, 0.99], difference
    −0.20 [−0.46, −0.003], p 0.045. Verdict: **SLIPGUARD STILL REDUCES MALFORMED CALLS ON THE AUDIT'S PICK**
    (`#primary_P2_awq_fullp_vs_awq_base`).
  - **Read it as a smaller cut, not a robust one.** The CI's upper bound is only just below 0, and the cut is smaller
    than on Google's QAT checkpoint (0.21×, above). The prediction was a ratio of about 0.75 with a probability of
    about 0.4 of a significant cut (§14, row p).
  - Wasted calls (S1): 0.54 → 0.33, ratio 0.61 [0.38, 0.98]. Stuck episodes (S2): 5 → 1 of 678, McNemar p 0.22.
  - S4 replicates the PREREG_E_awq primary on fresh episodes: AWQ base 0.50 vs QAT base 1.91, ratio 0.26 [0.15,
    0.44], **REPLICATES** (`#secondary/S4_awq_base_vs_qat_base_fresh`). It is task-paired across runs, like the
    original.
  - Descriptive, all 8 AWQ replicates (r1–r8, sequential): 0.47 → 0.30, ratio 0.63 [0.42, 0.96].
  - Resolve (S3) is descriptive only: 6 replicates and no power analysis, so no resolve claim is made.
- **PREREG_E_audit and PREREG_E_comp** (frozen 2026-11-07; analysed once on Nov 8 at 15:09 UTC; `PREREGISTRATIONS.md`
  rows 23–24). Results: the component bullet below and §6 ("The audit's flags predict end-to-end malformed calls").
- **Replicates.** The 31B proxy-vs-stock result has ten replicates: PREREG_E's two (stuck 9 → 0, p = 0.004; and 5 → 0,
  p = 0.06) and PREREG_E_ext's eight. The AWQ checkpoint has eight (PREREG_E_awq's two and PREREG_E_awq2's six); E4B
  and 12B have one each.
- **Which component carries the gain (PREREG_E_comp, registered; analysed once Nov 8 15:09 UTC).** Quarantine-only and
  IPD-only arms, salt-paired with PREREG_E_ext's replicates r3–r6 (113 tasks, 452 episode sets per arm;
  `experiments/endtoend/analysis/prereg_E_comp.json`). Malformed calls per episode:

  | arm | Y1 | vs stock |
  |---|---|---|
  | stock | 1.56 | |
  | quarantine only | 0.66 | 0.42× [0.25, 0.73], Holm p 0.003: **QUARANTINE ALONE REDUCES** |
  | IPD only | 0.37 | 0.24× [0.15, 0.37], Holm p < 1e-4: **IPD ALONE REDUCES** |
  | full proxy | 0.29 | |

  - Secondary contrasts (pre-specified, not in the Holm family):
    - IPD adds to quarantine: full vs quarantine −0.37 [−0.71, −0.15].
    - Quarantine adds little to IPD: full vs IPD −0.08 [−0.17, +0.02], n.s.
    - IPD alone beats quarantine alone: 1.80× [1.19, 2.98].
    - Stuck episodes: stock 24, quarantine 3, IPD 0 and full 1 of 452.
    - Wasted calls (Y2) follow Y1.
  - **Resolve (descriptive, NI at −3 pp):**
    - IPD-only −base +1.1 pp [−1.8, +4.0] (NI shown);
    - quarantine-only −base −1.1 pp [−4.4, +2.2] (NI not shown: the interval reaches −4.4).
  - **Reading:**
    - In whole episodes, repair (IPD) carries most of the cut; quarantine alone still more than halves malformed calls.
    - In the registered branch runs (the paper's §4), each component alone ends most post-slip loops (quarantine alone 11.6 → 0.18). That result is per branch after a first slip. Per episode, the slip calls themselves are also counted, and quarantine alone does not repair them.
  - **Predictions** (§14, row u): quarantine Y1 met. IPD Y1 is 0.37 against a predicted 0.4–0.8, a larger cut. The prediction "IPD stuck above 0" missed (0 of 452).
- **Malformed-call counts cannot see silent corruption.** Y1 counts the calls the reference judge flags in what the
  harness receives. The proxy's repair exists to turn flaggable calls into valid ones, and on injected slips it also
  turns some into valid but wrong calls (§3: 6.9% of the 393 detectable slips; 20.4% of all 600). Those lower Y1 while
  still doing harm. End to end, resolve non-inferiority is the only check on them.
- **Outcome-adjacent observations before unblinding** (PREREG_E; logged, none changed a decision). A log tail showed
  resolve counts for half of one replicate, but no co-primary data. Others are listed in §10.
- **Why the fresh cut is weaker, and where the proxy still fails** (EXPLORATORY, post hoc; not registered):
  - **The ratio swings with a few runaway loops.** Per replicate, the fullp/base ratio ranges from 0.10 to 0.74.
    Episodes whose base arm got stuck carry 39–81% of the base arm's malformed calls in each replicate.
  - **Without those pairs, the proxy roughly halves malformed calls:**
    - r1–r2: 0.58 → 0.26, ratio 0.46 [0.33, 0.62] (212 pairs);
    - r3–r10: 0.67 → 0.38, ratio 0.57 [0.36, 0.90] (855 pairs);
    - pooled over all ten replicates: 0.65 → 0.38, ratio 0.58 [0.38, 0.91] (1,067 pairs). With the stuck pairs, the
      ten-replicate pool is 1.91 → 0.35, ratio 0.19 [0.12, 0.29] (1,130 pairs).

    Source: `experiments/endtoend/analysis/EXPLORATORY_ext_replicates.json`.
  - **All 3 stuck fullp episodes are one failure mode** (rich_4070 in r6 and r7; fastapi_13920 in r9):
    - Every delivered malformed call in them is `edit_file` missing `old_string`. The model writes JSON-style escaped
      quotes inside a Gemma string. It is not a mistyped delimiter, so IPD finds no slip site (`no_site` on 81 of 81),
      and the proxy delivers the call as vLLM parses it, by design.
    - Quarantine was active, yet the model kept repeating the call.
    - The paired base episodes had 0 malformed calls; the trajectories diverge once the proxy changes anything.
    - These 3 of 1,130 fullp episodes carry 20% of all fullp malformed calls
      (`experiments/endtoend/analysis/EXPLORATORY_fullp_loops.json`).
  - **Practical reading:** slipguard repairs delimiter slips. Other malformations pass through, flagged in the history
    but unrepaired, and can still loop. A loop breaker (e.g. stop after k identical malformed calls) is not part of
    slipguard 0.1.1.

## 3. Repair (IPD, the proxy)

- **Key-position slips pass through.** IPD repairs a look-alike closer inside a *string value*. It does not repair a
  slip in an argument *name* (e.g. a key emitted as `start_line"`). These are delivered as the model wrote them.
  - The proxy's residual in PREREG_E's two replicates is 0.27 malformed calls per episode, i.e. 62 delivered calls in
    226 episodes (`prereg_pop31.json#co_primary/Y1/fullp_mean` × 226). They are calls IPD cannot repair: key-position
    slips and other malformations that are not a mistyped delimiter (for example `key=value` drift, or the
    JSON-escaped quotes of §2's fresh-replicate loops). We have no released per-class count of them.
  - The strict parser (`gemma4_strict`) refuses these calls instead.
- **Silent corruption on injected slips** (PREREG_v2.4; `battery_run_analysis.json`). The denominators matter:
  - On the 393 detectable injected slips (the registered primary set for repair quality), IPD recovers the exact
    intent 90.6% [85.4, 94.1] but corrupts 6.9% silently, against 1.1% for the stock lenient parser. The registered
    bound was 2%.
  - Over all 600 injected slips (ITT, reweighted), IPD corrupts 20.4% silently, the stock lenient parser 15.5%,
    fail-loud 14.7% and greedy re-decoding 3.5%. A slip that yields a valid call cannot be detected, so it is
    silently wrong for every text-based method. IPD's exact rate over all 600 is 77.8%.
- **Baselines stronger than predicted.** Retries and greedy decoding recover intent more often than predicted (greedy
  69.0%). Grammar-constrained decoding produced malformed, not silently corrupted, calls.
- **Natural slips.** Exact intent on natural slips was not estimable, because natural malformed first edits were rare
  on PNC (1.0% vs 13% predicted). On the second tool schema, IPD had nothing to repair.
- **Opt-in text repair was fixed post hoc on PNC.** Its counts on the 218 known-intent PNC turns (152 exact, 0 wrong,
  66 loud) follow a fix made after we saw those turns (before: 152 / 1 wrong / 65 loud). PNC is therefore not held out
  for that rule. Its 327 repairs of turns without known intent are unscored.

## 4. History guard and the full stack

- **Two "gain with harm" verdicts.** On contaminated histories, the full stack drives the malformed-edit rate to 0 of
  300 at both sizes:

  | model | malformed-edit rate |
  |---|---|
  | 31B | 19.7% → 0/300 |
  | E4B | 7.0% → 0/300 |

  The registered verdict was nevertheless *gain with harm*, so we claim no gain from it.
  - The no-harm rule (N2) counted IPD repairs of strictly invalid calls that the reference judge does not flag: 1 of
    1,500 samples at 31B and 3 of 600 at E4B. No valid call was altered.
  - At 31B the N2 event occurred in a replay pooled into the first verdict by the registration. The second verdict
    has no N2 gate of its own. This is correct per the registration, but it reads oddly; we report it as registered.
- **Fail-loud can end an ADK turn.** Under ADK, a text-only answer is final. The strict parser trades a silently
  corrupted call (35.5% of laundered calls were executed in a full ADK runner) for a visible stop. Deploy it with the
  proxy or the history guard, which tells the model to re-issue the call.
- **Text-only repair is ill-posed in general.** A string can legitimately contain `` `,old_string: ``. slipguard never
  repairs from text alone without reporting it.

## 5. TranscriptLab (the causal benchmark)

- **Effect size.** The 31B effect on public states is about half its development size: copying +18.3 pp [13.6, 23.2].
  The success-response (induction) and dose effects were smaller than registered.
- **Without quantization (PREREG_v2.14, registered).** Gemma-4-31B in bf16 copies too: +8.7 pp [5.7, 12.0]. But half as often as
  the 4-bit QAT model on the same states (P1 8.7% vs 19.7%, McNemar p = 5e-8). Copying is a Gemma-4 trait that the QAT weights amplify.
- **Where it does not appear.** Copying did not appear in Gemma-4-12B or in any non-Gemma model tested (Hermes-3-Llama passes the P1 rule by retries, not copies; below).
  - Every other Gemma 4 configuration tested needs a guard (PREREG_v2.9, via the released CLI): E2B 4-bit (copying
    +4.7 pp, induction +10.3, the latter larger than predicted) and E4B bf16 (+3.0 / +4.7).
  - Induction passed its registered rule in 2 of 7 non-Gemma models: Qwen3-8B (PREREG X v2's X4 rule; it misses the first registration's ≥ 5 pp secondary, +4.7 pp) and Devstral-Small-2 (the extension's ≥ 5 pp rule).
  - **A Llama-family model is history-sensitive, but not by copying (PREREG_v2.12).** Hermes-3-Llama-3.1-8B, run through the
    CLI 0.1.3, gave copying RD +6.0 pp [2.6, 9.6] and imitation +5.3 pp [2.3, 8.7]: HISTORY-SENSITIVE. Our prediction of no
    copying failed. The frozen copy check shows none of its 28 malformed P1 edits copies the laundered call: 26 are tool-call
    blocks that do not parse. The error roughly doubles its edit attempts (26% → 55%). So the P1 contrast measures more than
    copying for this model.
  - **CLI 0.1.2 could not run that model.** X's frozen runner assumes Qwen's tokenizer: a null stop id, then a second BOS
    and no stop on Llama's end token. 0.1.3 adapts requests for new models only (PREREG_v2.12 deviation 1; CHANGELOG).
  - Qwen3.8-27B's induction CI excludes 0 (+4.7 pp [2.4, 7.2]), but it misses the registered ≥5 pp rule. The
    leaderboard's "History-sensitive" column uses the CI rule (a lower bound above 0), so it lists 4 non-Gemma
    models (Qwen3-8B, Devstral-Small-2, Qwen3.8-27B and Hermes-3-Llama-3.1-8B).
- **Injected corruption.** Most onsets in the branch experiment are injected (122 of 135); 13 are natural.
  - On the natural subset (exploratory), the pattern is the same and the base loop is stronger: post-onset malformed
    calls are 24.3 base → 0.15 quarantine / 0 IPD.
  - Source: `EXPLORATORY_distributions.md` (B9).
- **Logs cannot identify the effect.** The history effect and between-episode heterogeneity are identical in law for
  observational logs (proof in `paper/protocol_theory/`). Only interventions identify it, which is why TranscriptLab
  edits states.
- **Reliability (PREREG_v2.7 test-retest: PARTLY STABLE; PREREG_v2.8 released CLI: DOES NOT REPRODUCE).**
  - Copying is very stable. P1 is 19.7% (registered) vs 20.0% and 20.3% with two new seed sets and 19.3% through the
    released CLI. Copying RD runs +18.3 to +19.7 pp.
  - **Quarantine removal is not.** The pooled estimate is 92% [86, 98] over 300 states × 3 runs (900 samples per arm:
    the registered run and two new seed sets; pre-specified descriptive, computed afterwards). Per run: 98%
    registered, then 93% and 86% with the new seed sets; the released-CLI rerun (PREREG_v2.8, not in the pool) gave
    85%. Removal thus fell below the registered 90% bar twice, and both registered failures are reported in the
    paper's §6.
  - This is quarantine as the proxy does it (the recovered call plus an explicit error, P8a). The ADK and LiteLLM
    hooks quarantine with a sanitized re-render (P8b), which has one registered run: 98% [88, 110] (PREREG_v2 C6), and
    no rerun.
  - Removal rests on few events (5–11 malformed edits of 300 after quarantine). vLLM sampling is not bit-reproducible:
    only 63% of the CLI rerun's generations were byte-identical, with identical prompts.
  - Read removal as "about 85–98%", not as 98%.
  - Its contrast with an informative error (which leaves 76% of the excess) holds in every run.
- **Branch means are cap-dependent.** Base branches that loop run to the turn cap, so ratios of means are large: 11.6
  → 0.18 for quarantine. 15 of the 150 planned branch points were excluded by the (corrected, pre-outcome) fidelity
  or infrastructure rule, so 135 were analysed (`prereg_br31.json#excluded_fidelity_or_infra`).
  - The share of branches with any post-onset malformed call is the cap-free view (exploratory): 64% base → 9.6%
    quarantine → 3.7% IPD.
  - Excluding the 54 base-stuck branches, the cut is still 4–20×.

## 6. Weight audit (`slipguard audit-weights`)

- **Censoring.** The endpoint returns top-20 log-probabilities, so about half of the string-end margins on 31B
  checkpoints are censored and count as lower bounds (42–55% per checkpoint).
  - Exploratory sensitivity: every censored case is of the lower-bound kind. No look-alike was in the top-20, and the
    true delimiter was never outside it.
  - On positions where neither margin is censored, the gap between the two checkpoints widens: QAT-ct 5.67
    [4.94, 6.07] vs cyankiwi AWQ −0.47 [−0.81, −0.18]. Censoring does not explain the ranking.
  - Source: `experiments/quant_margins/wsa/EXPLORATORY_censoring.md`.
- **Dtype confound: resolved.**
  - The original test served the audit's pick (cyankiwi AWQ) in float16, against Google's QAT checkpoint in bf16.
  - Served in bf16 (PREREG_v2.7 D1), AWQ still cuts post-slip contagion: 12.0% vs 19.7%, −7.7 pp [−11.4, −4.0],
    Holm p 6e-5 (verdict: audit pick replicates at matched dtype).
  - The bf16-vs-float16 AWQ difference is +1.7 pp [0, 3.3], descriptive.
- **End to end (PREREG_E_awq, PREREG_E_awq2; §2).** Served under stock vLLM in the challenge harness, the audit's pick
  delivered 0.41 malformed calls per episode against QAT's 1.91 (0.22× [0.11, 0.39]; 2 AWQ against 10 QAT replicates),
  and 0.50 in six fresh AWQ replicates (0.26× [0.15, 0.44], REPLICATES). Both comparisons are task-paired across runs
  rather than CRN-paired. On AWQ the proxy still cuts malformed calls, by less than on QAT (0.59× [0.36, 0.99] in the
  six fresh replicates; 0.77×, not significant, in the first two). One checkpoint pair cannot show that the audit
  picks well in general; PREREG_E_audit (next bullet) tests the flags across checkpoints.
- **The audit's flags predict end-to-end malformed calls (PREREG_E_audit, registered; analysed once Nov 8 15:09 UTC).**
  - All four Holm tests pass (`experiments/endtoend/analysis/prereg_E_audit.json`). Stock-vLLM malformed calls per episode:

    | checkpoint | flag | base Y1 | test (difference, 95% CI) |
    |---|---|---|---|
    | bf16 | reference | 0.42 | T1: below QAT, −1.58 [−2.75, −0.67] |
    | nvidia NVFP4 | not flagged | 0.34 | T2: below QAT, −1.31 [−2.12, −0.65] |
    | AWQ (bf16 export) | not flagged | 0.47 | comparator, 8 replicates |
    | QAT | flagged | 1.91 | reference, r1–r10 |
    | QAT-AWQ | flagged | 3.81 | T3: above AWQ, +3.33 [1.94, 4.98] |
    | QAT-NVFP4 | flagged | 4.85 | T4: above AWQ, +4.37 [2.89, 6.07] |

  - The Spearman correlation between deficit and base Y1 over the six is 0.83 (descriptive).
  - **Is the proxy needed?** (pre-specified secondary, fullp vs base per checkpoint):
    - QAT-AWQ 3.81 → 0.19 (0.05× [0.005, 0.15]);
    - QAT-NVFP4 4.85 → 0.27 (0.06× [0.02, 0.13]);
    - nvidia NVFP4 0.34 → 0.19 (0.57× [0.36, 0.89]);
    - **bf16 0.42 → 0.45 (1.07× [0.33, 2.83], p 0.99): no measurable end-to-end gain on bf16.**
    - The prediction was "ratio ≤ 0.3 on flagged checkpoints; small or n.s. on unflagged ones".
      - It was met on both flagged checkpoints and on bf16.
      - On nvidia NVFP4 the cut is significant (p 0.02) but small in absolute terms (−0.15 per episode), so "small" holds and "n.s." does not.
    - With QAT (1.76 → 0.37) and AWQ (0.50 → 0.29), the proxy cut malformed calls on every checkpoint tested except bf16.
    - Practical reading: on bf16 the proxy is insurance against rare slips, not a measured gain in this harness. Its other functions (refusing laundered calls, the history guard) are unchanged.
  - **Limits:**
    - Analysis sets: bf16 has two replicates (r3–r4; tensor-parallel lanes are slower); the other new checkpoints have three (r3–r5).
    - T3 and T4 compare against AWQ task-paired across runs, not CRN-paired.
    - The magnitudes missed their predictions (§14, row t): the QAT-derived exports loop more than predicted, nvidia NVFP4 less.
    - Six checkpoints of one model, one harness, temperature 0.2.
    - The analysis started at 15:09 rather than 14:00. No data were added and it ran once (experiments/endtoend/PREREG_DEVIATIONS.md).
- **The audit predicts copying across checkpoints (registered, Nov 8).**
  - PREREG_v2.14: bf16 itself copies (+8.7 pp [5.7, 12.0]) but half as often as QAT-ct on the same states (P1 8.7% vs 19.7%, McNemar p = 5e-8).
  - PREREG_v2.15: across seven 31B checkpoints, the audit deficit ranks post-slip P1 (Spearman ρ = 0.89, exact one-sided p = 0.006).
    - Three of them were audited (PREREG_v2.10) but never run before this test.
    - Out of sample, the two flagged QAT-derived exports copy more than bf16 (22.3% and 24.3%), and the unflagged nvidia NVFP4 copies less than QAT (10.0%). All three registered McNemars were met.
  - Limits:
    - One rank is inverted: nvidia NVFP4 (1.36 nats, 10.0%) sits below AutoRound (0.63 nats, 13.3%).
    - Measured as excess over each checkpoint's clean baseline, AutoRound has the smallest effect, because its clean baseline is 8.3%.
    - Seven checkpoints of one model family.
  - PREREG_v2.16: the unquantized QAT weights, served at bf16 precision, copy like the 4-bit QAT model and twice as often as bf16 (P1 18.0% vs 19.7% and 8.7%; p = 2e-6 vs bf16; unquantized − 4-bit: −1.7 pp [−5.2, +2.0]).
    - Over 11 checkpoints the split is by origin, not format: QAT-derived 18–24%; bf16-derived 7.3–13.3% (AWQ, FP8, NVFP4, AutoRound).
    - Missed predictions: RedHat NVFP4 came in at 7.3% (predicted 9–13%), and the 11-checkpoint ρ is 0.79 (predicted ≥ 0.8).
- **No weight repair.** Three registered weight-repair candidates failed their gates, and we ship the audit, not a
  repair.
- **Audit breadth (PREREG_v2.10).**
  - The damage follows the QAT-trained weights, not the 4-bit format (H-QAT supported):
    - AWQ and NVFP4 exports of the QAT weights lose 6.00 [5.63, 6.35] and 7.41 [6.90, 8.14] nats, and both are flagged;
    - the same formats from the bf16 weights lose 0.02 and 1.36 [1.09, 1.53] (nvidia NVFP4, the most downloaded 4-bit
      export), and neither is flagged.
  - The nvidia NVFP4 deficit was above its predicted 0.5–1.0.
  - Not audited: two checkpoints would not serve in our pinned stack. unsloth bnb-4bit needs bitsandbytes ≥ 0.48.1,
    which we did not install mid-campaign. unsloth NVFP4's compressed-tensors targets do not match vLLM 0.19.1's fused
    modules under the text-only override.

## 7. PNC (the corpus)

- **Coverage.**
  - 1,181 episodes / 41,290 turns from one model and one harness.
  - 400 SWE-bench Verified tasks (100 of them again with a second tool schema) plus 681 non-Verified tasks.
  - SWE-bench grades exist for 1,167 episodes (499 resolved).
- **Licences.** Text from GPL-licensed repositories is excluded. Each record keeps its repository's licence.
- **No private competition data.** PNC was produced on public tasks only.
- **The released corpus is masked, and the masking moved P1 (PREREG_v2.11: MASKING CHANGES THE RESULT).**
  - Developer e-mail addresses are masked as `<email>` in the released corpus (v1.1). This changes 43 of TranscriptLab's 300
    A1 states (172 of 1,200 prompts). Every registered TranscriptLab number in the paper and in RESULTS.md was produced on
    the unmasked v1.0, which is not released.
  - We reran TranscriptLab on the released v1.1 through the released CLI, with the registered seeds, and analysed it once with the
    pre-registered rule:
    - copying +15.0 pp [10.9, 19.5], inside the registered CI [13.6, 23.2] (condition a: pass);
    - P1 16.7% vs the registered 19.7%: −3.0 pp [−5.4, −0.7], exact McNemar p = 0.022 (condition c: fail).
  - Other arms on v1.1: P0 1.7%, P6 7.7% (imitation +6.0 pp [3.0, 9.5]), P8a 2.7%; quarantine removal 93% [78, 109].
  - **A second masked run (PREREG_v2.11b, descriptive, registered before it ran)** gave P1 18.0%, copying +16.7 pp
    [12.2, 21.3] and removal 92% [78, 106]. Its pre-specified reading is INCONCLUSIVE.
    - On the 43 masked states, P1 was 13/43 in both masked runs vs 17 and 16 in the two unmasked same-seed runs.
    - On the 257 unchanged states it was 37 and 41 vs 42 and 42.
    - So masking plausibly lowers P1 a little on the states it changes: 17.3% vs 19.5% pooled over two runs each.
  - **These are the numbers a user reproduces from the released corpus** (within run-to-run noise; see the next item).
  - Exploratory (after the verdict): only 665 of the 1,028 unchanged-prompt generations were byte-identical to an
    earlier rerun, so run-to-run noise is real. The second run separates noise from masking (next item).
  - Files: `experiments/contagion/out/confirmatory/v211_masked_analysis.json`, `experiments/v211/RESULT_v211.md`.

## 8. Conformance suite

- **Public subset.** The public tree ships the non-sensitive conformance inputs. The exact inputs for four
  security-relevant defect classes (tool-call injection from strings, quadratic slowdowns, recursion crashes and
  infinite-loop hangs) are withheld; see `SECURITY.md`.
- **Streaming time bound.** Streaming inside vLLM 0.19.1 and 0.31–0.33, slipguard's plugin exceeds the suite's 250 ms
  bound on a 37,755-character input (448 ms to 1.23 s). It is linear in the input, but the bound is not met. vLLM
  0.19's streaming loop is super-linear for any parser. Built-ins take 0.8 s to over 15 s, or raise.
- **No speed claim.** On public traffic, parsing costs at most 0.11% of generation time.

## 9. Evaluated vs derived code

- **Evaluated.** The end-to-end and repair results use the frozen proxy (`fullp`, vLLM 0.19.1), shipped
  byte-identical. `slipguard verify` checks this.
- **Derived.** The vLLM plugin, the lite IPD engine and the extra history transforms are covered by conformance tests
  and a GPU smoke test, not by an end-to-end agent run.
  - Not done: an end-to-end agent run of the plugin path. The frozen end-to-end analysis cannot score it, and new
    measurement code was not written under deadline.
  - The plugin and the proxy were soak-tested against stock vLLM (§11).

## 10. Process

- Every deviation from a registration is logged in `paper/protocol_theory/prereg/PREREG_DEVIATIONS.md`, including
  pre-data clarifications.
- Exploratory analyses reuse the frozen code unchanged and are labelled as such in their file names.
- The frozen end-to-end analysis seeds its paired-difference bootstrap with Python's per-process string hash. Its
  difference CIs therefore reproduce only up to Monte-Carlo error, about ±0.08 calls per episode on Y1. Every
  registered verdict holds at all 1,000 possible seeds (`REPRODUCE.md`, "Known non-determinism").
- **Outcome-adjacent observations.** Besides the PREREG_E log tail of §2, the ledgers record three more; none changed
  a decision:
  - PREREG_E, 2026-11-06 02:17 UTC: per-arm completion counts and the timing of in-flight stock-arm branch sessions
    (some running about 100 turns) were seen before branch completion; no malformed-call or resolve values
    (`experiments/endtoend/PREREG_DEVIATIONS.md`).
  - PREREG_v1, 2026-11-04 11:47–11:50 UTC: a runner started before the freeze printed per-arm malformed counts after
    it (`paper/protocol_theory/prereg/PREREG_DEVIATIONS.md`, A item 1).
  - PREREG_E, 2026-11-04 12:02 UTC, before its freeze: a progress monitor printed the exploratory pilots' per-arm
    resolve counts once (values in PREREG_E.md §8).
- **Data that existed before a freeze.** PREREG_v1's final P6/P7 runs finished at 11:42 UTC, before its 11:47 freeze;
  they were not analysed or shown until after it (same ledger, A item 2).
- **Sequential re-tests.** PREREG_E_ext was registered after both of PREREG_E's replicates failed the resolve
  non-inferiority test, and PREREG_E_awq2 after PREREG_E_awq's two-replicate S-a miss. Both are disclosed in their
  registrations and use fresh replicates only. Pooled over all ten 31B replicates (descriptive), resolve is still
  non-inferior: +0.09 pp [−2.04, +2.30] (§2).

## 11. Soak under overload (PREREG_v2.7 §5: FAIL on K-a and K-b)

- **Setup.** A 2-hour soak replayed recorded PNC requests at concurrency 48 against one Gemma-4-31B 4-bit server:
  - 60 min through stock vLLM and the proxy (random 50/50 routing);
  - 60 min through vLLM with the slipguard plugin and the guarded template.
- **Passed:**
  - no crash or unavailability (0 bad health samples of 752);
  - no protocol-corrupt delivery through slipguard (0 of 473 proxy calls and 0 of 918 plugin calls; stock vLLM
    delivered 1 laundered call of 451);
  - latency of non-repaired proxy requests: median 0.96× and p99 0.77× stock;
  - memory growth: +22 MB proxy, +2 MB plugin server.
- **Failed:** the registered availability and error gates, because some requests hit the 600-s client timeout.
  - The load saturated the server: about 19 running and up to 43 waiting requests, KV cache 94%, ~3 tokens/s per
    request.
  - **Non-streamed requests** timed out at about the same rate on every route (1–2%): stock 5/232, proxy 4/230, plugin
    9/468.
  - **Streamed requests** timed out only through slipguard: stock 0/235, proxy 4/255, plugin 7/494. Both slipguard paths
    send nothing until a tool call is verified, so at ~3 tokens/s a long turn can be silent for more than 600 s.
  - **Overall timeout rates** do not differ detectably from stock: proxy 8/485 vs 5/467, Fisher p 0.58; plugin 16/962,
    p 0.49.
- **What to do.** Under heavy load, clients of slipguard's streaming endpoints see a longer time-to-first-byte on
  tool-call turns. Do not use short read timeouts.
- Details: `experiments/soak/EXPLORATORY_soak_timeouts.md`.

## 12. Bugs found by our own checks before release
- **TranscriptLab CLI.** `--python <venv>/bin/python` was resolved through the venv symlink to the base interpreter,
  which dropped the venv's packages. Found by PREREG_v2.8's first attempt, before any generation. Fixed, with a
  regression test.
- **Soak launcher.** The launcher picked up a stale failed systemd unit as the server's name. Found 7 minutes into the
  first soak; the run was restarted and the 7 minutes excluded (PREREG_DEVIATIONS v2.7 item 4).

## 13. The reference judge (what "malformed" means)
- Every rate is scored by the project's fixed reference judge: vLLM 0.19.1's Gemma 4 parsing plus a schema check.
- An independent replication from raw records found two narrow cases. Neither changes a conclusion.
  - **A final string closed by a look-alike** (e.g. `` `} ``) is not flagged. A strict-grammar judge gives the C1
    copying run P1 20.0% (vs 19.7%), RD +18.3 pp (unchanged) and removal 96% (vs 98%).
  - **An unparsed call** counts as an edit only if the judge recovers the name `edit_file`. This moves P0/P1/P6 by about
    one sample each.

## 14. Other registered predictions and verdicts that failed
Listed so nothing is hidden; registration files and keys are in `PREREGISTRATIONS.md`. "Induction" is the registrations'
name for what the paper calls imitation (a laundered call followed by its success response).

| # | registration | item | result |
|---|---|---|---|
| a | PREREG_v2.4 | the registered family testing that IPD silently corrupts less than each baseline (6 tests) | all failed |
| b | PREREG_E / E_PREDICTIONS | the predicted small-model crossover (12B s_post 0.25) | 0.79 |
| c | PREREG_E branches, 12B and E4B | quarantine / IPD ≥ 50% cut | no post-onset loop to break: base 0.07 malformed calls per branch; the rule is false |
| d | PREREG_v2 C10 | "induction ≥ copying" in the small models | failed at 12B and E4B |
| e | PREREG_v2 C11 | quarantine at 12B and E4B | 12B P5 and P8a, and E4B P5, failed (underpowered) |
| f | PREREG_v2 natural descriptives | immediate retry after a slip | 12.8% (predicted 72%) |
| | | stuck episodes in PNC's own harness | 0.8% (predicted 6%) |
| | | closer share | 53% (predicted ≥ 70%) |
| g | PREREG_v2 C15, natural slips (n = 13) | retry and greedy | failed; grammar-constrained attenuated |
| h | PREREG_v2.6 | AutoRound's no-harm check | failed: clean baseline 8.3% vs 1.3% |
| i | PREREG_v2.10 | the nvidia NVFP4 deficit (predicted 0.5–1.0 nats) | 1.36 |
| j | PREREG_v2.9 | E2B induction (predicted +3 pp [0, 7]) | +10.3 |
| k | PREREG_v1 | the dose models M1–M3 | none fit; r-dose null |
| l | PREREG_v2.4 | IPD vs text repair | +7.0 pp, larger than predicted |
| m | E_PREDICTIONS secondaries | generated tokens (registered 0.97) | 0.81, n.s. |
| | | first edit | no earlier (median 10 vs 10 turns) |
| n | PREREG_E_ext §5 | Y1 ratio (predicted ≈ 0.11 [0.07, 0.18]) | 0.21 [0.13, 0.35]: missed, a weaker cut (the S1 verdict, REPLICATES, holds) |
| | | resolve CI half-width (predicted 3–4 pp) | about 2.3 pp ([−2.21, +2.43]): tighter than predicted |
| | | stuck episodes (predicted base ≈ 6%, fullp ≈ 0) | base 49/904 = 5.4% (met); fullp 3/904, about 0.3%: approximately met, but not zero |
| o | PREREG_E_awq §4 | S-a: the proxy on the audit's pick (predicted ratio ≤ 0.3) | 0.77 [0.44, 1.47], diff −0.09 [−0.39, +0.11], p 0.54: failed |
| | | AWQ-base Y1 (predicted ≈ 1.2–1.8, ratio 0.5–0.7) | 0.41 (0.22× [0.11, 0.39]): missed, a larger cut than predicted |
| p | PREREG_E_awq2 §5 | P2: the proxy on the audit's pick, 6 fresh replicates (predicted ratio ≈ 0.75, diff ≈ −0.1, a significant cut with probability ≈ 0.4) | 0.59 [0.36, 0.99], diff −0.20 [−0.46, −0.003]: significant; a larger cut than predicted |
| | | S3 resolve, fullp − base (predicted ≈ 0 pp) | +3.7 pp [+1.5, +6.1] (301 vs 326 of 678): missed. Descriptive, unexplained and not claimed (6 replicates, no power analysis) |
| | | S2 stuck (predicted base ≈ 0.5%, fullp ≈ 0) and S4 (predicted REPLICATES, ratio ≈ 0.2–0.3) | 5 vs 1 of 678; 0.26 [0.15, 0.44], REPLICATES: met |
| q | PREREG_v2.11 | masking e-mail addresses does not change TranscriptLab's result | failed: P1 16.7% vs 19.7%, McNemar p = 0.022 (copying +15.0 pp, inside the registered CI); a second masked run (v2.11b, descriptive) is inconclusive (§7) |
| r | PREREG_v2.12 §5 | Hermes-3-Llama-3.1-8B: copying ≈ 0 [−2, +3] | +6.0 pp [2.6, 9.6], HISTORY-SENSITIVE; but 0 of 28 malformed edits copy the laundered call (§5) |
| | | (not a prediction) the released CLI 0.1.2 runs this model | failed: null stop id; fixed in 0.1.3 (deviation 1) |
| s | PREREG_v2.13 | a second Llama-tokenizer model (Hermes-2-Pro-Llama-3-8B) | not run: 8,192-token context window (§5) |
| t | PREREG_E_audit §5 | base Y1: bf16 0.3–0.7; nvidia NVFP4 0.4–1.0; QAT-AWQ 1.5–2.5; QAT-NVFP4 1.5–3.0 | 0.42 (met); 0.34, 3.81, 4.85: missed, all in the direction of the flags (the four tests and Spearman ≥ 0.7, 0.83, met) |
| u | PREREG_E_comp §5 | IPD-only Y1 0.4–0.8 (ratio ≈ 0.25–0.45); IPD-only stuck above 0 | 0.37, ratio 0.24 (a larger cut); 0 of 452: both missed. Met: quarantine-only Y1 0.66, in 0.6–1.0; Q1; Q2; full < quarantine |
| v | PREREG_v2.14 §4 | bf16 P1 ≈ 9–10% | 8.7%: marginally below (copying ≈ +9 pp: +8.7, met; both verdicts met) |
| w | PREREG_v2.15 §4 | QAT-AWQ P1 ≈ 18–22% | 22.3%: marginally above (ρ ≈ 0.8–0.95: 0.89, met; QAT-NVFP4 and nvidia NVFP4 ranges, S1–S3: met) |
| x | PREREG_v2.16 §4 | RedHat NVFP4 P1 ≈ 9–13%; extended-panel ρ ≥ 0.8 | 7.3%; 0.79: both missed (H1, H2, qatunq, FP8 and QuantTrio ranges met) |

The paper's §6 names the main failures and points to this table for the rest. Several rows hold more than one test: row a is a family of six,
and rows f, m and n list several items. Other registered verdicts that failed or came out weaker than predicted are
described elsewhere on this page: copy-on-retry (X1) fails in all three Qwen models, and copying fails in all four
further families (§5); PREREG_v2.4's rules R4, R7 and R8 fail (§3, "Baselines stronger than predicted"); PREREG_v2's
C2 and C3 are ATTENUATED (§5). Rows n–p, t and u are the end-to-end extensions; rows q–s and v–x are the release-time TranscriptLab checks (Nov 8).

- **Silent corruption on injected slips (row a).** Rates are reweighted to natural closer shares
  (`experiments/intent_decoding/v24/battery_run_analysis.json`):

  | decoder | on the 393 detectable slips (registered primary set) | over all 600 injected slips (ITT) |
  |---|---|---|
  | IPD | 6.9% | 20.4% |
  | stock lenient | 1.1% | 15.5% |
  | fail-loud | 0% | 14.7% |
  | text-only repair | 9.1% | 22.3% |
  | greedy re-decoding | 4.1% | 3.5% |

  IPD recovers far more intent (90.6% exact vs 0% stock on the detectable slips; 77.8% vs 0% over all 600), but it
  also delivers more silently wrong calls than stock does: stock's failures are mostly visible. The undetectable slips
  (all 600 minus the 393) are silently wrong for every text-based method.

## 15. Technical caveats from an independent serving review
- **Strict parser = grammar, not schema.** `gemma4_strict` delivers any grammar-valid call. A verbatim copy of a
  laundered call (the copying of §5) restores delimiter parity, so it is grammar-valid and gets delivered.
  `gemma4_strict_schema` also rejects calls that do not match the request's tool schema and catches such copies. In the
  soak, 5 schema-invalid calls passed the plugin and 5 passed the proxy.
- **Use the reasoning-parser plugin with the tool-parser plugin.** Serve with both `--tool-call-parser gemma4_strict`
  and `--reasoning-parser gemma4_strict`. Without the reasoning plugin, a model thought makes every following call
  undeliverable.
- **The proxy does not refuse.** IPD repairs look-alike closers inside string values. Calls it cannot repair (key-position
  slips, `key=value` drift) are delivered as vLLM's lenient parser reads them. They make up the residual 0.27 malformed
  calls per episode of PREREG_E's two replicates (62 calls in 226 episodes; §3).
- **Byte identity applies to whole turns.** IPD cuts the turn at the first invalid call, so valid calls after it are
  resampled.
- **Not streamed.** The proxy returns the whole response as one chunk.
- **`tool_choice`.** `required` or a named tool bypasses every tool parser. The proxy ignores `tool_choice` and assumes a
  32k context.
- **Known-intent population.** The 218 ill-formed PNC turns of known intent are mostly `key=value` drift (150); at most
  16 are look-alike closers. slipguard's "0 wrong" holds by construction, because the strict parser refuses all of them.
- **Weight-audit deficit.** `median_deficit` is median(bf16 margin) − median(checkpoint margin) over matched string
  ends (a difference of medians, with a paired bootstrap over positions).
  - Repeat serving runs differ by up to 0.44 nats, which the CI does not include.
  - On H100, NVFP4 checkpoints run weight-only through Marlin, not native W4A4.
  - The 12B and E4B deficits in the sweep are measured against the 31B bf16 reference (cross-size).
- **The ADK and LiteLLM hooks quarantine with a sanitized re-render** (the P8b form), not the recovered call (P8a) used
  by the frozen proxy. The two forms have different evidence. P8b: one registered run, 98% [88, 110] of the excess
  removed (PREREG_v2 C6), no rerun, and no end-to-end run of the hooks. P8a: 98% in the same run (C5), 92% [86, 98]
  pooled over three runs (§5), 0 of 300 malformed next edits on the AWQ checkpoint, and the end-to-end results of §2
  through the proxy.
- **The judge's gaps** (also §13): it does not flag a closer slip in the last argument, or a dropped optional argument.

