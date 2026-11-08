# Workstream E — deviations from PREREG_E.md

Each entry: UTC timestamp · what changed · why · expected impact on the registered endpoints.
(none yet; the registration is frozen 2026-11-05 12:00 UTC)

- 2026-11-04 12:05 UTC · not a deviation from the (draft) registration, recorded for transparency: an automatic
  progress monitor written before the blinding instruction printed per-arm resolve counts of the EXPLORATORY pilots
  p12a/p4a once (12:02 UTC; values in PREREG_E.md §8). Monitor replaced by a pooled-count version at 12:05 UTC.

- 2026-11-04 19:30 UTC · PRE-FREEZE change (not a deviation; the registration is frozen 2026-11-05 12:00 UTC):
  IPD redesigned as workstream B's verify-then-repair with B's strict-validity guard in front of the decode-time,
  post-hoc and quarantine paths, after B's P1 test found the candidate (e2e_proxy.py 0c2a5278…) changed 278/1,200
  adversarial valid calls; whitespace-variant slips handled; declared-keys-only repair sites; separator drift no longer
  repaired by default; B's opener rule. Details: PREREG_E.md §8 "Pre-freeze changes". Expected impact on the endpoints:
  none on `base`; `ipd`/`fullp` can no longer corrupt valid calls (P1), and repair slightly more slips (whitespace
  variants, unfinished calls) — direction of Y1/Y2 effects unchanged.

---- entries below were added AFTER the freeze (2026-11-05 07:14 UTC; the manifest hashes this file as it was then) ----
- 2026-11-05 07:17 UTC · ADDED PRE-LAUNCH, EXPLORATORY, DOES NOT ENTER CONFIRMATORY AVERAGING: a third 31B
  population replicate (official harness, arms base + fullp, CRN salt pop31r3, the same 113 tasks and the same
  server-half split: half0 on :8300 after pop31r2s0, half1 on :8302 after pop31r2s1). Reason: measured 31B episode
  times (6–10 min) leave idle 31B capacity before the Nov 6 00:00 unblinding (PI approval, option (a); no D sign-off
  needed). The registered 2-replicate confirmatory analysis (co-primary Y1/Y2, Holm) is unchanged; the 3-replicate
  recomputation of the same endpoints is reported beside it, labelled exploratory. Decided before any outcome was seen.
- 2026-11-05 08:59 UTC · OPERATIONAL (scheduling only; no data seen; no design or analysis change): per the PI's
  priority rule (registered before exploratory), the 12B population (registered) no longer waits behind E4B at
  2 sandboxes. Scheduler sched_after_rep2.sh (scope ap-e2e-chain-sched) replaces the chains E4B->12B and rep2->rep3:
  the first 31B lane to complete replicate 2 hands its 6 sandboxes to pop12r1 (3 per arm); only the second lane's
  completion starts the exploratory replicate 3 (its half, leftover sandboxes), then the other half on its own lane.
  Arms, seeds/salts, tasks, budgets and the frozen code are unchanged; total sandboxes <= 14.
- 2026-11-05 10:52 UTC · EXPLORATORY REP 3 CANCELLED BEFORE LAUNCH (resource reallocation; no data seen): PI request; the
  31B servers :8300/:8302 are left idle after the registered replicate 2. The 07:17 entry is void; no pop31r3 run exists.
