# CANDIDATE_B — second repair candidate (workstream F), frozen before its calib gate

**Frozen** 2026-11-05 about 15:15 UTC. No B adapter, no B selection run and no B number existed at this time.

**Disclosure.** B's design was informed by a HELD-OUT gate failure. repairA failed G4: held-out byte identity was 89.0%, because the match-all targets raised `<|"|>` log-odds and caused premature closes at in-string line ends. The paper reports both candidates.

## Design (mechanism-driven, per D's decomposition)
- **Targets:** `la_rel_dq_onesided`.
  - Each look-alike's log-odds against `<|"|>` is moved to the bf16 teacher's value, and ONLY DOWNWARD (clamped ≤ 0).
  - The log-odds of `<|"|>` against the rest of the vocabulary is unchanged, so the edit never raises `<|"|>`.
  - p_min = 0: no relevance mask, so look-alike targets are active at every valid string end.
- **Same edit family as repairA:** closed form, last decoder layer `down_proj`, rank 81 (|S|), ρ = 0, α = 1, ε = μ = 1e-3. Fitted on calib VALID string ends only, never on slip states.
- **Preserved keys:** the same as repairA (calib generic PNC, protected look-alike content, in-string content, openers, wikitext-2 validation) PLUS in-string LINE-END hard negatives. These are positions inside new/old values that follow a newline token where the content continues: up to 12 per value, QAT-ct HF extraction of the 300 calib valid items (`out/hf_qatct_lineend_calib.pt`).

## Selection (calib inner CV only)
- **Grid:** λ ∈ {1e3, 3e3, 1e4, 3e4, 1e5}.
- **Criterion:** the largest margin gap closure (ratio of sums, deficit ≥ 1 nat) on cv = 1, subject to these thresholds on cv = 1:
  - G2/G3 thresholds on generic PNC, wikitext-2 validation and protected content;
  - premature close (`<|"|>` newly top-1) ≤ 0.5% at BOTH in-string content and line-end positions.
- **Tie rule:** within 2 points, take the larger λ.
- If no λ passes, B stops: there is no held-out look.

## Calib-only behaviour gate (before ANY held-out look)
- Greedy regeneration of 100 calib valid calls on the vLLM gate server (QAT-ct base vs B LoRA), with the same procedure as G4.
- Requirements: byte identity ≥ 95%, and a valid-call rate that is not lower than the base's.
- If B fails here, STOP and report.

## Held-out evaluation (once, only if the calib gate passes)
- **Metrics:** the same primary (E_pop) and gates G1–G5 as ANALYSIS_PLAN (amended), plus the addendum secondaries (a)–(c).
- **G4 uses 200 FRESH held-out valid calls,** not used in repairA's G4 (`data/items_heldout_g4_fresh.jsonl`). repairA's 200 calls are also reported, for continuity.
- **G4 is also reported net of the vLLM noise floor** (base vs zero-weight adapter on the same calls), as a descriptive figure. The verdict uses the frozen 95% threshold.
- **(d), the quarantine + adapter stack** on the 37 contagion states, runs only if B passes all gates.
