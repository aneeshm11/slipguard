
## 7. Confirmatory run on workstream P's fresh corpus (PREREG_v2 §3.2: C12–C16)
Everything above uses the main-track logs: that is the **discovery** set. The confirmatory run uses workstream P's
fresh corpus (SWE-bench tasks, our harness, Gemma-4-31B-QAT, thinking ON). B has not opened P's data. It is read
only by the frozen scripts below, after PREREG_v2 is frozen.

- **Frozen package `confirm/`.** Frozen 2026-11-04 15:45 UTC, before the pools existed. Combined sha256 (= sha256
  of `confirm/FREEZE_MANIFEST.txt`): `2ee89869735ea76514908f0a3626c362bfd58ec93de40ab608536cee4a84e2b0`. Per-file
  hashes are in `confirm/FREEZE_MANIFEST.txt`. The package imports only its own frozen copies of the library, plus the
  frozen closer prior `prior_ft_edit.json` (505 main-track fine-tune slips, add-½).
- **States.** Pool B1 of stratum S1 (A's `POOLS_MANIFEST.json` → `S1_B1.jsonl`), in rank order, the first 600.
  One sample per state.
- **Rendering.** The corpus manifest's chat template and kwargs, with system content as text parts when declared.
  The token count must equal the logged `prompt_tokens`; otherwise the state is recorded as `render_mismatch`.
- **Sampling.** P's: T = 1.0, top-p 0.95, top-k 64. The thinking budget is emulated. If the natural next call is not
  the edit tool, an edit call is forced and flagged, as in discovery.
- **Arms**, on the same baseline sample with the prefix pinned: IPD (i+), retry ×2, greedy, grammar-CD. T1,
  lenient and fail-loud are computed offline.
- **Claims and rules** (abridged from PREREG_v2 §3.2; the PREREG text governs):

  | # | claim | discovery | prediction | rule |
  |---|---|---|---|---|
  | C12 | natural first-edit census-malformed under base decoding | 18.7% (closer slips 17.5%) | 14% [6, 26] | descriptive |
  | C13 | IPD relative reduction of delivered-malformed first edits | 93.7% [87.6, 96.9] | 90% [75, 98] | REPLICATES iff CI_lo ≥ 0.50 and point ≥ 0.75; ATTENUATED iff CI_lo > 0 and point < 0.75; FAILS iff CI_lo ≤ 0 |
  | C14 | byte identity: IPD changes 0 valid calls | 0/480; 0/229,414 model-free | 0 | any changed valid call FAILS |
  | C15 | head-to-head on slips | IPD 98% clean; T1 97%; retry×2 24% clean, 76% loud; greedy 84% malformed; grammar-CD 97% silent | IPD clean ≥ 0.90; T1 clean ≥ 0.90 and \|IPD − T1\| ≤ 5 pp; retry×2 loud ≥ 0.50; greedy malformed ≥ 0.60; grammar-CD silent ≥ 0.80 | per decoder: REPLICATES iff the point satisfies it and the 95% CI excludes the opposite side of 0.5 |
  | C16 | IPD exact intent on P's real slips (gold from a later clean retry) | PREREG: 97.7% (interim 44/229); final discovery 507/519 = 97.7% (§4.5c) | ≥ 0.90 | REPLICATES iff CI_lo ≥ 0.80; NOT_ESTIMABLE if P yields no such slip |

- **F3c family (Holm).** C13 vs base, plus IPD vs each baseline (lenient, T1, retry ×2 lenient, greedy, grammar-CD)
  on delivered-malformed: exact McNemar, Holm-adjusted. Halves H1 and H2 are reported beside the full sample. S2 is
  a separate stratum if `S2_B1.jsonl` exists.
- **Schedule.** Run on Nov 5 after the user's green light (S1 07:05–08:42 UTC, S2 08:44–08:53 UTC). Outputs:
  `out/confirm_S1_B1.jsonl`, `out/confirm_S1_B1_analysis.json` and `out/confirm_gold_S1.jsonl`. They are reported as
  an addendum to this README and to `results.json`, with no change to the frozen code.
- **Run log.** PREREG_v2 pools applied 2026-11-05 07:02:24 UTC (A's `POOLS_MANIFEST.json`, script sha256 60025bef…):
  - S1 B1 has 600 states (236 verified, 364 extended); S2 B1 has 82.
  - The confirm/ hashes were re-verified before launch (combined sha256 2ee89869…, unchanged).
  - S1 started 07:05 UTC on :8302, with --conc 22 --workers 10 (≤32 requests in flight, prefix pins included).
  - P's manifest gives the chat template path relative to the manifest (`chat_template.jinja`, md5 f016bd4b…, the
    July template that P's server used). The frozen runner opens that path as given, so it runs with the manifest
    directory as working directory, as P's manifest note prescribes. No code was changed.
  - Rendering: the first states render to exactly the logged `prompt_tokens`, with system content as parts.
- **Verified-only analysis.** `confirm_subset.py` restricts the runner output to `verified_only/S1_B1.jsonl`, and the
  frozen `confirm_analyze.py` is applied to it unchanged.
- **Operational.** S1 was restarted once at 172/600 records (07:27 UTC) to raise workers from 10 to 14. The runner
  resumes by context, and in-flight states were re-run with the same per-context seeds. All 600 S1 states and 82 S2
  states rendered to exactly the logged `prompt_tokens`, with 0 errors and 0 preemptions.

### 7.1 Confirmatory results (FINAL; `results.json` → `confirmatory_PREREG_v2`)
**S1 B1, all 600 states** (600 edit calls, 239 forced; P's sampling at T = 1.0):

| claim | result | verdict |
|---|---|---|
| C12 census-malformed first edits | 13/600 = **2.2% [1.3, 3.7]**: natural 3/361 = 0.8%, forced 10/239 = 4.2%; closer slips 13/600 | **LOWER** than predicted (80% PI 14% [6, 26]; §4 descriptive rule) |
| C13 IPD relative reduction | 13 → 1 census-malformed (the 1 is not a slip): **92.3% [66.7, 98.6]** | **REPLICATES** |
| C14 byte identity | **0/582** valid calls changed | **REPLICATES** |
| C15 IPD clean on slips | 13/13 | REPLICATES |
| C15 T1 clean on slips | 13/13; IPD − T1 = 0 | REPLICATES (within 5 pp) |
| C15 retry ×2 loud | 2/13 (11/13 clean) | **FAILS**: at T = 1.0 most retries succeed |
| C15 greedy delivered-malformed | 5/13 | **FAILS** (prediction ≥ 0.60) |
| C15 grammar-CD silent corruption | 10/13 = 77% | **ATTENUATED** (prediction ≥ 0.80) |
| C16 IPD exact intent on P's real slips | 0 eligible slips | **NOT_ESTIMABLE** (see below) |

- **F3c, delivered-malformed over all 600 calls, IPD 0/600** (exact McNemar, Holm):
  - vs lenient 13/600: p_Holm = 0.0012;
  - vs grammar-CD 12/600: 0.0020;
  - vs greedy 7/600: 0.047;
  - vs retry ×2 with lenient fallback 3/600: 0.50 (n.s.);
  - vs T1 0/600: 1.0.
- **Verified-only sub-population (236 states):**
  - C12 7/236 = 3.0% [1.4, 6.0].
  - C13 85.7% [48.7, 97.4] → ATTENUATED: the lower bound just misses 0.50, with 7 events.
  - C14 0/228 changed → REPLICATES.
  - C15 verdicts are the same as on the full set.
- **Post-hoc split** (the PREREG defines halves for A1 only), ranks 1–300 / 301–600:
  - C13 100% [70.1, 100] (9 events) → REPLICATES, vs 75% [30.1, 95.4] (4 events) → ATTENUATED;
  - C14 0/289 and 0/293 changed.
- **S2 B1** (separate stratum, `str_replace_editor`, 82 states):
  - C12 4/82 = 4.9% [1.9, 11.9], with **0 closer slips**. The four malformed calls are a YAML-style argument block
    inside `command`, `// comments` between arguments (2), and a bash command sent as `command`.
  - IPD has no slip site to repair in any of them, so C13 = 0% → FAILS by rule. Under IPD's strict policy these four
    fail loud: 0/82 delivered malformed vs 4/82 lenient (Holm p = 0.63).
  - C14 0/78 changed; C15 is NOT_ESTIMABLE (no slips).
- **C16 NOT_ESTIMABLE.** The frozen `confirm_gold.py` found **0** S1 B1 states whose logged first edit is a
  `new_string` closer slip with a later clean retry that matches the registered G1 rule (same `file_path`,
  `new_string` equal to the payload).
  - The documentation says this is not a missing-field artifact. CONTEXT_SCHEMA §3 lists `outcomes.raw_response_text`.
    P's `build_contexts.py` writes it from `raw_completion`, and P's `integrity.py` requires that field to be
    non-empty. `outcomes.jsonl` exists (17.5 MB).
  - Field presence was not checked by opening outcomes, per the PI's instruction (documentation and file existence
    only).
  - With base onset at 2.2%, only about 13 slips are expected before the retry-match filter.
- **Reading.**
  - On P's fresh public corpus the first-edit closer slip is about 8× rarer than in the main-track logs (2.2% vs
    17.5–18.7%). It is lower than D's transported prediction.
  - Where slips occur, IPD repairs all 13 and never alters a valid call (0/582).
  - The decoder-ranking claims about the baselines do not transport to T = 1.0. Retry mostly succeeds, greedy mostly
    repairs, and grammar-constrained decoding still silently corrupts 77% of slips.
  - B's part of "the fixes replicate" (C13 and C14) holds on the full sample. C5/C4 are A's.
