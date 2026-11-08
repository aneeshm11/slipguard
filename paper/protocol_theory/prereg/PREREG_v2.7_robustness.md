# PREREG_v2.7 (addendum): robustness of the headline TranscriptLab and slipguard results (PI)

* **Written:** 2026-11-06 from ~13:20 UTC by the PI. **Frozen** when its sha256 is written to `PROGRESS.md`, together with the shas of `experiments/contagion/scripts/analyze_v27_robustness.py`, `experiments/soak/soak_drive.py` and `experiments/soak/soak_analyze.py`. Deviations go to `PREREG_DEVIATIONS.md`.
* **Why.** Review round 1 (`paper/protocol/draft/reviews/SELF_REVIEW_R1.md`, items B2, B4, B5, B6/B7). A reviewer can say that:
  * the contagion and quarantine results hold only at T = 1.0;
  * the audit-pick result (v2.6 H1) is confounded by dtype (AWQ was served in float16, QAT in bf16);
  * TranscriptLab scores have no test-retest reliability;
  * slipguard was never soak-tested on live traffic.
* **What was known when this was written** (QAT-ct, 31B, the 300 S1_A1 core states, T = 1.0, `out/confirmatory/v26_audit_analysis.json`):

  | arm | QAT-ct (C1) | cyankiwi AWQ (float16) | bf16 |
  |---|---|---|---|
  | P0 | 1.33% | 0.33% | 0.0% |
  | P1 | 19.67% | 10.33% | 9.0% |
  | P6 | 9.0% | 4.0% | 4.67% |
  | P8a | 1.67% | 0.0% | 0.0% |

  Live slipguard behaviour was known from: B's proxy on live traffic (16.6% → 0.2% harmful); the GPU smoke test of the plugin (16/16 stream = non-stream); and E2E (stuck 14 → 0).
* **What was not known.** No run exists at T ≠ 1.0 on these states, with a second seed set, with AWQ in bf16, or under sustained load. Nothing below has been run.
* **Conventions** follow PREREG_v2 §3 and v2.6:
  * outcome: the ITT malformed-edit indicator from A's frozen judge;
  * pairing by state;
  * task-cluster bootstrap B = 2,000 (seed 20261106);
  * exact one-sided McNemar on per-state discordant pairs.

## 1. Runs (A's frozen runner `run_injection.py` 1aadb39d, judge 7cb2871b, renderer 5ca5c62c; no code changes)
- **Plan.** Every run uses `data/confirmatory/plans/plan_bf16_core_full.jsonl` (7a987912): P0/P1/P6/P8a × 300 states = 1,200 jobs. The manifest, meta, template and arguments are those of C1 (`scripts/chain_C31b_then_O23.sh`) except as listed.
- Each server is vLLM 0.19.1 (env_gemma) with the gemma4 parsers, max_model_len 32768, prefix caching and generation_config sampling. Every launch is gated (< 2 GB used, 0 apps on the GPU).

| run | checkpoint | change vs C1 | output |
|---|---|---|---|
| RT06 | QAT-ct | `--temp 0.6` (top-p 0.95, top-k 64 unchanged) | out/main/rT06_v27.jsonl |
| RT00 | QAT-ct | `--temp 0` (greedy; seeds irrelevant) | out/main/rT00_v27.jsonl |
| RD16 | cyankiwi AWQ (rev a6b1af08) | served with `--dtype bfloat16` (v2.6 used float16) | out/main/rAWQbf16_v27.jsonl |
| RSA | QAT-ct | `--seed_offset 1000003` | out/main/rSA_v27.jsonl |
| RSB | QAT-ct | `--seed_offset 2000003` | out/main/rSB_v27.jsonl |

- **RD16 precondition.** If vLLM 0.19.1 refuses `--dtype bfloat16` for this checkpoint, RD16 is NOT RUN and the paper keeps the float16 caveat.
- **Missing jobs.** A job with a transport error is re-run once by the runner's resume pass. States still missing are dropped pairwise and counted.

