# Workstream E runbook (clock-gated steps, UPGRADE_PLAN §3 / PREREG_E.md)

> **HOLD (PI, 2026-11-04 ~19:00 UTC):** GPU maintenance from 00:30 UTC Nov 5; no E process from 00:05 until the
> user gives the green light. All times below shift by the outage (the PI resumes E with new times). The
> PREREG_E freeze still happens BEFORE any population launch; unblinding stays after the launches complete,
> no earlier than Nov 6 00:00. Freeze candidate: acceptance/final_code_sha256.txt.

All commands from `experiments/endtoend`; everything runs under `tools/limited.sh`
(launchers do it). Rules: ≤ 16 sandboxes total; no `prompt_logprobs`; never restart a proxy mid-campaign; one dir per
run; no outcome analysis of registered runs before **2026-11-06 00:00 UTC** (operational QA only:
`tests/smoke_qa.py`, pooled completion counts, 5xx/tracebacks). Stop a campaign: `systemctl --user stop
$(systemctl --user list-units --type=scope --no-legend 'ap-e2e-<tag>*' | awk '{print $1}')`, then remove its containers:
`DOCKER_HOST=unix:///var/run/docker.sock DOCKER_CONFIG=docker/cli docker rm -f $(docker ps -aq --filter label=e2e_run=<run dir name>)`.

## Nov 5 11:00–12:00 — 31B smoke of the freeze candidate (:8300 after X restores 31B-QAT, ≤ 4 SB)
1. `curl -s http://127.0.0.1:8300/v1/models` → served `gemma-4-31b`.
2. `bash tests/smoke31.sh` (2 tasks × {base, fullp}, 1 SB per arm, proxy :8449, tag `smoke31`).
3. When both arms finished (`runs/smoke31_H_*/per_task.jsonl` have 2 lines each):
   `python tests/smoke_qa.py logs/proxy_smoke31` → expect status 200 only, 0 exceptions, every tool result hashed,
   CRN index pairs identical. Do NOT look at resolve/malformed.
4. Stop the smoke proxy (`ap-e2e-smoke31-proxy-*`).

## Nov 5 12:00 — CODE FREEZE
1. All tests: `tests/test_protocol.py`, `tests/test_generate.py`, `tests/test_proxy_e2e.py` (env_gemma),
   `tests/test_prereg_analysis.py` (env_agentpaper), `python -I export/quarantine_renderer.py --selftest`.
2. `bash tools_freeze.sh` → `PREREG_E_manifest.txt` + digest; paste the digest into PREREG_E.md §9 and progress.md;
   change PREREG_E.md status line to FROZEN; post the digest to the PI.
3. Any later code change → `PREREG_DEVIATIONS.md` entry + new manifest label.

## Nov 5 13:00 — small-model population (GPU1, 2 SB; 6 SB from Nov 6 14:00)
E4B first (fast), then 12B; one replicate each; CRN salt = tag:
- `bash run_population.sh http://127.0.0.1:8311/v1 gemma-4-e4b models/gemma-4-e4b-it-qat-w4a16-ct subs/sample_noadapter_e4b popE4r1 configs/eligible_113.txt 8455 1 popE4r1`
- later `bash run_population.sh http://127.0.0.1:8301/v1 gemma-4-12b models/gemma-4-12b-it-qat-w4a16-ct subs/sample_noadapter_12b pop12r1 configs/eligible_113.txt 8456 1 pop12r1`
  (per-arm conc 1 → 2 SB; raise to 3 when 6 SB are allotted by stopping + relaunching a NEW tag on the remaining tasks)
Contingency (PI): if 31B episodes > 45 min → 1 31B replicate, 100 branch points, drop the 12B population.

## Nov 5 14:00 — 31B population lane 1 (:8300, 6 SB) and 18:00 lane 2 (:8302, 6 SB)
Replicate 1 (salt `pop31r1`), split by server halves (no server × arm confound):
- 14:00 `bash run_population.sh http://127.0.0.1:8300/v1 gemma-4-31b models/gemma-4-31b-it-qat-w4a16-ct subs/sample_noadapter pop31r1s0 configs/eligible_113_half0.txt 8450 3 pop31r1`
- 18:00 `bash run_population.sh http://127.0.0.1:8302/v1 gemma-4-31b models/gemma-4-31b-it-qat-w4a16-ct subs/sample_noadapter pop31r1s1 configs/eligible_113_half1.txt 8451 3 pop31r1`
Replicate 2 (salt `pop31r2`) on each lane when its replicate-1 half finishes (tags `pop31r2s0` :8452 / `pop31r2s1` :8453).
QA every few hours: `python tests/smoke_qa.py logs/proxy_pop31r1s0 ...` (pooled), 5xx, stuck sessions.

