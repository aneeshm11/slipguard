# PREREG_v2 — confirmatory replication on the public natural corpus (workstream P)

* **Written:** 2026-11-04, 14:46–15:10 UTC, by workstream D. **Frozen** when its sha256 is written to
  `PROGRESS.md`. After that, changes go to `PREREG_DEVIATIONS.md` (this folder) with a UTC
  timestamp and a statement of whether any P outcome had been seen.
* **Blindness at writing time.** No P corpus file existed under `experiments/` when this was written (checked 14:45 UTC),
  and D has opened none. Everything below comes from discovery-set results (main-track contexts) and from P's design as
  stated by the PI.
* **Governs:**
  * A's confirmatory arms: 31B {P0, P1, P5, P6, P6k(1, 2, 4), P8a, P8b, P9}; 12B and E4B {P0, P1, P5, P6, P8a};
  * B's first-edit decoder head-to-head: IPD vs T1 vs retry×2 vs grammar-CD vs greedy (31B, thinking on);
  * X's cross-family arms on P contexts {P0, P1L, P1N, P5, P6, P8a};
  * the natural descriptives of P's corpus.
* **Relation to earlier registrations.** PREREG_v1 (sha256 53e34f1f…) and E_PREDICTIONS_v1 (sha256 182365c9…) are
  unchanged. X's own `experiments/crossfamily/prereg.md` (12:15Z) governs X's discovery runs on A's gate contexts.
  PREREG_v2 governs only analyses on P's corpus.

## 1. Discovery set vs confirmation set
* **Discovery = everything measured so far.** Contexts from the team's main-track logs: the official swegemma/ADK harness,
  its system prompt, the competition repos and rebench tasks, the `edit_file(filepath, old_string, new_string)` schema,
  the June-5 template (July only in NT and the replays), and logged temperatures 0.2/0.7. All mechanism estimates (A),
  decoder estimates (B) and natural estimates (D/T3) are discovery estimates.
* **Confirmation = P's public corpus** (design as stated by the PI):
  * Gemma-4-31B-QAT on SWE-bench Verified, about 400 tasks, matplotlib excluded;
  * our own Apache-2.0 harness and system prompt;
  * schema **S1** = `edit_file(file_path, old_string, new_string)`, and **S2** = an OpenHands-style
    `str_replace_editor` on a paired 100-task subset;
  * thinking on; Google's default sampling (T = 1.0, top-p 0.95, top-k 64, from the model's `generation_config.json`);
  * served through E's proxy in its `base` config (vLLM 0.19.1-faithful rendering and parsing; the July template from
    `models/`).
* What changes between discovery and confirmation: harness, system prompt, tasks and repos, the key name (`file_path`),
  the template (July), and the sampling temperature (1.0). The predictions below are transported with explicit
  adjustments for the last two and widened intervals for the rest.

## 2. Context-sampling rule (deterministic; applied by a script hashed before any outcome table is produced)
**Definitions.**
* An *episode* is one task attempt.
* A *state* is the chat request immediately before an assistant turn.
* An *edit call* is an S1 `edit_file` call, or an S2 `str_replace_editor` call with `command = str_replace`.
* A call is *malformed* under A's full vLLM-parse judge, extended with the S1/S2 key names (`file_path`, `old_str`,
  `new_str`, `path`, `command`, `insert_line`): required key missing; look-alike closer + `,<declared key>:` leak; special
  token in a value; unknown key; unparsed call text.
* A history is *protocol-clean* if no call of any tool before the state is malformed.

**Pools** (S1 only; S2 is a separate secondary stratum with the same rules):

| pool | eligibility | used by |
|---|---|---|
| A1 (k = 1 injection) | the state precedes a logged edit call; the history is protocol-clean; the most recent prior edit call is valid and its tool result is a success | A (31B, 12B, E4B), X |
| A2 (dose) | A1 plus ≥ 4 prior edit calls that are valid and succeeded (k_usable ≥ 4) | A's P6k |
| B1 (first edits) | the state immediately before the first edit call of an episode; the history is protocol-clean | B, X census |

**Selection.**
* Rank every eligible state by sha256(`"PREREG_v2|20261105|" + episode_id + "|" + str(turn_index)`), ascending.
* Accept states in rank order subject to the caps.
* **Caps:** at most 2 states per episode in A1 and A2 (the two best-ranked) and 1 in B1. No repository may supply more
  than 40% of the accepted states: once a repository (django in practice) reaches 40% of the target n, its further
  states are skipped.