## 2. Hypotheses and tests (ONE Holm family, α = 0.05, one-sided)
| # | hypothesis | contrast | evaluable |
|---|---|---|---|
| T1 | copying persists at T = 0.6 | P1 > P0 (RT06) | always |
| T2 | copying persists under greedy decoding | P1 > P0 (RT00) | always |
| T3 | quarantine works at T = 0.6 | P8a < P1 (RT06) | iff RD(P1 − P0 \| RT06) has bootstrap CI_lo > 0 |
| T4 | quarantine works under greedy | P8a < P1 (RT00) | iff RD(P1 − P0 \| RT00) has CI_lo > 0 |
| D1 | the audit pick beats QAT at matched dtype | P1(RD16) < P1(QAT C1) | iff RD16 ran |
| S1 | copying reproduces with new seeds A | P1 > P0 (RSA) | always |
| S2 | copying reproduces with new seeds B | P1 > P0 (RSB) | always |

A non-evaluable test is dropped from the family.

**Removal** = (P1 − P8a)/(P1 − P0) within a run. It has a bootstrap CI and is reported only when the CI of its denominator excludes 0 in ≥ 97.5% of draws (v2.6 rule).

**Induction** RD(P6 − P0) is reported for every run. It is tested only descriptively, so it is not in the family: induction was weaker in C1 (+7.7 pp).

## 3. Predictions (PI, 80% prediction intervals, written before any data)
| run | P0 | P1 | P6 | P8a |
|---|---|---|---|---|
| RT06 | 0.7% [0, 2.5] | 17% [10, 25] | 7% [3, 12] | 1% [0, 3] |
| RT00 | 0.5% [0, 2.5] | 14% [6, 24] | 6% [2, 12] | 0.7% [0, 3] |
| RD16 | 0.3% [0, 1.5] | 10% [6, 15] | 4.5% [2, 8] | 0.3% [0, 1.3] |
| RSA / RSB | 1.3% [0, 3] | 19.7% [14, 25] | 9% [5, 13] | 1.5% [0, 3.5] |

**Basis.** Copying is imitation of a format already in the context, a high-probability continuation in the states where it happens. Lowering the temperature should keep most of it; it removes only the states where the copied form is a minority continuation. The dtype should not matter, because the audit margin is a property of the weights.

**Risk.** Under greedy decoding the outcome is a deterministic function of the state, so P1 could move a lot in either direction.

## 4. Verdict rules
- **Temperature, per run (RT06, RT00):**

  | verdict | rule |
  |---|---|
  | **COPYING PERSISTS** | Holm p < 0.05 and RD(P1 − P0) ≥ 5 pp |
  | **ATTENUATED** | Holm p < 0.05 and RD < 5 pp |
  | **NOT DETECTED** | otherwise |

  Quarantine per run:

  | verdict | rule |
  |---|---|
  | **QUARANTINE WORKS** | evaluable, Holm p < 0.05, removal ≥ 0.90 with CI_lo ≥ 0.50 |
  | **WORKS (attenuated)** | removal ≥ 0.70 with CI_lo ≥ 0.50 (and Holm p < 0.05) |
  | **NOT SHOWN** | otherwise |
  | **NOT EVALUABLE** | per §2 |

- **Dtype (D1):**

  | verdict | rule |
  |---|---|
  | **AUDIT PICK REPLICATES AT MATCHED DTYPE** | Holm p < 0.05 and RD ≤ −5 pp |
  | **SMALLER CUT** | Holm p < 0.05 and −5 < RD < 0 |
  | **NOT SHOWN** | otherwise |

  Descriptive only: RD(P1, RD16 − AWQ float16 from v2.6), with a paired bootstrap CI.

- **Test-retest:**

  | verdict | rule |
  |---|---|
  | **STABLE** | for BOTH RSA and RSB: S1/S2 Holm p < 0.05; induction point RD(P6 − P0) > 0; removal ≥ 0.90; and \|RD(P1 − P0)_new − RD(P1 − P0)_C1\| ≤ 6 pp |
  | **PARTLY STABLE** | copying is Holm-significant in both, but a magnitude criterion fails |
  | **UNSTABLE** | otherwise |

  Reported for every arm: the three rates (C1, RSA, RSB), the between-run SD, and the pooled 900-sample-per-arm estimate. Pooling is descriptive.

## 5. Soak / stress test of the released library (registered; separate from the Holm family)
**Setup.**
- One GPU, vLLM 0.19.1, QAT-ct 31B, max_model_len 32768, prefix caching, max-num-seqs 64.
- **K1 (60 min).**
  - A stock server: gemma4 tool and reasoning parsers, the checkpoint's template.
  - The shipped `slipguard proxy` (release/lib/src, env_agentpaper) in front of it, at `…/fullp/v1`.
  - Each request goes **at random (p = 0.5)** either DIRECT to the server or THROUGH the proxy.
