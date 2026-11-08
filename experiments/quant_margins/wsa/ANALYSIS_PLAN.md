# ANALYSIS_PLAN — weight-space audit (T1) and repair (T3), workstream F

**Written** 2026-11-05 about 12:40 UTC. No QAT-ct number on the PNC decision points existed or had been opened at writing time: `out/hf_qatct.pt` did not yet exist. The bf16 31B numbers were already seen (progress.md 12:35).

**Frozen** when its sha256 is recorded in `PROGRESS.md`. Every deviation is logged at the end of this file, under "Deviations", with a UTC time and whether it was decided before or after seeing the governed data.

## Data and splits (fixed)
- **Decision points.** Public PNC corpus only: `data/pnc_points_all.jsonl` (sha256 e8364526…). No main-track data.
- **Split.** `split = calib` if `int(sha256(episode_id)[:8], 16) % 2 == 0`, else `heldout`.
- **Item sets:**

  | File | Contents | sha256 |
  |---|---|---|
  | `data/core_items.jsonl` | 951 items: all 51 slips plus 450 valid per split, ≤ 21k tokens | 23a1377e… |
  | `data/core_items_qat.jsonl` | 651 items: slips plus the first 300 valid per split, interleaved | 75765a3f… |
  | `data/audit_items_16k.jsonl` | held-out items with ≤ 16.4k tokens, for the endpoint sweep | 4d1b8dee… |

- **Inner CV**, used for every tuning decision. Within calib only, `cv = int(sha256('cv|' + episode_id)[:8], 16) % 2`. Fit on cv = 0 and evaluate on cv = 1.
- **Leakage rule.** Held-out positions are never used for fitting, probing designs, or the choice of λ / ρ / α / iterations or of any other hyperparameter.

## Measurement
- **Exact (primary).** HF teacher forcing (`hf_extract.py`) gives full-vocabulary distributions at identical token prefixes for:
  - bf16 (`models/gemma-4-31b-it`);
  - QAT-ct (the -ct checkpoint, int4 weights dequantized exactly as Marlin computes them);
  - the repaired model. For the last-layer down_proj edit this is computed exactly from the QAT-ct extraction, because the edit changes only the position's own residual.
- **Confirmation.** vLLM 0.19.1 serves QAT-ct + LoRA over the W4A16 base. Checks:
  - `audit.py` endpoint audit, with the sampler rebuilt from the top-20;
  - `lora_validate.py`: offline-vs-vLLM agreement;
  - `byte_identity.py`.

## Endpoints
- **Primary.** E_slip = the mean, over held-out VALID new_string / old_string closer positions, of the shipped-sampler probability of a look-alike closer.
  - Sampler: T = 1.0, top-k 64, top-p 0.95.
  - Look-alikes: the 80 vocabulary tokens made only of quote, backtick or backslash, optionally with a leading ▁ or a trailing comma.
  - It is a continuous, per-string-end quantity.
  - Logged natural slips are too few for a count endpoint (8 held-out), so they are reported descriptively only.
- **Primary contrasts** (held-out; cluster bootstrap over episodes, B = 2000; 95% CI):
  1. T1: QAT-ct vs bf16. Report E_QAT, E_bf16, the ratio, and the difference.
  2. T3: gap closure G = (E_QAT − E_rep) / (E_QAT − E_bf16), plus the relative reduction (E_QAT − E_rep) / E_QAT. Absolute numbers are always reported.
