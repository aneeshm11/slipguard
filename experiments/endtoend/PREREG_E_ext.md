# PREREG_E_ext — eight fresh end-to-end replicates: resolve non-inferiority and replication of the co-primaries

Written by the PI on 2026-11-06 (see PROGRESS.md for the freeze time and sha256s), before any E_ext episode. It
extends PREREG_E (frozen 2026-11-05 07:14, manifest DIGEST c9c20591). Code, harness, proxy, tasks and arms are
PREREG_E's, unchanged. The user granted all free GPUs for 48 h at ~17:45 UTC on Nov 6.

## 1. Why
- **Resolve.** PREREG_E's resolve non-inferiority (NI) test at −3 pp was declared underpowered (MDE ≈ 6–8 pp) and was
  not met in either replicate: rep1 +1.8 pp [−4.4, +8.0], rep2 −1.8 [−8.9, +5.3]. So the paper claims no resolve
  effect. Reviewers will ask whether slipguard can cost task success.
- **Co-primaries.** The fresh replicates also give an independent replication of PREREG_E's co-primary result
  (malformed calls per episode 2.47 → 0.27).

## 2. Design
- **Replicates r3 … r10 (8 fresh).** Each is the 113 eligible tasks (configs/eligible_113.txt) × arms {base, fullp},
  split into the registered halves (configs/eligible_113_half0/1.txt).
  - A **lane** is one (replicate, half) on one vLLM server, with both arms on the same server, as in PREREG_E (no
    server × arm confound).
  - Command per lane (PREREG_E's frozen launcher, unchanged):
    `bash run_population.sh <server>/v1 gemma-4-31b <QAT-ct dir> subs/sample_noadapter pop31r<k>s<h> configs/eligible_113_half<h>.txt <proxy port> 3 pop31r<k>`
  - The CRN seed salt is `pop31r<k>`, shared by both halves of replicate k. The salts differ from r1/r2, so these are
    fresh replicates.
- **Servers.** vLLM 0.19.1, Gemma-4-31B QAT-ct, PREREG_E's server arguments:
  - tools/serve_vllm.sh defaults: max-model-len 32768, gpu-mem 0.90, prefix caching, max-logprobs 20;
  - plus `--max-num-seqs 64 --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4`;
  - one server per GPU, on any GPU that passes the user's gate.
- **Sandboxes.** The rootless dockerd on cores 150–175 (the frozen launcher pins proxies and harnesses to 140–149). At most 3 lanes run at once, i.e. 18 sandboxes. Lanes start in
  replicate order: r3s0, r3s1, r4s0, …
- **Blinding.** No resolve or malformed-call outcome is looked at before the analysis set is final (§4). Only
  operational QA is allowed: tests/smoke_qa.py, completion counts, 5xx/tracebacks, infra errors.

## 3. Endpoints and analysis (analysis/prereg_E_ext_analysis.py, frozen with this document)
The script imports PREREG_E's frozen analysis/prereg_analysis.py unchanged: load_proxy, load_arm, task_mean,
boot_paired, boot_ratio, wilson, mcnemar, B = 10,000. Every bootstrap seed is passed explicitly as a fixed integer,
which avoids the hash-seed issue documented in EXPLORATORY_bootseed. Infra-error episodes are excluded as in PREREG_E.

- **Primary (NI).**
  - Statistic: per task, the mean over the analysed fresh replicates of (fullp resolved − base resolved).
  - Mean difference over tasks with the paired task bootstrap (boot_paired, seed 20261107).
  - **RESOLVE NON-INFERIOR** iff the 95% CI lower bound is > −0.03; otherwise **NI NOT SHOWN**.
  - The point estimate and CI are reported either way.
- **Secondary S1 (replication of co-primary Y1).**
  - Malformed calls per episode, base vs fullp: task means over replicates.
  - Ratio fullp/base with boot_ratio (seed 1); difference with boot_paired (seed 20261108).
  - **REPLICATES** iff ratio ≤ 0.30 and the difference CI excludes 0 (PREREG_E's success rule).
- **Secondary S2 (Y2, wasted calls):** same statistics, seed 20261109. Reported.
- **Secondary S3 (stuck episodes, pooled over the fresh replicates):** base vs fullp counts, with an exact McNemar over
  paired (task, replicate) episodes. Reported.
- **Descriptive (sequential, labelled as such):** the same NI statistic pooled over all 10 replicates (r1–r10).

## 4. Analysis set and stopping rule (fixed now)
- Replicate k is **complete** when both halves × both arms have a per_task.jsonl line for every task of that half.
- **The analysis set is r3 … rK.** K is the largest index such that every replicate r3..rK is complete, evaluated at
  the earlier of: (a) all 8 complete; (b) 2026-11-08 14:00 UTC.
- If K < 6, i.e. fewer than 4 fresh replicates, the NI test is reported as **UNDERPOWERED** (descriptive only).
- The analysis runs **once**, on that set. Lanes still running at the cutoff are stopped, and their partial data are
  not analysed.

## 5. Predictions (written before data)
| endpoint | prediction | basis |
|---|---|---|
| Resolve difference | 0.0 pp, 95% CI half-width ≈ 3–4 pp with 8 replicates | 26 of 113 tasks have mixed outcomes across the 4 existing episodes |
| P(NI met \| true difference 0) | ≈ 0.5 (Jeffreys-shrunk task rates) to 0.8 (raw rates) | tmp/ni_power.py simulation |
| Y1 ratio | ≈ 0.11 [0.07, 0.18] | PREREG_E 0.11 [0.06, 0.22] |
| Stuck episodes | base ≈ 6% of episodes, fullp ≈ 0 | |

## 6. What gets written
| result | text |
|---|---|
| NI met | "Across eight fresh replicates (N episodes), resolve rates were non-inferior at −3 pp (difference X [lo, hi])." Replaces "we claim no resolve effect". |
| NI not shown | "Across eight fresh replicates, the resolve difference was X [lo, hi]; non-inferiority at −3 pp was not shown." Keeps "no resolve claim", with the tighter interval. |
| S1 | "The co-primary result replicates in eight fresh replicates (Y1 a → b, ratio r [CI])", or the failure, stated plainly. |

## 7. Deviations
Logged in experiments/endtoend/PREREG_DEVIATIONS.md under "E_ext", with UTC time and before/after-data status.