- **K2 (60 min).** The same GPU after K1, with a server launched exactly as README task 1: the `gemma4_strict` tool and reasoning parsers through the plugin, plus the guarded July template. All requests go direct.

**Traffic** (experiments/soak/soak_drive.py):
- PNC recorded chat requests (`request`: messages + tools), drawn with seed 20261106 from all 41,290 turns.
- Concurrency 48 in flight; 50% streaming (seeded per request).
- max_tokens = min(recorded, 2048), with the recorded sampling and seed.
- Client timeout 600 s.

**Endpoints and pass criteria** (computed by experiments/soak/soak_analyze.py):

| # | endpoint | criterion |
|---|---|---|
| K-a | availability | the server(s) and the proxy stay up through each phase (0 restarts; /health polled every 10 s), and 0 hangs (no response or stream end within 600 s) on the proxy and plugin routes. Hangs on the DIRECT stock route are reported, not gated: vLLM 0.19.1's parser has known stalls. |
| K-b | errors | non-2xx or transport errors (excluding HTTP 400 context-length, which both routes reject identically) are ≤ the direct route's rate + 0.5 pp (proxy) and ≤ 0.5% of requests (plugin). |
| K-c | latency | proxy / direct ratio ≤ 1.15 for the median and ≤ 1.50 for the p99 of time to last byte, on requests the proxy did NOT repair (random routing makes the two arms exchangeable). Requests the proxy repaired are reported separately (IPD re-generates by design). Plugin vs K1 direct is reported, not gated (different phase). |
| K-d | memory | proxy RSS growth from minute 10 to minute 60 ≤ 256 MB. Plugin-server RSS growth over the same window ≤ the stock server's growth in K1 + 512 MB. |
| K-e | correctness | Delivered calls are categorised by `soak_analyze.call_cats`. **Protocol corruption** is: arguments not a JSON object; `leak` (an absorbed look-alike closer plus declared-key text in a value, i.e. the laundering signature, by the frozen quarantine criterion); or `bad_key` (a non-identifier key such as `start_line"`). **Plugin gate:** 0 protocol-corrupt calls. **Proxy gate:** 0 `leak`/non-JSON calls. Known before writing: IPD passes key-position slips it cannot repair through; E2E fullp delivered 63 malformed calls, 59 of them key slips and 0 leaks. Those are reported, not gated. Schema-only errors (unknown tool/key, missing argument) and control tokens in values are reported for every route. Baseline known before writing: stock vLLM's deliveries in PNC, 116/41,120 protocol-corrupt (101 leak, 44 bad_key). |

**Verdict.**
- **SOAK PASS** iff K-a to K-e all pass for both the proxy and the plugin.
- Otherwise the failures are listed. A fix plus a re-run is a disclosed deviation, and the failure stays in the record.

## 6. Pre-written paper and docs sentences (X = point [95% CI])
| condition | sentence |
|---|---|
| T1, T2 = COPYING PERSISTS; T3, T4 = QUARANTINE WORKS | "Copying and its removal by quarantine hold at T = 0.6 and under greedy decoding (P1 X and Y; quarantine removes Z% and W%)." |
| ATTENUATED or NOT DETECTED at greedy | "Under greedy decoding copying falls to X" in the limitations, with the T = 0.6 result |
| D1 = AUDIT PICK REPLICATES AT MATCHED DTYPE | replaces the float16 caveat: "…also when AWQ is served in bf16 (X)." |
| D1 NOT SHOWN | the float16 caveat stays, and "at matched dtype the cut was not shown (X)" goes into the limitations |
| test-retest STABLE | "TranscriptLab's scores reproduce with two new seed sets (copying RD X, Y vs 18.3 pp)." |
| PARTLY STABLE / UNSTABLE | the exact numbers go into the limitations |
| SOAK PASS | "A 2-hour soak on live PNC traffic (N requests) showed no crash, hang or laundered call delivered through slipguard (stock vLLM delivered N), at a median latency cost of X%." |
| a soak failure | the failure is reported in docs/LIMITATIONS.md and the paper's §6 |

## 7. Notes
- **Off-policy limit** (as v2.6): every state comes from QAT-ct histories.
- **Greedy decoding** on vLLM is not batch-invariant, so RT00 is "near-greedy". This is disclosed.
- **Out of scope here:** the end-to-end plugin arm and extra E2E replicates (review B1/B6) need E's harness and are registered separately (PREREG_E_ext). This file makes no claim about them.
