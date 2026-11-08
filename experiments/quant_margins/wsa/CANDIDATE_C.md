# CANDIDATE_C — third and FINAL repair candidate (workstream F), frozen before any C fit

**Frozen** 2026-11-05 about 16:50 UTC. No C adapter, C selection run or C number existed at this time.

**Disclosure.** This is the third and final candidate. It was designed after two gate failures:
- repairA failed held-out G4 (89.0% byte identity: premature closes at in-string line ends);
- candidate B failed its calib-only behaviour gate (94%: the newline-vs-close choice before the closer, and the first content token after a string opener).

All three candidates are reported. If C fails, weight repair ends and the result is reported as a negative with the mechanism. No threshold is changed.

## Design
- **Targets:** look-alike suppression only, exactly as B (`la_rel_dq_onesided`, p_min = 0). Each look-alike's log-odds against `<|"|>` moves DOWN to the bf16 teacher value at calib valid string ends. There is no `<|"|>` target.
- **Output-span restriction (new):** the edit may move ONLY look-alike logits relative to everything else.
  - The output basis is the minimum-movement right inverse of the look-alike rows, under the metric of all OTHER logits (including `<|"|>`):
    B_out = M⁻¹ K (Kᵀ M⁻¹ K)⁻¹, with K = D E_LAᵀ (5376 × 80), M = D Γ_rest D + ε·mean(diag)·I, Γ_rest = (EᵀE − E_LAᵀE_LA)/V, D = diag(g ⊙ g_pf).
  - To first order, a unit move of look-alike logit t then changes no other look-alike row, and its squared movement of every non-look-alike logit is minimal.
  - The LoRA rank is 80 (look-alike rows only; `<|"|>` is not an output direction).
- **Key map (stage 2):** as before, A = T Kᵀ (KKᵀ + λ(n/N_p) C_p + μI)⁻¹, with T = per-position look-alike targets / κ_i.
- **Preserved keys (calib only)** = B's set (generic PNC, protected look-alike content, in-string content, openers, wikitext-2 validation, the 2,135 in-string line-end negatives) PLUS two new hard-negative classes from a QAT-ct HF extraction of the 300 calib valid items (`out/hf_qatct_cneg_calib.pt`):
  - (i) `postopen`: the position predicting the FIRST content token after the opener `<|"|>` of every new/old value;
  - (ii) `nlclose`: the position predicting the newline token that immediately precedes a closer, i.e. where "\n then `<|"|>`" competes with "`<|"|>` now".

## Selection (calib inner CV only; the same cv split)
- **Grid:** λ ∈ {1e3, 3e3, 1e4, 3e4, 1e5}.
- **Criterion:** the largest margin gap closure (ratio of sums, deficit ≥ 1 nat) on cv = 1, subject to:
  - all G2/G3 thresholds (generic PNC, wikitext-2 validation, protected);
  - premature close ≤ 0.5% at in-string content and at line ends;
  - top-1 changed ≤ 0.5% at BOTH postopen and nlclose positions (new, offline proxies of the two B failure modes).
- **Tie rule:** within 2 points, take the larger λ. If no λ passes, C stops with no gate run.

## Calib behaviour gate (before any held-out look)
- 100 calib valid calls DIFFERENT from B's gate set: items 101-200 of `data/items_calib_valid.jsonl`, where B used 1-100.
- Greedy regeneration on the vLLM server (QAT-ct base vs C LoRA), same procedure as G4, with the zero-weight-adapter floor on the same calls.
- PASS iff byte identity vs base ≥ 95% and the valid-call rate is not lower. Otherwise STOP.

## Held-out (only if the calib gate passes)
- The frozen held-out metrics (ANALYSIS_PLAN amended: E_pop + G1-G5, plus addendum secondaries), computed once.
- G4 on the 200 FRESH held-out calls reserved for B (`data/items_heldout_g4_fresh.jsonl`, still unused).