* **Prompt length:** ≤ 24,000 tokens under the Gemma render, for every pool.
* **Targets:** A1 300; A2 300 (or all eligible if fewer); B1 600. X uses the first 300 of A1 and the first 600 of B1.
  12B and E4B use the same 300 A1 contexts as 31B. Histories are off-policy (written by 31B), as in discovery.
* **Shortfall rule (pre-registered):**
  * if A2 has < 150 eligible states, P6k runs at k ∈ {1, 2} on A1 states with k_usable ≥ 2, and k = 4 on whatever A2 states
    exist; both are reported, k = 4 as underpowered;
  * if A1 has < 300, all eligible states are taken.
* **Internal stability split:** ranks 1–150 (half H1) and 151–300 (half H2) are also reported separately. Claims are judged
  on the full sample.
* **Natural descriptives (§4):** computed on every S1 episode (no sampling), with the same judge.
* Whoever applies the rule computes no outcome summary until the descriptive script (§4) and the arm analyses have
  frozen hashes logged in their own progress files.

## 3. Transported predictions and per-claim outcome rules

**Conventions.**
* Primary estimand for A's and X's arms: *unconditional* (ITT) P(next call is a malformed edit), per context. The
  conditional P(malformed | next call is an edit) is secondary.
* Contrasts are paired by context. CIs come from an episode-cluster bootstrap (B ≥ 2,000, percentile).
* Intervals in this section are D's 80% prediction intervals (PI), not CIs.

