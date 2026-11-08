
## 10. PREREG_v2.5: the full slipguard stack vs the stock stack on public states
The prereg is `paper/protocol_theory/prereg/PREREG_v2.5_stackGain.md` (sha256 50f8a395…). B's deviations are entries
1–6 of `PREREG_DEVIATIONS.md`.

**What was frozen.** `v25/FREEZE_MANIFEST_v25.txt` (2f0c667b…) holds:
- the glue `v25/stack_runner.py`: 21db9d7d…, replaced by d3440af4… after an operational fix (deviation 6: the P8a
  replay built A's prompts in a worker thread);
- the analysis `v25/analyze_v25.py` (b9cc42d2…), run once;
- slipguard and A's scripts, with hashes as registered.

**Pre-run CPU checks** (all passed):
- N1: HistoryGuard leaves the P0 histories unchanged on 300/300.
- HistoryGuard(P1) renders identically to A's P8a context on 300/300.
- I2: the native-results inverse of O1 renders identically to O0 on 600/600.
- Template check: 300/300. With thinking on the two templates are identical. With thinking off the guarded template
  equals the official one plus `<|channel>thought\n<channel|>` (ids 100, 45518, 107, 101).

**Run.** A confirmed the replay preconditions, so the switch rule was not triggered. Everything ran on :8300 (GPU0),
2026-11-05 14:40–15:44 UTC: F3, then the replays of C1 P8a, C1 P0 and v2.3 O0, then L1 live, then F2 live.

| family | STOCK | SLIPGUARD | test (Holm) | verdict |
|---|---|---|---|---|
| **F1** contaminated history (A1, 300; R1 replay primary) | harmful 59/300 = **19.7%** [15.6, 24.5] | **0/300** [0, 1.3]; loud 5/300 = 1.7% | McNemar 59–0, p_Holm 5e-18; reduction **100%** [100, 100]; RD −19.7 pp [−24.5, −15.2] | **GAIN WITH HARM** (the N2 rule fails on 1 case; see below) |
| F1, L1 live (secondary) | — | 0/300; loud 6/300 = 2.0% | consistent with R1 | — |
| **F2** ADK/LiteLLM serialization (600; O0 replay primary) | drift 19/350 edits (5.4%); closer slips 6/600 | drift **0/348** edits; closer slips **0/600**; loud 6/600 | H2a: 19–0, p_Holm 4e-6. H2b: 6–0, p_Holm 0.016 | **DRIFT REMOVED**; closer slips **REMOVED** |
| F2, live first 100 (secondary) | — | drift 0/56 edits; closer slips 0; loud 1 | — | — |
| **F3** thinking-off leak (300) | thought opened 296/300 = **98.7%** | guarded **1/300 = 0.3%** [0.1, 1.9] | McNemar 295–0, p_Holm 6e-89 | **THINKING-OFF HONOURED** |

**No-harm checks:**
- N1: 300/300.
- N3: SLIPGUARD P0 harmful 0/300 vs STOCK 4/300. RD −1.3 pp [−2.7, −0.3] → holds.
- N4: P0 loud 4/300 = 1.3% [0.5, 3.4], below 2%.
- Parser disagreements (slipguard strict vs B's `is_valid`): 0.
- **N2: 1 violation in 1,500 samples.** It is in the F2 O0 replay, `sphinx-doc__sphinx-8595__S1:12`.
  - The base call's last argument is closed by a backtick: `old_string:<|"|>…if not self.__all__:` followed by
    `` ` `` and `}`. vLLM's lenient parse would deliver `old_string` with a stray backtick, and A's judge does not flag
    that.
  - IPD repaired it to the strictly valid intended call.
  - The registered rule allows interventions only at calls A's judge flags, so N2 fails and the frozen F1 verdict is
    **GAIN WITH HARM**. That means no gain sentence under the prereg.
  - Substantively this is a true end-slip that the judge cannot see. It is not an alteration of a valid call: the base
    call was strictly invalid.

**Sensitivity analyses:**
- Excluding the budget-forced records (C1 P8a 1; O0/O1 8) changes nothing: F1 59→0 of 299; F2 drift 19→0 and closer
  slips 6→0 of 592.
- Live and replay agree: L1 at 0/300 lies inside R1's CI.

**Files** (all under `v25/out/`):
- `cpu_checks.json` 2c461808…;
- `f3.jsonl` 56e58214…;
- `replay.jsonl` 46e57811…;
- `live_l1.jsonl` 556b0af6…;
- `live_f2.jsonl` 81b98c6e…;
- `analysis_v25.json` d0a6f6e2…;
- `replay_attempt1_errors.jsonl` 984879ca…, the 300 failed first-pass P8a records, kept for the audit.
