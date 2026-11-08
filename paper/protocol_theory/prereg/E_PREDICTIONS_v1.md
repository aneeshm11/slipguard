# E_PREDICTIONS_v1: D's numeric predictions for workstream E's pre-registered end-to-end endpoints

* **Written:** 2026-11-04 ~12:10 UTC by workstream D. **Frozen** when its sha256 is logged in `PROGRESS.md`.
  This is before the deadline of 2026-11-06 00:00 UTC and before any pre-registered E run exists. E's code freeze is Nov 5
  12:00, after which the population and branch runs start.
* **What D has seen of E** (disclosed):
  * E's `README.md` (design), the definitions in `analysis/pilot_metrics.py`, and `progress.md` up to 11:55 UTC;
  * this includes one tiny *operational* exercise (E4B, 20 contexts): delivered-malformed edits base 2/15, ipd 1/19, full 0/17;
  * D has **not** opened any pilot outcome file (`results.json`, `runs/`, `analysis/*_metrics.json`, `*_events.jsonl`).
* **Basis.** Main-track logs, teacher-free (theory.md T3), A's injection gate, B's IPD numbers, C's slip-class shares, and
  theory.md §R (Property F1, the R.3 corollary). Every interval below is D's subjective 80% prediction interval.
* Endpoint definitions are E's (`pilot_metrics.py`):
  * **delivered-malformed** = the call the client received was malformed (all tools);
  * **wasted** = delivered-malformed calls + tool results with a protocol error type;
  * **stuck** = ≥ 5 consecutive malformed calls.

## 0. Anchors (base 31B-QAT, June template, main-track logs; E runs the July template, so absolute rates are uncertain)

| quantity | value |
|---|---|
| malformed `edit_file` calls per attempt | mean 1.21 (SD 4.19), median 0 |
| attempts with ≥ 1 malformed edit | 22.4% |
| stuck attempts | 9.8% |
| first edit malformed | 17.4% |
| malformed edits before the first clean edit | 0.86 |
| `edit_file` share of all malformed calls | 75% (read_file 18%, write_file 6%) |
| malformed per onset | 5.15 |
| KM E[min(L, 30)] | 12.1 |

* **IPD(i+) coverage of base slip classes** (C): closer slip 88.9% + opener drift 0.2% covered. key_drift 6.0%,
  unparsed_call 2.2% and others are not covered.
* **IPD efficacy** (B): 31B thinking-on first edit 11.2% → (i) 1.1% → (i+) 0/89.
* **Quarantine** (A, 31B gate): P1 46.2% → P4/P5 3.4%; error message only (P2) 1.3%.

## 1. Co-primary endpoints (31B population, official harness, 113 tasks × {base, full′} × 2 seeds)

| endpoint | base (per episode) | full′ / base | prediction for E's success criterion |
|---|---|---|---|
| delivered-malformed tool calls | 1.4 [0.6, 2.5] | **0.12 [0.04, 0.25]** (cut −88% [−75, −96]) | "full′ cuts ≥ 70% with CI excluding 0": **holds, P = 0.85** |
| wasted calls | 1.5 [0.7, 2.7] | **0.15 [0.05, 0.30]** (−85% [−70, −95]) | — |

*Mechanism.* Under full′ the covered slips (~89%) are repaired before delivery and enter history valid (Cor. 3.4(iv)). The
uncovered ones (~11%) are delivered once and then quarantined. Hence delivered/base ≈ (1 − 0.89κ)·(1/(1 − q_Q))/E[L], with
κ ≈ 0.95, q_Q ≈ 0.05–0.10 and E[L] ≈ 5, plus new failure classes (missing opener after a forced thinking-budget end, key
restart) that widen the interval.

## 2. Secondary endpoints (31B population)