**Transport adjustments.**
* Template: where a July-template discovery value exists (A's NT arm), it is the anchor.
* Sampling: onset-type rates are multiplied by 1.12 (T 0.7 → 1.0) to 1.37 (T 0.2 → 1.0). This comes from the calibrated
  margin model, `theory.md` T5 (`sim/out/t5_*`). Copy and contagion rates are multiplied by 1.00, since they sit at deep
  negative margins.
* Harness, prompt and tasks: no point shift; intervals are widened to about twice the discovery CI width.

**Outcome rules.**
* **Risk-difference claims** (discovery point θ_D > 0):
  * **REPLICATES** iff CI_lo > 0 and θ_C ≥ 0.5·θ_D;
  * **ATTENUATED** iff CI_lo > 0 and θ_C < 0.5·θ_D;
  * **FAILS** iff CI_lo ≤ 0.
* **Removal-fraction claims** (quarantine; the plan's rule):
  * **REPLICATES** iff removal ≥ 0.70 with CI_lo ≥ 0.50;
  * **ATTENUATED** iff removal ≥ 0.40 with CI_lo > 0, but the replication rule fails;
  * **FAILS** otherwise.

### 3.1 A: mechanism (31B, pool A1 unless noted)

| # | claim | discovery estimate (uncond.) | transported prediction (80% PI) | rule |
|---|---|---|---|---|
| C1 | a laundered exemplar raises next-edit slips: RD(P1 − P0) | +35.3 pp [29.4, 41.1] (June gate); +33.3 pp [25.5, 41.6] (July, NT) | P0 3% [1, 8]; P1 30% [14, 48]; **RD +27 pp [+11, +45]** | RD; θ_D = 33.3 (July anchor) |
| C2 | format induction without a retry motive: RD(P6 − P0) | +21.3 pp [16.1, 26.4] (gate) | **RD +15 pp [+5, +30]** (new-content-only edits ≥ +10 pp) | RD; θ_D = 21.3. The plan's induction threshold (≥ +5 pp, CI_lo > 0) is also reported |
| C3 | induction accumulates over distinct exemplars, P6k (pool A2): logit linear in log k | cond. 11.7 / 45.1 / 84.1%; Δ₂ = +1.83 [1.45, 2.26]; Δ₄ = +3.69 [3.24, 4.29]; Δ₄ − 2Δ₂ = +0.04 | Δ₂ = +1.6 [0.8, 2.4]; Δ₄ = +3.2 [1.8, 4.5]; Δ₄ − 2Δ₂ ∈ [−0.8, +0.8] | REPLICATES iff Δ₂ CI_lo > 0, Δ₂ ≥ 0.92 and Δ₄ > Δ₂. ATTENUATED iff Δ₄ CI_lo > 0 but Δ₂ < 0.92. FAILS iff Δ₄ CI_lo ≤ 0. The shape is reported, not judged |
| C4 | removal + note removes the excess: P5 | ≈ 108% (P5 −2.7 pp vs P1 +35.3 pp) | removal 1.00 [0.80, 1.15] | removal rule |
| C5 | **shipped quarantine (recovered call) works:** P8a | 113% [107, 122] | 1.05 [0.85, 1.20] | removal rule |
| C6 | shipped quarantine (sanitized): P8b | 112% [105, 121] | 1.00 [0.75, 1.20] | removal rule |
| C7 | informative error feedback does not remove the effect: P9 | keeps 87% of the P1 excess (RD +30.7 pp [25.0, 36.7]) | retention 0.85 [0.55, 1.10] | REPLICATES iff RD(P9 − P0) CI_lo > 0 and retention ≥ 0.50 (CI_lo ≥ 0.25). ATTENUATED iff RD CI_lo > 0 and retention < 0.50. FAILS iff RD(P9 − P0) CI_lo ≤ 0 |
| C8 | 12B: RD(P1 − P0) | +5.0 pp (6.5 vs 1.5%; 600 contexts) | +4 pp [+1, +9] | RD; θ_D = 5.0 |
| C9 | E4B: RD(P1 − P0) | +3.2 pp (5.7 vs 2.5%) | +3 pp [0, +8] | RD; θ_D = 3.2 (FAILS is a live possibility) |
| C10 | small models: induction ≥ copy, RD(P6 − P1) ≥ 0 | 12B +2.3 pp; E4B +5.3 pp | 12B +2 pp [−3, +7]; E4B +4 pp [−1, +10] | REPLICATES iff the point is ≥ 0 and RD(P6 − P0) CI_lo > 0, per model. Otherwise FAILS. Descriptive, not part of any Holm family |
| C11 | 12B/E4B quarantine: P5 and P8a removal | 12B P5 106%, P8a 117%; E4B P5 106% | ≥ 0.70 [0.40, 1.30] | removal rule, per model (small denominators; FAILS by low power is reported as "underpowered" when CI_hi − CI_lo > 1) |

Note: the P1(1) on the k ≥ 4 set was 24.8% in discovery vs 46.2% on the gate set (a selection effect). Pool A2's
absolute rates are therefore predicted lower than A1's, and C3 is judged on logit *differences*.

### 3.2 B: first-edit decoders (31B, thinking on, pool B1)

| # | claim | discovery (June, 600 Gemma-only contexts) | transported prediction | rule |
|---|---|---|---|---|
| C12 | natural first-edit malformed under base decoding (census) | 18.7% (closer slips 17.5%) | 14% [6, 26] (July lowers onset, T = 1.0 raises it ×1.12–1.37) | descriptive (§4 rule) |
| C13 | IPD (i+) relative reduction of delivered-malformed first edits | 93.7% [87.6, 96.9] | 90% [75, 98] | REPLICATES iff CI_lo ≥ 0.50 and point ≥ 0.75. ATTENUATED iff CI_lo > 0 and point < 0.75. FAILS iff CI_lo ≤ 0 |
| C14 | **byte identity:** IPD changes 0 valid calls | 0/480 in-loop; 0/229,414 model-free | 0 changed | REPLICATES iff 0. **Any** changed valid call FAILS (it is a guarantee) and is reported with the case |
| C15 | head-to-head on slips (shares of delivered clean / loud / malformed / silent corruption) | IPD 98% clean; T1 97%; retry×2 24% clean, 76% loud; greedy 84% malformed; grammar-CD 97% silent corruption | IPD clean ≥ 0.90; T1 clean ≥ 0.90 and \|IPD − T1\| ≤ 5 pp; retry×2 loud ≥ 0.50; greedy malformed ≥ 0.60; grammar-CD silent ≥ 0.80 | each decoder's inequality: REPLICATES iff its point satisfies it and its 95% CI excludes the discovery-opposite side of 0.5; otherwise ATTENUATED if the point is on the predicted side, else FAILS |
| C16 | IPD exact intent on real slips (gold from the model's own clean retry, if P yields any) | 97.7% (interim 44/229) | ≥ 0.90 | REPLICATES iff CI_lo ≥ 0.80 |

### 3.3 X: cross-family on P contexts (Qwen3-8B, Qwen3-32B: hermes JSON; Qwen3.5-9B: qwen3_coder XML)
These are a-priori predictions from the Gemma discovery plus the format proposition (theory.md R.2), not from X's
discovery runs (which do not exist yet). The rule labels are **GENERALIZES / PARTIAL / FAILS** (RD rule with θ_D replaced
by the stated point).

| # | claim | prediction (80% PI) | point used as θ_D |
|---|---|---|---|
| X1 | copying a *laundered* exemplar is format-independent: RD(P1L − P0) > 0 in every model | Qwen3-32B +12 pp [+2, +35]; Qwen3-8B +10 [+1, +30]; Qwen3.5-9B +10 [+1, +30] | 12 / 10 / 10 |
| X2 | a format-native slip: hermes P1N is loud, so it exposes raw text (a P3-like confound: the template drops earlier thoughts); XML P1N re-syncs silently with a residue | hermes RD(P1N − P0) +5 pp [0, +25]; XML +5 pp [0, +20] | 5 / 5 |
| X3 | quarantine removes the excess: P5 and P8a removal | ≥ 0.70 [0.40, 1.20] each | removal rule |
| X4 | induction without retry: RD(P6 − P0) | +5 pp [0, +20] per model | 5 |
| X5 | natural census malformed edit (base decoding, pool B1) | ≤ 2% for every Qwen model (teacher logs 0.46%) | descriptive |

### 3.4 Global statements the paper may make
* "**The laundering loop replicates on a public corpus**" iff C1, C2 and C5 all REPLICATE.
* "**Replicates with attenuation**" iff each of C1, C2 and C5 is at least ATTENUATED.
* Otherwise "**partially replicates**", listing the failing claims.
* "**The fixes replicate**" iff C5 (or C4), C13 and C14 REPLICATE.
* "**Generalizes across families**" iff X1 GENERALIZES in ≥ 2 of 3 Qwen models.

## 4. Predicted natural descriptives of P's corpus (31B, S1, all episodes)
The rule for each descriptive: **CONSISTENT** iff the observed 95% CI overlaps the 80% PI; otherwise **HIGHER** or
**LOWER** than predicted (no pass or fail language).

| # | descriptive | discovery (June logs, teacher-free) | prediction (80% PI) |
|---|---|---|---|
| D1 | first-edit onset: P(first edit call malformed) | 17.4% (16.8% by chain) | **13% [5, 25]** |
| D2 | later edit, clean history (K = 0) | 4.3% [3.6, 5.1] | 4% [1.5, 10] |
| D3 | observational contagion: P(malformed \| ≥ 1 malformed edit in context) | K = 1: 59.8%; replay (July): 64.8% | **55% [30, 80]** |
| D4 | immediate retry after one malformed edit (R = 1, D = 1) | 77.6% [74.0, 80.8] | 72% [45, 90] |
| D5 | ratio D3 / D2 | ≈ 14 (59.8 / 4.3) | ≥ 4 (point 12) |
| D6 | closer slips as a share of malformed edits; backtick share among closers | 88.9%; 84–86% | ≥ 70%; ≥ 60% |
| D7 | `old_string` lost in closer slips | 96.4% | ≥ 85% |
| D8 | malformed calls per episode (all tools) | ≈ 1.6 (edit only 1.21) | 1.0 [0.3, 2.5] |
| D9 | stuck episodes (≥ 5 consecutive malformed calls) | 9.8% | 6% [2, 15] |
| D10 | S2 (`str_replace_editor`) first-edit onset (paired 100 tasks) | — | 10% [3, 30] |
| D11 | a malformed call re-enters history well-formed (laundered), under E's base proxy | 53% (C, June template) | 50% [25, 90] |

## 5. Statistics and firewall
* **Families (Holm within each):**
  * F1c mechanism: C1, C2, C5, C4;
  * F3c decoders: C13 vs base, plus IPD vs each baseline on delivered-malformed;
  * F2c cross-family: X1 per model and X3 (P5) per model.
* Everything else is secondary or descriptive.
* **Reporting:**
  * risk differences first;
  * no headline ratio with an infinite CI;
  * conditional estimands beside the unconditional ones;
  * H1 and H2 halves beside the full sample;
  * S2 as a separate stratum.
* **Firewall:** P's outcome files are opened only by the scripts governed here, after this file's PROGRESS.md line exists.
  Any analysis not listed here is labelled exploratory.
* **Interpretation:** a FAILS on the confirmation set does not erase the discovery result. Both are reported, and the
  paper's claims are restricted to what REPLICATES.