- 2026-11-05 10:52 UTC · OPERATIONAL: systemd on this host failed to add inotify watches for some scopes ("Failed to add
  ... inotify watch descriptor"), so finished harness scopes stayed 'active' with 0 tasks and the run_chain.sh chains never
  fired: lane 1 sat idle from 10:25 (pop31r1s0 complete) to 10:51. Replaced the chains and sched_after_rep2.sh by
  sched_v2.sh (scope ap-e2e-chain-sched2): completion = per_task counts AND 0 tasks in the arm scopes; rep1->rep2 per lane,
  the first lane finishing rep2 -> registered 12B population (3 per arm), the second lane -> idle; idempotent launches.
  pop31r2s0 launched 10:51. Arms, salts, tasks, budgets and frozen code unchanged.
- 2026-11-05 10:52 UTC · BLINDING DISCLOSURE (E's error): while diagnosing the stuck scopes at ~10:48, a 'tail' of the
  harness stdout logs displayed per-arm summary lines for pop31r1s0 (31B replicate 1, half0, 58 tasks per arm):
  "DONE base resolved 25/58" and "DONE fullp resolved 28/58", plus two per-task lines of the base arm (both unresolved,
  one ending by the 100-turn budget). This is the SECONDARY resolve endpoint for half of replicate 1; no co-primary (Y1/Y2)
  data, no slip/IPD counts were seen. No analysis or design decision is affected (all decisions were already fixed).
  Harness stdout logs are not read again before unblinding.
- 2026-11-06 00:06 UTC · UNBLINDING (after all registered populations completed 2026-11-05 21:47:28 and after
  2026-11-06 00:00). Frozen analysis run once per population (31B, E4B, 12B) with analysis/prereg_analysis.py sha
  1f8fca3a… (manifest digest c9c20591… verified). No infrastructure failures in the PREREG §6 sense (0 proxy 5xx), so no
  re-runs. IMPLEMENTATION DISCREPANCY found at unblinding: the frozen script's infra test (error prefix
  'Sandbox execution error: litellm') also matches the proxy's 400 context-length error, which §6 classifies as an
  OUTCOME. It affects only 12B (3 base + 7 fullp episodes; frozen script analyses 103/113 tasks); 31B (co-primary) and
  E4B have no such episodes. Both are reported: frozen output analysis/prereg_pop12B.json and the §6-conforming result
  analysis/prereg_pop12B_sec6conforming.json (wrapper analysis/prereg_sec6_conforming.py, frozen code imported
  unchanged, only that classification changed). Differences: 12B resolve non-inferiority holds in the frozen output and
  not in the §6-conforming one; 12B Y1 significant in both, Y2 not in either.
  Branch-at-onset (registered (b), secondary 7) has NOT been run (31B lanes reallocated by the PI); D's P-a/P-b are not
  evaluable without it.
- 2026-11-06 00:17 UTC · BRANCH-AT-ONSET, PRE-OUTCOME (no branch outcome exists yet; logged before launch):
  (1) Plans built with the frozen build_branch_plan.py (seed 20261105, source = population base arms; 31B r1+r2 in
      r1s0,r1s1,r2s0,r2s1 order): 31B 150 points (14 natural, 136 injected; 8 skipped: 5 no edit_file, 3 proxy 400
      context-length before the onset), E4B 100 (7 natural, 93 injected; 1 skipped), **12B 80 < registered 100** (0
      natural, 80 injected): only 80 of the 113 registered 12B source episodes ever call edit_file (33 skipped,
      'no edit_file call'); the registered source rule caps n, nothing was chosen. plans/b31.json was partitioned
      operationally into b31a (50) / b31b (49) (sorted task ids, alternating; entries incl. branch_id/seeds unchanged)
      so that 31B runs on 3 lanes (b31a, b31b, b31_2), each lane running all 4 arms.
  (2) IMPLEMENTATION DISCREPANCY in the replay-fidelity check, found with a mock-backend pre-check (36 branch points,
      prefix replay only; the mock ends every episode right after the onset, so no outcome was generated): the frozen
      normaliser masks the VALUE of the harness's "budget_warning" annotation but not its PRESENCE; the registered
      40-call branch cap makes the harness add it from call 30 on (absent in the 50-call source episodes), so every
      prefix with >= 30 calls fails the hash although the tool output is identical (31B pre-check: 5/12 flagged; 3 of
      them only for this reason). Also, Docker container ids (64-hex) appear in some error messages. CORRECTED RULE
      (decided now, applied to all arms; frozen code unchanged): a branch point is excluded iff in ANY arm a replayed
      prefix tool result differs from the source episode in tool name, status, error type, or the frozen normalised
      hash computed after removing the "budget_warning" key and masking 64-hex container ids (from the harness traces;
      analysis/branch_fidelity_corrected.py). Pre-check under this rule: 31B 10/12 ok, 12B 12/12, E4B 12/12; the
      remaining 2 are cap-infeasible prefixes (>= 40 tool executions before the onset -> BudgetExceeded), which stay
      excluded: 21 such branch points exist (31B 14, 12B 7, E4B 0). Both the frozen-flag and the corrected exclusion
      counts will be reported; the branch analysis uses the frozen prereg_analysis.py with only the fidelity input
      replaced (wrapper written before any outcome is looked at).
- 2026-11-06 00:19 UTC · PRE-OUTCOME: correction scripts fixed (read-only) before any branch outcome is looked at:
  analysis/branch_fidelity_corrected.py sha256 600a494b580e279190d56671751a39e0a7dbe8c3dd187c1fcfceba7191bfeddb
  analysis/prereg_branch_corrected.py   sha256 9c80a70b7129209c9ce1c948ad8cc495e490a0d83db019c392835a2e8ea647f0
  (tested only on the mock pre-check data: frozen flags exclude 5/12, corrected 2/12 = the 2 cap-infeasible prefixes).
  Launched 00:18 UTC: b12 (12B, :8463 -> :8301, 3 per arm), bE4 (E4B, :8464 -> :8311, 2 per arm); 31B lanes pending.
- 2026-11-06 02:17 UTC · OPERATIONAL OBSERVATION before branch completion (disclosed for transparency): to diagnose a
  slow tail, E looked at per-arm completion counts and the timing of in-flight 31B base-arm branch sessions: the fix
  arms (quar/ipd/fullp) completed first, and several base-arm sessions run ~100 turns alternating ~4.1-4.3k-token
  turns (thinking budget exhausted) with ~0.55k-token turns. No malformed-call counts, resolve outcomes or per-arm
  endpoint values were looked at. No decision depends on it (everything is fixed; runs continue as launched).

## E_ext (PREREG_E_ext.md, frozen 2026-11-06 17:54:21 UTC) — deviations

## E_awq (PREREG_E_awq.md, frozen 2026-11-06 19:56:34 UTC) — deviations

## E_audit / E_comp — 2026-11-07 11:55 UTC (before any E_audit or E_comp episode)
- **Orchestration only (GPU pairing):** the frozen launch used dispatch_q.sh with slots "1 6" (single queue) and "0+2" (bf16 tensor-parallel pair, then "0 2" single). After E_awq2 released GPU 0 at 11:54 while GPU 2 stayed busy until ~12:55, the 0+2 pair would have left GPU 0 idle for ~1 h. The two waiting dispatchers (no server started, no lane launched; only queue claims popQAWQr3s0, popQNVr3s0, popBF16r3s0 held) were stopped, the three claims released, and the same frozen dispatch_q.sh / queues relaunched with slots "0 6" (single) and "1+2" (TP, then "1 2" single). GPU 1 frees ~12:30, so the expected idle drops to ~25 min. Queue order, models, server arguments, launchers, salts and analyses are unchanged; serve_vllm_tp2.sh cores for 1+2 are 76–79 and 80–83.

## E_audit — 2026-11-07 13:41 UTC (backend outage; decided from status codes only, before any outcome of these lanes was inspected)
- **What happened:** E_awq2's dispatcher (ext/dispatch_awq2.sh, derived from dispatch_ext.sh) ends with a cleanup loop that stops every `ap-vllm-g$g-*` unit for g in its GPU list (0 1 2 6). When it finished at 13:05:57, it also stopped the E_audit servers that dispatch_q.sh had started on GPU 0 (QAT-AWQ, :8300) and GPU 6 (QAT-NVFP4, :8306).
  - Lanes popQAWQr3s0 (started 11:59) and popQNVr3s0 (12:42) kept running against dead backends: proxy 504 "backend ClientConnectorError" from 13:05:57 to 13:39, 572 and 515 requests, 0 successful requests after the first 504.
  - The bf16 TP lane (unit ap-vllm-tp-g1g2-*, started 13:12) was not affected (0 errors).
- **Detection:** PI operational QA (status-code counts per proxy log) at 13:39.
- **Action (13:40):**
  1. stopped the waiting/running dispatcher ap-eqsingle06 and both lanes' harness and proxy scopes;
  2. removed only their sandbox containers (label e2e_run);
  3. moved their runs/ and logs/ to experiments/endtoend/discarded/2026-11-07_backend_outage/ (kept, NOT analysed);
  4. released their queue claims;
  5. relaunched the frozen dispatch_q.sh with slots "0 6" (ap-eqsingle06b). It re-runs both lanes in full from the start (same tags, salts, models, arguments).
- **Rule applied (fixed now, before outcomes):** a lane any part of which ran against a stopped backend is discarded entirely and re-run, never partially analysed.
- **Root-cause guard:** no other dispatcher with a global cleanup loop is running (E_awq2's has exited; dispatch_q.sh stops only its own slots' servers).

## E_audit — 2026-11-07 14:17 UTC (bf16 TP engine hang during a node-level GPU-driver stall; decided from status codes and server logs only)
- **The bf16 tensor-parallel server** (GPUs 1+2, :8305, started 13:07:45) stopped producing tokens at ~14:00:00. At 14:04:52 its EngineCore timed out waiting for the TP workers (shm_broadcast TimeoutError → EngineDeadError) and the API server exited. The lane popBF16r3s0 (started 13:12) then got 504s. Detected by the PI's backend-health monitor (≈14:05).
- **Node state at the time:** from ~13:54, processes outside this project (titled VLLM:Worker_D5, GPU 5) were stuck in uninterruptible sleep on NVIDIA driver locks. nvidia-smi calls by several users and a root cleaner hang. runc init and a kernel rcu_gp worker were also in D state. The TP hang is consistent with this node-level stall. The TP scope was also near its memory limit (41 of 50 GB), a possible contributor.
- **Action (14:11–14:16):**
  1. stopped the TP dispatcher ap-eqtp12, the lane's scopes, its 2 containers and the TP server scope (workers are now zombies);
  2. moved the lane's runs/logs and the server log to experiments/endtoend/discarded/2026-11-07_tp_engine_hang/ (NOT analysed);
  3. released the claim.
- **Same rule as the 13:40 entry:** a lane that ran any part against a dead backend is discarded entirely.
- **Not restarted yet:** bf16 TP waits until the node's GPU driver is healthy (nvidia-smi responds). The single-GPU lanes on GPUs 0 and 6 kept serving (HTTP 200) and continue. If bf16 cannot run before LAST_START, T1 is reported as not run (PREREG_E_audit §3–§4: INCOMPLETE).

## E_audit — 2026-11-07 16:43 UTC (lane start timeout; no episode ran)
- **Lane popQAWQr3s1 (16:41) failed to start:** its proxy did not answer /health within run_population.sh's 180 s window ("proxy did not start"); the node was still slow after the GPU-driver stall. No harness started and no episode ran (all proxy logs empty).
- **The dispatcher counted it EXITED EARLY** and moved on, consuming the claim.
- **Action:**
  - moved the empty proxy logs to experiments/endtoend/discarded/2026-11-07_proxy_start_timeout/;
  - released the claim, so the dispatcher re-runs the lane in full later (same tag, salt and arguments).
- **Same rule for any further start timeouts:** release and re-run; nothing partial is analysed.
- **Driver state:** nvidia-smi answers again at 16:43, slowly (48 s). GPUs 1 and 2 still hold ~76 GB each from the exited TP workers (zombies stuck in driver teardown) and stay unusable.

## E_audit / E_comp — 2026-11-07 17:40 UTC (queue paused for node degradation; decided before any E_audit/E_comp outcome was inspected)
- **Node state:**
  - Since the GPU-driver stall (~13:54), a lane proxy takes 330 s (cold) and 375 s (warm) to answer /health (PI test proxy on port 8599 at 17:2x). The frozen launcher (run_population.sh) waits 180 s.
  - Lanes popQAWQr3s1 (16:41) and popQNVr3s1 (17:22) therefore failed to start (0 episodes). Each failure also made the dispatcher switch models (≈ 30 min per load on this node).
  - The QAT-AWQ server on GPU 6 failed at 17:19 with CUDA out of memory: the previous server's memory was not yet released, the same driver-teardown symptom as GPUs 1 and 2.
- **Decision:** pause new lane starts until the node is healthy.
  - Stopped dispatcher ap-eqsingle06b, the start-failure watcher and GPU 0's loading server.
  - Released the never-launched claims popNVr3s0 and popQAWQr3s1.
  - Not chosen: extending the launcher's wait. Episodes on a node this slow (tool timeouts 300 s, sandbox start) may not be comparable with the healthy-node QAT reference they are paired with.
- **Pre-specified now, blind:** the two complete lanes popQAWQr3s0 and popQNVr3s0 were re-run 13:44–16:54, i.e. inside the degradation window. If they enter any analysis set, an EXPLORATORY sensitivity analysis excluding lanes that ran during 13:54–(node recovery) will be reported next to the registered result. Neither currently completes a replicate: each needs its s1 half.
- **If the node is not healthy by 2026-11-08 07:30 UTC:** too late to complete a replicate (2 halves × ~2 h, plus loads) before LAST_START 11:30. E_audit and E_comp are then reported with their registered INCOMPLETE / UNDERPOWERED verdicts (no complete replicate), as an infrastructure failure, in LIMITATIONS.

## E_audit / E_comp — 2026-11-07 19:51 UTC (queue RESUMED on a healthy node after the user's reboot; decided before any E_audit/E_comp outcome was inspected)
- **Context:**
  - At 18:27 the user asked for every process to be cleared for a GPU reboot. The node has now been rebooted: all GPUs at 0 MiB, nvidia-smi answers in 0.09 s, load ~3, no zombie workers.
  - The user then wrote: "Please continue with your experiments, GPU 0-4 are all yours."
  - The 17:40 pause condition ("resume only when the node is healthy", useful-resume deadline 2026-11-08 07:30) is met.
- **Unchanged:** frozen dispatch_q.sh, queue_single.txt / queue_tp.txt, LAST_START 2026-11-08T11:30:00Z, the analysis cutoff 14:00, analysis sets, tests, seeds; at most 4 lanes at once.
- **Operational change (GPU map only):**
  - single-GPU slots on GPUs 0, 1, 2;
  - the bf16 tensor-parallel slot on the pair 3+4 (before the stall: singles 0, 6; TP 1+2).
  - GPU 6 is not ours now. Server cores follow the GPU (tools/serve_vllm*.sh defaults).
- **Cleanup:** removed 6 stopped leftover sandbox containers from the stall (labels popBF16r3s0 ×5, discarded; popQAWQr3s0 ×1, a dead sandbox of the complete re-run). No run directory was touched.
- **Still pre-specified:**
  - the complete lanes popQAWQr3s0 and popQNVr3s0 ran inside the 13:54–reboot degradation window;
  - if they enter an analysis set, an EXPLORATORY sensitivity analysis excluding them is reported next to the registered result.

## E_audit — 2026-11-07 19:53 UTC (re-run of the two degraded-window lanes on the healthy node; decided BLIND: no outcome of any E_audit/E_comp lane has been inspected)
- **Lanes:** popQAWQr3s0 and popQNVr3s0, complete (58/58 per arm), re-run 13:44–16:54 inside the node-degradation window (driver stall from ~13:54; proxy start 330–375 s; slow sandboxes).
- **Concern (logged at 17:40):** these episodes may not be comparable with the healthy-node QAT reference they are paired with.
- **User:** "Make sure you continue and respwan whatever you lost due to the GPU issues, no worries, we can re do whatever we need".
- **Decision:** both lanes are re-run in full on the healthy node, with the same tags, salts, models and arguments.
  - Their degraded-window runs/ and logs/ go to experiments/endtoend/discarded/2026-11-07_degraded_window/ (kept, NOT in any registered analysis set).
  - Their claims are released, so the frozen dispatcher re-claims them in queue order.
- **Consequence:**
  - the registered analysis sets contain healthy-node lanes only;
  - this replaces the 17:40 pre-specified "sensitivity excluding the degradation-window lanes";
  - the degraded copies may be reported only as an EXPLORATORY comparison (degraded vs healthy run of the same lane).

## E_audit — 2026-11-07 21:40 UTC (BLINDING LAPSE by the PI; disclosed)
- **What happened:** while checking why a finished lane was not yet marked complete, the PI ran `tail -3 logs/popBF16r3s0_H_base.out`. The harness log prints per-task outcomes, so the PI saw:
  - two per-task lines (rich tasks: one resolved, one not; tool-call counts 42/50);
  - the arm summary "DONE base resolved 30/58" for lane popBF16r3s0, base arm (bf16, replicate 3, half 0).
- **What was NOT seen:** any malformed-call count (Y1, the endpoint of the primary tests T1–T4), any fullp-arm outcome, and any other lane's outcome.
- **Affected endpoint:** base resolve, which is DESCRIPTIVE in PREREG_E_audit §4 ("resolve of base vs QAT base, descriptive"). No registered test uses it, and no decision depends on it. The lane was complete before the look (its per_task files had 58/58; the dispatcher logged COMPLETE the same second).
- **Rule tightened:** operational QA uses only per_task line counts, proxy HTTP status codes and dispatcher logs. Harness *.out logs are never read before the analysis set is final.

## E_audit / E_comp — 2026-11-08 15:20 UTC (analysis start time; logged after the run, no outcome inspected before it)
- **Registered (§3 of both):** the analysis set is evaluated once, "at the earlier of the queue being finished or 2026-11-08 14:00 UTC". The queue never "finishes" because compr7/8 were never started (LAST_START 11:30), so 14:00 applied.
- **What happened:** the guarded one-shot script ext/run_final_analyses.sh was ready (tested 09:09; it refuses before the cutoff or if outputs exist). Nothing triggered it at 14:00: the PI session was idle with no scheduled wakeup. It ran at **15:08:59** when the PI noticed (log ext/run_final_analyses.log).
- **Effect on data:** none.
  - The last lane finished at 13:05:02 and no lane unit ran after it (`active lane units 0`; no stop at the cutoff was needed).
  - `--status_only` gave the analysis sets recorded at 13:07 (CKPT_041): E_audit bf16 [3, 4], nvnvfp4/qatawq/qatnvfp4 [3, 4, 5], AWQ comparator 1–8; E_comp [3, 4, 5, 6].
  - No output file existed before the run, no outcome was viewed, and each analysis ran once (rc 0).
- **Outputs:**

  | file | sha256 |
  |---|---|
  | analysis/prereg_E_audit.json | a9ff64d2… |
  | analysis/prereg_E_comp.json | 6e4be7f0… |

  Each also has a .stdout.txt.
- **Process fix:** every time-triggered step now gets an explicit wakeup or a background waiter.
