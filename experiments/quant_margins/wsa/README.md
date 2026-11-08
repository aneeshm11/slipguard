# Weight-space audit and repair of the quantization-induced protocol defect (workstream F, 2026-11-05)

**Goal.** Check whether a Gemma-4 checkpoint closes code strings with `<|"|>` or with a look-alike closer. Then repair the
quantized checkpoint with a closed-form, minimal weight edit, shipped as a tiny LoRA that vLLM serves over the W4A16 base.
No LLM is in the loop, and nothing is trained by gradient descent.

Decision points come from the public PNC corpus only (`data/pnc`). Main-track data is not used.

## Status
<!-- STATUS -->
FINAL (2026-11-05 19:45 UTC). Results with JSON citations: `RESULTS.md`. audit-weights ships as `release_audit/` (wsa-1.0, frozen); weight repair ended. The three repair candidates (repairA/B/C, `repair_memit.py`, `lora_io.py`, `adapters/repair*`) **did not pass the registered gate** and are research code only. Running log: `../progress.md`.

## Decision points (T1)
- `build_points.py` → `data/pnc_points_all.jsonl`, covering every PNC turn whose first tool call is the edit tool.
  - **Valid calls.** These are vLLM-faithful parses with all three string arguments present and no look-alike leak. Their decision positions are the closing `<|"|>` of path, new and old.
  - **Slips.** These are look-alike closers followed by `,<key>:`. The decision position is the look-alike token.
  - **Protected positions.** These are look-alike tokens that are legitimate string content.
  - **Split.** sha256(episode_id) parity separates `calib` from `heldout`.
- **Prompt rendering** (`pnc_render.py`) uses the corpus chat template with the system message as text parts, as vLLM 0.19.1 renders it. It reproduces the logged `prompt_tokens`.
- `select_core.py` → `data/core_items.jsonl`: all slips plus 450 valid items per split, with total tokens ≤ 21k.
  - `data/core_items_qat.jsonl` holds 651 items: the slips plus 300 per split.
  - `data/audit_items_16k.jsonl` holds the held-out items that fit every server's KV cache.

## Measurements
- **Endpoint audit** (`audit.py`, library `audit_checkpoint`). Generation-mode teacher forcing against any OpenAI-compatible endpoint returning logprobs, with no `prompt_logprobs`.
  - **Sampler.** The shipped sampler (T=1, top-k 64, top-p 0.95) is rebuilt from the top-20 log-probs.
  - **Scores:**
    - `E_slip`: the mean look-alike probability per string end, with an episode-cluster bootstrap CI;
    - the per-call slip probability;
    - margin quantiles, where margin = log P(`<|"|>`) − log P(best look-alike).
- **Exact HF extraction** (`hf_extract.py`). One forward pass per item on one GPU. Arms:
  - `bf16`;
  - `qatct`: an exact int4 dequant overlay of the -ct checkpoint, the same rounding Marlin uses;
  - `ptq`: on-the-fly llama.cpp Q4_0;
  - `qatunq`, `qatfq`.
  - Per position it stores h, x_L, PRE-softcap logits of `<|"|>` and the 80 look-alikes, lse and lse_rest, the top-20, exact sampler masses, the last-layer down_proj input and output, and per-layer residuals for the D subset.
  - It also stores positions for side-effect checks: generic PNC prompt/completion text, wikitext-2, protected content, in-string content and string openers.
- `t1_scores.py` computes per-arm scores and paired contrasts. `temperature_baseline.py` checks whether the defect is temperature-like. `weights_proxy.py` is a weights-only screen.

## Repair (T3)
`repair_memit.py` implements a closed-form, MEMIT-style edit of the last decoder layer's `down_proj`, exported as a PEFT LoRA by `lora_io.py`.
- **Why `down_proj`.** vLLM 0.19.1 cannot put a LoRA on Gemma-4's `lm_head`: the vocab of 262,144 exceeds its 258,048 limit.
- **Why exact offline evaluation is possible.** A last-layer MLP edit changes only that position's own x_L, so its effect at every extracted position is exact:
  - x_L' = x_L + s·(pf(y + ΔW a) − pf(y));
  - h' = RMSNorm(x_L');
  - z' = E h'.
- **Stage 1: targets.** Restore the bf16 teacher's log-odds of `<|"|>` and of every look-alike against the unchanged rest of the vocabulary, at calibration decision points.
- **Stage 2: output basis.** B = (D(E_SᵀE_S + ρΓ)D + εI)⁻¹ D E_Sᵀ, with D = diag(g ⊙ g_pf) and Γ = EᵀE/V.
- **Stage 3: key map.** A = T Kᵀ (KKᵀ + λ(n/N_p) C_p + μI)⁻¹, where C_p is the key covariance of preserved positions. ΔW = B A, of rank ≤ 81.
- **Gate (PI).** Held-out E_slip must fall by ≥ 50% vs QAT-ct, with no regression on:
  - held-out NLL on PNC text and wikitext;
  - KL at other tokens;
  - valid-call byte identity (`byte_identity.py`).
  - `lora_validate.py` checks that vLLM + LoRA reproduces the offline predictions.

## Files
- **Data:** `data/` (points, core items, wikitext-2 test).
- **Outputs:** `out/` (`hf_*.pt` extractions, `t1_scores.json`, `audit_*.json`, `repair_*.json`).
- **Adapters:** `adapters/`.
- **Logs and downloads:** `logs/`; every download is listed in `DOWNLOADS.log`.
- **Drivers:** `gpu3_chain.sh`, `gate_eval.sh` and `t1_sweep.sh` run on GPU3 and only with the PI's approval.
- **Library:** `release_audit/wsaudit` (audit-weights only; sha list in RESULTS.md §7). `slipweights.py` is a superseded stub (its `repair_adapter` is NOT part of slipguard).
