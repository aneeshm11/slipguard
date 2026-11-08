# SWEEP_PLAN — T1 checkpoint audit sweep and repair of flagged checkpoints (workstream F)

**Frozen** 2026-11-05 about 14:30 UTC, before any sweep number was looked at.
- An interrupted 31B-bf16 endpoint run left 373 records in `out/audit_sweep_31b_bf16.records.jsonl`. They have not been analysed.
- Fixed inputs: decision points `data/audit_items_16k.jsonl` (sha256 4d1b8dee…: 235 held-out items = 227 valid + 8 slips, prompt+completion ≤ 16.4k tokens, so the same states fit every server).
- Governing plans: ANALYSIS_PLAN.md and its addendum (sha in PROGRESS.md).

## Checkpoints
Each is served by vLLM 0.19.1 on GPU3 :8304, text-only (`Gemma4ForCausalLM` override), with the same flags.

| group | checkpoints |
|---|---|
| 31B reference and Google releases | bf16 (reference); QAT-ct (Google -ct export); QAT-unquantized (Google release) |
| 31B Q4_0 PTQ | PTQ-Q4_0 (bf16 → llama.cpp Q4_0 grid, fake-quantized) |
| 31B community 4-bit | QuantTrio AWQ 4-bit; cyankiwi AWQ-4bit (compressed-tensors); Intel AutoRound int4 |
| 31B community other | RedHat FP8-dynamic; RedHat NVFP4 |
| smaller Google | 12B QAT-ct; E4B bf16; E4B QAT-ct |

- If a checkpoint fails to load or serve, record the error and move on. Nothing is patched to make it load.

## Metrics per checkpoint
Endpoint audit (`audit.py`): generation-mode teacher forcing, top-20, shipped sampler T = 1 / top-k 64 / top-p 0.95 rebuilt.

1. **Held-out new/old string-end margins.** Report the median and p10 of m = log P(`<|"|>`) − log P(best look-alike).
   - m is censored when no look-alike is in the top-20; the censoring fraction is reported.
   - The lower bound m_lb = lp(`<|"|>`) − lp_20 is used for censored states.
   - Both statistics are exact whenever the quantile itself is uncensored.
2. **P(m < ln 19).** This is exact, because any look-alike with m < ln 19 is in the top-20.
3. **E_slip:** the mean sampler look-alike probability at held-out valid new/old string ends.
4. **Onset per-call slip probability:** clean-history valid calls, p_call = 1 − Π(1 − p).
5. **Logged held-out slip states** (n = 8): descriptive only.
6. **Paired contrasts vs 31B bf16 on identical states:** episode-cluster bootstrap, 95% CI.

## Audit flag rule (`audit-weights`; vs the bf16 reference of the same family, same states)
- **FLAG** if P(m < ln 19) ≥ 0.5%, OR the median margin deficit vs bf16 is ≥ 3 nats.
- **SEVERE** if P(m < ln 19) ≥ 2%, OR E_slip ≥ 1%.
- The weights-only proxy is reported alongside as "screen only"; it never sets a flag.

## Repair of flagged checkpoints (recipe fixed in advance, no tuning)
- **Recipe:** identical to repairA. Match-all targets (bf16 teacher), λ = 1e4, ρ = 0, α = 1, ε = μ = 1e-3, p_min = 1e-4. Rank 81 (`<|"|>` + 80 look-alikes), last decoder layer `down_proj` LoRA.
- **Fit data:**
  - fitted only on THAT checkpoint's calib valid string ends (HF teacher-forced extraction of that checkpoint on `core_items_qat.jsonl`, with the bf16 extraction as teacher);
  - preserved keys: calib generic PNC, protected, in-string content, openers, wikitext-2 validation.
- **Eligible checkpoints:** those whose weights can be loaded exactly into HF Gemma-4 (bf16 skeleton plus an exact dequant overlay: compressed-tensors int4 and FP8, Q4_0 PTQ, bf16 releases). Others are recorded as "not repairable with this tool version".
- **Evaluation:** held-out, exact offline, then vLLM + LoRA over the served quantized base.
  - Primary for the sweep repairs: reduction of P(m < ln 19), and of onset E_onset. A "big gain" claim requires ≥ 50% reduction with CI lower bound > 0 on either, with all side-effect gates passing.
  - Also reported: margin-deficit restoration R_med, E_pop (all states), and gap closure vs bf16.
- **Side-effect gates** are the same as T3: G2/G3 thresholds on held-out PNC text, the 24 odd wikitext-2 test windows, protected content and premature close; G4 byte identity ≥ 95%; G5 vLLM fidelity.

## Order
1. Sweep all checkpoints (endpoint audit).
2. Flag.
3. Repair the most severely flagged eligible checkpoint first.
4. Report each, positive or negative.

## Amendment (2026-11-05 15:10 UTC, PI decision; before any sweep number)
- repairA FAILED G4: held-out byte identity 89.0%, from premature closes at in-string line ends. It does not ship.
- The repair step of this sweep uses the FIRST recipe that passes ALL gates (G1-G5) on QAT-ct. That is candidate B if it passes; B is defined in CANDIDATE_B.md.
- If no recipe passes, the sweep is AUDIT-ONLY: flags are reported, and no repaired checkpoint is claimed.
- Execution: the sweep may also run on GPU2 (window 15:10-15:55) and on GPU0/GPU2 after about 16:50. The states, metrics and flags are identical on every GPU.