## Nov 6 ≥ 00:00 — unblinding allowed; branch plans
- Population analysis (when complete): `python analysis/prereg_analysis.py population --label 31B --base runs/pop31r1s0_H_base+runs/pop31r1s1_H_base+runs/pop31r2s0_H_base+runs/pop31r2s1_H_base --fullp runs/pop31r1s0_H_fullp+runs/pop31r1s1_H_fullp+runs/pop31r2s0_H_fullp+runs/pop31r2s1_H_fullp --proxy-logs logs/proxy_pop31r1s0 logs/proxy_pop31r1s1 logs/proxy_pop31r2s0 logs/proxy_pop31r2s1 --out analysis/prereg_pop31.json`
  NOTE: '+' joins dirs of the same arm; for 31B the halves of a replicate are DIFFERENT tasks, so pass the replicate
  structure as `r1s0+r1s1` and `r2s0+r2s1` is fine (the script groups episodes by task; each task appears once per replicate).
- Branch plans (31B, 150 points; natural onsets first): `python analysis/build_branch_plan.py --run runs/pop31r1s0_H_base --run runs/pop31r1s1_H_base --run runs/pop31r2s0_H_base --run runs/pop31r2s1_H_base --proxy-logs logs/proxy_pop31r1s0 --proxy-logs logs/proxy_pop31r1s1 --proxy-logs logs/proxy_pop31r2s0 --proxy-logs logs/proxy_pop31r2s1 --n 150 --seed 20261105 --out plans/b31.json`
  (→ plans/b31.json and plans/b31_2.json if > 113 points)
- Branch campaigns (4 arms, 40-call cap; 5 SB per 31B lane): create `subs/sample_noadapter_b40` (copy of
  subs/sample_noadapter with max_tool_calls 40; already created), then per plan file:
  `bash run_branches.sh plans/b31.json http://127.0.0.1:8300/v1 gemma-4-31b models/gemma-4-31b-it-qat-w4a16-ct subs/sample_noadapter_b40 b31a 8460 1`
- Branch analysis: `python analysis/prereg_analysis.py branches --label 31B --group plan=plans/b31.json,base=runs/b31a_base,quar=runs/b31a_quar,ipd=runs/b31a_ipd,fullp=runs/b31a_fullp [--group plan=plans/b31_2.json,...] --proxy-logs logs/proxy_b31a [logs/proxy_b31b] --out analysis/prereg_br31.json`
- Small models: same with 100 points each from `popE4r1`/`pop12r1` (`subs/sample_noadapter_e4b_b40`, `_12b_b40`).

## Always
- `progress.md` every ~30 min; `PREREG_DEVIATIONS.md` for any deviation; failure log refresh:
  `python analysis/failure_log.py` (real outputs only; for workstream C).
- Exploratory (not registered): `analysis/pilot_metrics.py <tag> --cfgs base,full` for p12a/p4a — only after
  2026-11-06 00:00.

## RE-TIMED 2026-11-05 (after the green light) — exact commands, as launched / to launch
- DONE 07:03–07:12 smoke31 (QA clean); 07:14 PREREG_E FROZEN (DIGEST c9c20591…); 07:14 lane 1 launched:
  `bash run_population.sh http://127.0.0.1:8300/v1 gemma-4-31b $M31 subs/sample_noadapter pop31r1s0 configs/eligible_113_half0.txt 8450 3 pop31r1`
  + chain (scope ap-e2e-chain-pop31r1s0): `run_chain.sh pop31r1s0 58 -- ... pop31r2s0 configs/eligible_113_half0.txt 8452 3 pop31r2`
- ON THE PI's SIGNAL — GPU1 (12B :8301 + E4B :8311), 2 SB: E4B first, then 12B chained:
  `bash run_population.sh http://127.0.0.1:8311/v1 gemma-4-e4b $ME4B subs/sample_noadapter_e4b popE4r1 configs/eligible_113.txt 8455 1 popE4r1`
  `QN=VLLM:Worker_D1 NAME=e2e-chain-popE4r1 CORES=140-149 nohup $L bash run_chain.sh popE4r1 113 -- http://127.0.0.1:8301/v1 gemma-4-12b $M12B subs/sample_noadapter_12b pop12r1 configs/eligible_113.txt 8456 1 pop12r1 > logs/chain_popE4r1.out 2>&1 &`
