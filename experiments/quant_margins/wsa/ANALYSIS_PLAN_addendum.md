# ANALYSIS_PLAN addendum — pre-specified SECONDARY endpoints for the T3 adapter (workstream F)

**Written and frozen** 2026-11-05 about 14:05 UTC, at the PI's request. At this time:
- the repair has been fitted and tuned on calib only (inner CV);
- NO held-out repair number has been computed or seen;
- no held-out file and no held-out evaluation output exists.

**Scope.** The adapter targets the quantization-induced ONSET defect. Copying from a corrupted history (post-slip contagion states) is the job of slipguard.history (quarantine).

**What stays unchanged.** The frozen and amended gate in `ANALYSIS_PLAN.md` (primary E_pop over all 51 logged slip states; G1–G5) is reported exactly as logged, with no re-tuning. Everything below is SECONDARY. Anything not listed here is labelled post hoc.

All endpoints are computed on held-out data (logged slip states: all of them are out-of-sample) for three models:
- QAT-ct;
- QAT-ct + the adapter selected by the inner-CV rule (no re-tuning);
- bf16.

CIs use a cluster bootstrap over episodes (B = 2000, 95%).

## (a) Onset-only population estimate E_onset
E_onset = (N_v0 · mean_{held-out valid clean-history calls} p_call + N_s0 · mean_{ALL onset slip states} p) / (N_v0 + N_s0)

- **Counts** (PNC): N_v0 = 3,866 valid first-edit calls with a clean history (no prior malformed edit); N_s0 = 14 onset slip states (calib 8 + held-out 6; none used in fitting or selection).
- **p:** the shipped-sampler look-alike probability (T = 1, top-k 64, top-p 0.95).
- **p_call:** 1 − Π(1 − p) over the call's new/old closers.
- **Reported:** E_onset for the three models, the relative reduction (QAT → repaired), and the gap closure (E_QAT − E_rep)/(E_QAT − E_bf16).

## (b) Margin-deficit restoration on held-out valid new/old string ends
- **R_med** = (median m_rep − median m_QAT) / (median m_bf16 − median m_QAT), where m = log P(`<|"|>`) − log P(best look-alike).
- **Tail metric P(m < τ)** with **τ = ln 19 ≈ 2.944 nats**. Under the shipped T = 1 / top-p 0.95 sampler, a look-alike ranked second behind `<|"|>` enters the 0.95 nucleus once p(`<|"|>`) < 0.95, i.e. p_LA > 0.05 when the mass is concentrated on the pair, i.e. m < ln(0.95/0.05). This τ is the margin below which a slip becomes samplable at all.
- **Descriptive:** P(m < 6) and the 10th-percentile margin.

## (c) Per-call slip probability at held-out valid string ends
- mean p_call for QAT-ct, the repaired model and bf16, with ratios and CIs.

## (d) Combined stack on contagion (post-slip) states, if computable
- **States:** the 37 post-slip logged slip states (all out-of-sample).
- **Procedure:** re-render the history with slipguard.history quarantine (the frozen renderer in release/lib), keep the logged completion prefix up to the slip position, and probe P(look-alike) at the slip position (vLLM endpoint, top-20) under:
  - original history + QAT-ct;
  - quarantine + QAT-ct;
  - quarantine + QAT-ct + adapter.
- **Reported:** mean pLA and top-1-is-look-alike for each. If it is not computable today, this is stated rather than substituted.

## Power add-on (endpoint)
- On the vLLM gate server, generation-mode probes (no prompt_logprobs; one request per position, prefix-cached) of the new/old closer positions of ALL held-out valid PNC turns that fit the server, for QAT-ct vs QAT-ct + LoRA.
- Endpoint values (top-20 sampler reconstruction) are validated against the exact offline values on the overlapping core positions (G5).