| endpoint | prediction |
|---|---|
| stuck episodes | base 8% [3, 15]; full′ ≤ 1% [0, 2] |
| emitted (pre-repair) slip rate on the FIRST edit call | base ≈ full′ (difference within ±3 pp): IPD acts after emission, and the first edit has a clean history in both arms |
| time to first applied edit | mean 0.9 [0.3, 1.6] agent turns earlier under full′; median difference 0 |
| resolve rate (paired, McNemar) | full′ − base = +1.5 pp [−2, +5]; the −3 pp non-inferiority margin is met with P = 0.85; superiority not detectable (MDE 6–8 pp) |
| generated tokens per episode | full′/base = 0.97 [0.90, 1.03] (removed wasted turns outweigh B's ≈ +1.8% IPD overhead) |
| emulated 4×L4 wall-clock | full′/base = 0.98 [0.90, 1.08] |
| 12B population | base delivered-malformed per episode 0.5 [0.15, 1.5]; full′ cut −65% [−35, −90] (more uncovered classes: missing opener, key drift) |
| E4B population | base 0.4 [0.1, 1.5]; full′ cut −70% [−35, −95] (E4B errors are mostly opener drift, which (i+) covers; key restart is not) |

## 3. Branch-at-onset (31B: 150 branch points, about 40–60 natural onsets; cap 40 calls)
The corrupted first edit (natural slip, or injected P1 corruption) is in history in every arm. The quantity is
**post-onset delivered-malformed calls per branch, excluding the onset call itself**.

| stratum | base | quar | ipd | full′ |
|---|---|---|---|---|
| natural onset | 5 [2, 11] | 0.45 [0.15, 1.2]: content stickiness survives quarantine (h ≈ 0.6) | 0.2 [0.05, 0.6]: decode-time repair also catches sticky retries | 0.15 [0.03, 0.5] |
| injected (P1) | 2.3 [1, 5] | 0.05 [0.01, 0.2] (A: P4 3.4%) | 0.10 [0.02, 0.3] | 0.03 [0, 0.15] |
| pooled relative cut | — | **−85% [−65, −95]** | **−92% [−80, −98]** | −95% [−85, −99] |

* E's criterion "quarantine and IPD each cut post-onset malformed calls by ≥ 50%" **holds, P = 0.90**.
* **Causal q_r in the base arm:**
  * first post-onset edit malformed: natural 0.75 [0.60, 0.88], injected 0.43 [0.33, 0.55];
  * second, given the first: natural 0.82 [0.65, 0.92], injected 0.70 [0.50, 0.85].
  * The q₂ > q₁ rise is expected partly from selection (contexts that copied once copy again). It is **not** by itself
    evidence of run-length reinforcement (theory.md R.1). The pre-registered r-dose arm of A identifies that.
* 12B and E4B branch points (mostly injected): post-onset base 0.16 [0.05, 0.5] (12B) and 0.10 [0.02, 0.4] (E4B).
  Quarantine and IPD each cut these by ≥ 50% (P = 0.75 for 12B; underpowered for E4B).

## 4. D's predictions P-a, P-b, P-c, stated in terms of E's design
* **P-a (lever crossover with model size).** Let s_post = (post-onset share of base wasted calls), read from the population
  base arm as calls after the first malformed call of an episode. Let g_Q and g_I = (relative cut of post-onset wasted calls
  under quar and ipd at branch points). Quarantine's predicted removal of *total* waste is s_post·g_Q. IPD's is
  ≥ (1 − s_post)·0.9 + s_post·g_I.
  * **31B:** s_post = 0.80 [0.65, 0.90], so quarantine removes ≥ 0.60 of total waste (point 0.68); IPD ≥ 0.85.
  * **12B/E4B:** s_post = 0.25 [0.10, 0.40], so quarantine removes ≤ 0.30 of total waste (point 0.22); IPD ≥ 0.70.
  * The crossover (IPD ≫ quarantine) is predicted for the small models only. With E's arms, P-a is evaluated through this
    decomposition. If a quar-only population arm is added, it is evaluated directly with the same numbers.
* **P-b (repair written into history ≈ repair + quarantine).** At 31B branch points, post-onset delivered-malformed per
  branch under ipd vs full′ differs by ≤ 0.15 calls (absolute) and the relative cuts differ by ≤ 10 pp. *Emitted* slips at
  the first post-onset edit stay high under ipd (≈ base: the exemplar is still visible) but fall to ≈ P0 under full′; the
  repaired call then becomes the most recent exemplar.
* **P-c (quantization does not drive contagion; F's probes).** At post-slip states, R_post = E[s_bf16/s_QAT | slip] ∈
  [0.8, 1.25] (contagion margins are about −5.5 nats, far beyond a few-nat perturbation). Contrast the onset value
  R = 0.235 (theory.md T5).

## 5. What would falsify the underlying theory (beyond missing a point estimate)
* full′/base for delivered-malformed > 0.5 at 31B. Repair-in-history would then *not* prevent contagion, contradicting
  Cor. 3.4(iv) and assumption V.
* A first-edit emitted slip rate that differs between base and full′ by > 5 pp. That would mean an implementation side
  effect on the first emission.
* quar ≥ ipd at 31B *natural* onsets by a wide margin (> 0.5 calls per branch). That would contradict the content-stickiness
  account (h < 1).
* R_post ≪ 1.