- ON THE PI's SIGNAL — lane 2 on :8302, 6 SB:
  `bash run_population.sh http://127.0.0.1:8302/v1 gemma-4-31b $M31 subs/sample_noadapter pop31r1s1 configs/eligible_113_half1.txt 8451 3 pop31r1`
  `QN=VLLM:Worker_D2 NAME=e2e-chain-pop31r1s1 CORES=140-149 nohup $L bash run_chain.sh pop31r1s1 55 -- http://127.0.0.1:8302/v1 gemma-4-31b $M31 subs/sample_noadapter pop31r2s1 configs/eligible_113_half1.txt 8453 3 pop31r2 > logs/chain_pop31r1s1.out 2>&1 &`
  (M31/M12B/ME4B = models/gemma-4-{31b,12b,e4b}-it-qat-w4a16-ct; L = tools/limited.sh;
  NEVER end an && list with '&' — it backgrounds the whole list.)
- 09:05 PRIORITY CHANGE (PI): chains popE4r1->pop12r1 and rep2->rep3 replaced by sched_after_rep2.sh (scope ap-e2e-chain-sched,
  log logs/chain_sched.out): 1st lane done with rep 2 -> pop12r1 at 3 per arm on :8301; 2nd lane -> exploratory rep 3 (its half);
  then the other rep-3 half. Rep1->rep2 chains unchanged. Blinded watchdog: scope ap-e2e-watch -> logs/e2e_status.txt,
  logs/e2e_alerts.log (exits when all E campaigns/chains are done).

## UNBLINDING + CONFIRMATORY ANALYSIS (only after 2026-11-06 00:00 UTC AND all registered populations complete:
## pop31r{1,2}s{0,1} 58/55 tasks per arm, popE4r1 + pop12r1 113 per arm; check logs/e2e_status.txt) — run from experiments/endtoend, env_agentpaper
`P=/opt/envs/env_agentpaper/bin/python; sha256sum -c acceptance/final_code_sha256.txt && tail -1 PREREG_E_manifest.txt` (frozen code/manifest intact) ->
`grep -h '"error": "Sandbox execution error: litellm\|"error": "Container' runs/pop*_H_*/per_task.jsonl | wc -l` (infra failures; PREREG §6: re-run each ONCE with the same salt as tag <tag>_rr, log in PREREG_DEVIATIONS; the script otherwise excludes them pairwise) ->
`$P analysis/prereg_analysis.py population --label 31B --base runs/pop31r1s0_H_base+runs/pop31r1s1_H_base+runs/pop31r2s0_H_base+runs/pop31r2s1_H_base --fullp runs/pop31r1s0_H_fullp+runs/pop31r1s1_H_fullp+runs/pop31r2s0_H_fullp+runs/pop31r2s1_H_fullp --proxy-logs logs/proxy_pop31r1s0 logs/proxy_pop31r1s1 logs/proxy_pop31r2s0 logs/proxy_pop31r2s1 --out analysis/prereg_pop31.json` (CONFIRMATORY: co-primary Y1/Y2 + Holm; keep the r1-before-r2 order identical in both arms) ->
`$P analysis/prereg_analysis.py population --label E4B --base runs/popE4r1_H_base --fullp runs/popE4r1_H_fullp --proxy-logs logs/proxy_popE4r1 --out analysis/prereg_popE4B.json` and the same with 12B/pop12r1 -> analysis/prereg_pop12B.json (secondary, per model) ->
EXPLORATORY (label it so): the 31B command with +runs/pop31r3s0_H_base+runs/pop31r3s1_H_base appended to --base, +runs/pop31r3s0_H_fullp+runs/pop31r3s1_H_fullp appended to --fullp, and logs/proxy_pop31r3s0 logs/proxy_pop31r3s1 added to --proxy-logs -> analysis/EXPLORATORY_pop31_3rep.json ->
then branch-at-onset per the section "Nov 6 ≥ 00:00" above (build_branch_plan.py from the base arms of replicates 1+2; run_branches.sh; prereg_analysis.py branches --group ...), and `analysis/pilot_metrics.py p12a|p4a --cfgs base,full` for the exploratory pilots.
- 10:51 sched_v2.sh replaces all chains (systemd empty-scope bug); exploratory rep 3 CANCELLED (PI). After rep 2 the
  31B servers stay idle. In the unblinding sequence above, SKIP the EXPLORATORY 3-replicate step. Never `tail` the
  harness .out logs before unblinding (they print per-task outcomes); use logs/e2e_status.txt.
