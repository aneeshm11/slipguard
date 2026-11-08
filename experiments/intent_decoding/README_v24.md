
## 9. PREREG_v2.4: injected-slip repair battery on public states (gold known by construction)
The prereg is `paper/protocol_theory/prereg/PREREG_v2.4_injectedSlipRepair.md` (sha256 e7af894b…). B's pre-data
operationalisations are entries 1–13 of `PREREG_DEVIATIONS.md`. The frozen package is
`v24/FREEZE_MANIFEST.txt` (sha256 7c18f256…), with analysis 25a5d20c… and runner 08bf695d….

**Design.**
- **Calls:** 600 strictly valid `edit_file` calls from P's public S1 corpus, each with tool result `ok`, from 458
  episodes. They were taken in sha256 rank order with seed 20261105, at most 2 per episode and at most 40% per repo.
- **Injection:** the logged thought and call are teacher-forced up to the closing `<|"|>` of `new_string`. That
  delimiter is replaced by one of four closers, 150 states each: BT `` ` ``, DQ `"`, EQ `\"`, TB ```` ``` ````. The
  31B QAT-ct then continues live at P's sampling (T 1.0, top-p 0.95, top-k 64), with one seed per state.
- **Arms:** seven decoders run on the identical slipped prefix, using B's frozen code (`confirm/`).
- **Run:** :8300 (GPU0), 2026-11-05 12:42–14:38 UTC, 600/600 states, 0 errors. `v24/run_manifest.json` records
  `/v1/models` and the server's command line.
- **Estimates:** strata are reweighted to the natural closer mix (BT 0.865, DQ 0.082, EQ 0.037, TB 0.016). Single rates
  use Wilson at the Kish effective n; contrasts use an episode-cluster bootstrap with B = 4,000.

**Injection mechanics** (ITT, reweighted), i.e. what the model wrote right after the injected closer:
- **slip pattern** (the closer is followed by the next key): 81.6% [75.6, 86.4];
- **doubling** (the model also writes `<|"|>`): 14.6% [10.3, 20.1];
- **content continuation** (the model keeps writing `new_string` content): 3.8% [1.9, 7.5].

EQ (`\"`) is mostly undetectable: 70 doubling and 57 continuation out of 150. The detectable subset (the emission is
strictly invalid) is 393/600 states: BT 136, DQ 73, EQ 60, TB 124.

**Detectable subset, reweighted.** Outcomes are judged against gold. Each cell is the share of detectable slips.

| arm | exact intent | silent corruption | delivered-malformed | loud | other valid | `new_string` exact |
|---|---|---|---|---|---|---|
| **IPD (i+)** | **90.6% [85.4, 94.1]** | 6.9% [4.0, 11.6] | 0.1% | 0.8% | 1.6% | 92.8% |
| T1 text-only | 83.6% [77.4, 88.3] | 9.1% | 0.0% | 2.4% | 4.9% | 88.5% |
| lenient | 0.0% | 1.1% | 98.9% | 0 | 0 | 0.0% |
| fail-loud | 0 | 0 | 0 | 100% | 0 | 0 |
| grammar-CD | 0.0% | 3.1% | 96.9% | 0 | 0 | 0.0% |
| retry ×2 (T 1.0) | 65.3% | 4.5% | 0 | 0.8% | 29.5% | 66.8% |
| greedy | 69.0% | 4.1% | 0.7% | 0 | 26.2% | 69.1% |

- **IPD vs T1:** **IPD BEATS T1**. Exact intent is +7.0 pp [+3.2, +11.2] higher, Holm p = 0.003. The secondary,
  unadjusted contrasts point the same way:
  - composite closers (EQ + TB): +10.3 pp [+5.7, +15.4];
  - `new_string` exact on composite closers: +4.3 pp [+1.2, +7.8];
  - BT: +6.6 pp [+2.2, +11.5].
- **Holm family F-R** (12 tests):
  - IPD has higher exact intent than each of the 6 baselines (all Holm p = 0.003).
  - None of the 6 "IPD has less silent corruption" tests is significant. Under the pre-declared outcome order, the
    baselines' damaged calls count as delivered-malformed or loud rather than silent.
- **Rules R1–R8:**
  - R1 (IPD exact ≥ 0.85, CI_lo ≥ 0.75), R2, R5 and R6 **REPLICATE**.
  - **R3 FAILS:** IPD's silent corruption is 6.9%, against ≤ 2%. In 27 of the 28 cases one injected look-alike
    character is left at the end of `new_string`.
  - **R4 FAILS:** grammar-CD's silent share is 3.1%, against ≥ 0.80. This follows from B's pre-declared order, which
    checks "malformed under A's/E's judge" before "silent".
    - Exploratory: 393/393 grammar-CD outputs on detectable slips are strictly valid but wrong, with the look-alike
      `,key:` residue inside the value. Under a silent-first order they would all be silent corruption, as in discovery.
  - **R7 and R8 FAIL:** retry ×2 reaches 65.3% exact and greedy 69.0%. The injected states were valid originally, so
    resampling from the call head often reproduces the gold call.
- **ITT** (all 600):
  - IPD exact intent 77.8%, T1 71.9%.
  - Every parser-based arm carries 15–22% silent corruption, driven by doubling and continuation, which no decoder can
    detect.
- **Cost per state:**

  | arm | tokens | latency |
  |---|---|---|
  | IPD | 139 | 63 s |
  | the live emission alone (T1, lenient and fail-loud add nothing to it) | 94 | 29 s |
  | retry ×2 | 219 | 67 s |
  | greedy | 200 | 59 s |
- **Files:**
  - `v24/battery_inputs.jsonl` (f5c7839e…) and `v24/battery_manifest.json` (366ab3da…);
  - `v24/battery_run.jsonl` (ce230afc…);
  - `v24/battery_run_analysis.json` (8c97e05f…) and `v24/battery_run_analysis_states.jsonl` (16af4c7a…).