- **Secondary (descriptive):**
  - margin quantiles, where margin = log P(<|"|>) − log P(best look-alike);
  - the share of margins under 2 and under 4 nats;
  - per-call slip probability, 1 − Π(1 − p) over a call's new and old closers;
  - logged slip states (calib n = 43, held-out n = 8);
  - path closers.

## T3 gate (all on held-out; decided now)
Primary candidate: the configuration selected by the inner-CV rule below and refitted on all of calib.

- **G1 (big gain).** The relative E_slip reduction vs QAT-ct must be ≥ 50%, and the lower bound of its cluster-bootstrap 95% CI must be > 0. G is reported alongside.
- **G2 (no NLL regression).** Mean next-token NLL change ≤ +0.01 nats/token on both of:
  - held-out generic PNC positions (prompt and completion text outside tool calls);
  - wikitext-2 test windows (BOS-correct rerun; see the deviations).
- **G3 (no KL / flip regression on preserved positions):**
  - generic PNC + wikitext: mean KL(repaired ‖ QAT-ct) ≤ 0.01 nats, and top-1 changed at ≤ 1% of positions;
  - legitimate look-alike CONTENT inside string values (protected): mean KL ≤ 0.01, top-1 flip ≤ 1%, and mean Δ log p of the logged content token ≥ −0.05 nats. This is measured exactly on the extracted protected positions, and also via the endpoint on all protected positions of the held-out core items (flip rate and Δ log p);
  - in-string content: the rate at which `<|"|>` newly becomes top-1 (premature close) must be ≤ 0.5%.
- **G4 (valid-call byte identity).** Greedy regeneration of ≤ 300 held-out valid calls from the call start, base vs repaired on the same vLLM server:
  - byte-identical ≥ 95%;
  - the repaired valid-call rate must be ≥ the base valid-call rate.
- **G5 (implementation fidelity).** vLLM + LoRA must reproduce the offline predictions: median |Δ log p| over the top-10 ≤ 0.1 nats at the checked string ends.
- **Verdict.** PASS only if G1–G5 all pass. Otherwise the candidate is reported as a negative or a partial result, just as plainly.

## Inner-CV selection rule (calib only)
1. Grid: λ ∈ {0.01, 0.1, 1, 10, 100}, ρ ∈ {0, 1}, α ∈ {0.5, 1.0}, refinement iterations ∈ {0, 1}, with ε = μ = 1e-3 and p_min = 1e-4.
2. Fit on cv = 0 and evaluate on cv = 1.
3. Among configurations meeting the G2/G3 thresholds on the cv = 1 half, choose the one with the largest relative E_slip reduction.
4. Ties within 2 percentage points go to the larger λ, i.e. the more conservative edit.
5. If no configuration meets the thresholds, report that as a negative result and do not loosen the thresholds silently.

## T1 sweep (descriptive)
- Endpoint audit of every servable checkpoint on `audit_items_16k.jsonl`: 31B bf16, QAT-ct, PTQ-Q4_0, QAT-unquantized, AWQ ×2, AutoRound int4, FP8-dynamic, NVFP4, 12B QAT-ct, E4B bf16 and E4B QAT-ct.
- The same states are used for every checkpoint.
- The weights-only proxy (unembedding geometry) is reported with its correlation to E_slip across checkpoints. It is labelled "screen only" because it cannot see PTQ, which keeps the bf16 embedding.

## Deviations
- 2026-11-05 12:40 UTC (before any QAT-ct number). Bug fix, not a design change: the wikitext-2 windows 1..47 in the bf16 and QAT-ct main runs lack `<bos>`, so their NLL (about 8) is invalid. G2/G3 use a BOS-correct wikitext-only rerun (`hf_extract.py --wikitext_only`) for both arms, and the main-run `generic_text` positions are ignored.
- **2026-11-05 13:00 UTC — ENDPOINT CHANGE (decided AFTER seeing QAT-ct numbers on the first 150 valid items; BEFORE any QAT-ct slip-state number and before any repair result).**
  - **What was seen.** The pre-registered primary endpoint (held-out valid-string-end E_slip under the shipped sampler) is degenerate on PNC.
    - Partial QAT-ct (75 held-out items, 150 string ends) gives E_slip = 0.0; bf16 gives 8e-5 on 900.
    - QAT-ct margins are smaller (median 15.6 vs 20.4 nats; 10th percentile 9.1 vs 16.3), but top-p 0.95 removes every look-alike at these valid states.
    - The natural PNC slip rate (51/4,207 calls, 1.2%) is carried by a small set of hard states that valid-call states, selected on success, do not contain.
  - **Changes:**
    1. **New primary endpoint: E_pop**, the population-weighted expected slip probability per first-edit call:
       E_pop = (n_v · mean over held-out valid calls of p_call + n_s · mean over ALL logged slip states of p) / (n_v + n_s), with n_v = 4,074 and n_s = 51 (PNC counts).
       - p is the shipped-sampler look-alike probability, and p_call = 1 − Π(1 − p) over the call's new/old closers.
       - CI: cluster bootstrap over episodes, stratified by stratum.
       - For QAT-ct this estimates its own natural rate (validation: it should be near the observed 1.2%). For bf16 and the repaired model it is unbiased under "same as QAT".
    2. **The repair is fitted on calib VALID string ends only** (new/old/path closers). No logged slip state is used in fitting or in selection, so all 51 slip states (calib and held-out) are out-of-sample test states.
    3. **Inner-CV selection criterion** (calib, cv = 1 valid string ends): maximize mean margin gap closure, mean over i of (m_rep − m_QAT)/(m_bf16 − m_QAT) on states where m_bf16 > m_QAT, subject to the unchanged G2/G3 side-effect thresholds.
    4. **G1 now reads:** the relative reduction of E_pop vs QAT-ct must be ≥ 50%, with the CI lower bound > 0. Gap closure G is computed on E_pop.
    5. **Still reported:** the original valid-string-end E_slip, plus the raw untruncated P(look-alike) at T = 1, as secondary endpoints. G2–G5 are unchanged.
- **2026-11-05 13:15 UTC — GRID EXTENSION (decided after inner-CV results on calib only; no held-out repair result exists).**
  - **What was seen.** The first inner-CV test (match-all targets) dropped 3 of 72 cv = 1 string ends below a 2-nat margin. D's decomposition found that QAT-ct's post-softcap margin loss is softcap saturation plus a RISEN look-alike logit; the raw `<|"|>` logit is not too low.
  - **Change:**
    - Add target modes `la_rel_dq` (match bf16's look-alike-vs-`<|"|>` log-odds; `<|"|>` vs the rest of the vocabulary is unchanged) and `la_rel_dq_onesided` (the same, but look-alikes are only ever suppressed), next to `match_all`.
    - Widen λ to {0.01, 0.1, 1, 10, 100, 1e3, 1e4}.
  - **Selection** follows the same inner-CV rule, applied across modes.
- **2026-11-05 13:30 UTC — SELECTION METRIC FIX (calib-only information; no held-out repair result exists).**
  - **What was seen.** The pre-specified mean of per-state ratios (m_rep − m_QAT)/(m_bf16 − m_QAT) is numerically unstable: on inner-CV stage A it gave −9.2 and +6.8 from near-zero denominators.
  - **Replacement:** the ratio of sums over cv = 1 string ends whose bf16 margin exceeds QAT-ct's by ≥ 1 nat: Σ(m_rep − m_QAT) / Σ(m_bf16 − m_QAT).
  - Thresholds and the rest of the rule are unchanged.
- **2026-11-05 14:2x UTC — GENERAL-TEXT GATE SET (PI integrity note; decided before any held-out repair number).**
  - **What happened.** Earlier inner-CV runs (13:5x-14:1x) used EVEN-numbered wikitext-2 TEST windows: cv = 1 even windows were looked at during λ selection, and cv = 0 even windows were preserved keys.
  - **Fix:**
    - λ selection and preserved keys now use the wikitext-2 VALIDATION split (new download, logged).
    - The G2/G3 wikitext gate uses ONLY the 24 ODD-numbered test windows (768 positions). They were never used in fitting or selection.
    - Selection is redone on calib (inner CV) with the validation split.
