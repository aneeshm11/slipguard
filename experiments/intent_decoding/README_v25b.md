
## 11. PREREG_v2.5b: the same stack on Gemma-4-E4B (F1, R1 replay only)
The prereg is `paper/protocol_theory/prereg/PREREG_v2.5b_stackGainE4B.md` (sha256 c78e7512…). B's entries 1–5 are in
`PREREG_DEVIATIONS.md`.

**Code.**
- Glue: `v25b/stack_runner_e4b.py` (f3e4d7ae…), the v2.5 glue with paths only changed.
- Analysis: `v25b/analyze_v25b.py` (c1569986…), the v2.5 analysis restricted to F1/R1, with H1-E4B alone at α = 0.05.
- Both were frozen before any outcome was opened.

**Preconditions** (all held, so no switch rule fired):
- Re-render length equals the logged length for P0, P1 and P8a, 300/300 each.
- Stop id 49 only. One budget-forced record, in P1.
- HistoryGuard(P1) renders identically to A's E4B P8a context, 300/300.
- N1 holds, 300/300.
- :8311 is the same server process that served A's E4B run, so no record is a cross-server resume.

**Run.** The IPD resumes ran on :8311 (≤ 8 requests in flight) at about 21:14 UTC: 600 replays, 17 IPD interventions,
about 1 GPU-minute.

**F1 on E4B (300 states):**
- Harmful next edits fall from 21/300 = **7.0%** [4.6, 10.5] to **0/300** [0, 1.3].
- Exact McNemar 21–0, p = 4.8e-7. Relative reduction **100%** [100, 100]; RD −7.0 pp [−10.0, −4.3].
- Loud refusals: 2/300 = 0.7%.
- The sensitivity analysis excluding the budget-forced record gives the same result.

**No-harm checks:**
- N1 holds.
- N3 holds: P0 harmful falls from 7/300 to 0/300, RD −2.3 pp [−4.1, −0.7].
- N4: P0 loud is 3/300 = 1.0%.
- Parser disagreements: 0.
- **N2 fails: 3 violations in 600 samples.** Each is an IPD intervention on a strictly invalid call that A's judge
  does not flag:
  - `pydata__xarray-3976__S1:37` (P0): `old_string` opened with a Python `"""`;
  - `pytest-dev__pytest-7186__S1:8` (P8a): both strings opened and closed with `"""`;
  - `sympy__sympy-13840__S1:28` (P8a): the last argument is closed by `}` with no delimiter.

  In every case IPD's output is strictly valid and carries the intended content. No valid call was altered.

**Verdict, as frozen: GAIN WITH HARM.** No cross-size claim is made, and the result goes to the limitations. As in
v2.5, the gain itself is unambiguous. The verdict is set by the N2 rule, which counts any repair of a protocol
violation that the registered judge does not see (opener drift, unterminated last argument) as a violation.

**Files:**
- `v25b/out/analysis_v25b.json` 49f19530…
- `v25b/out/replay.jsonl` b695c6cb…
- `v25b/out/cpu_checks.json` 2c461808…
- `v25b/out/preconditions_e4b.json` 3c422c2c…
