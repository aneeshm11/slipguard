# Level 1 re-analysis: verified results

`tools/reproduce_level1.sh` (in the project tree: `release/docs_pack/tools/reproduce_level1.sh`) re-runs every
registered (and labelled exploratory) analysis from its frozen script on the released run records. It writes only into
`$OUT`, and compares each output with the released result file using `tools/compare_json.py`.

```bash
tools/reproduce_level1.sh              # all rows; OUT defaults to a new mktemp directory under <root>/tmp
tools/reproduce_level1.sh --list       # row ids
tools/reproduce_level1.sh v26 e_pop31  # selected rows
```

The script exits with status 1 if any row is DIFFERENT or FAILED, or if a released file changed during the run.

**Verified run.**
- When and where: 2026-11-06, 21:37:09–21:56:07 UTC, on the project tree (`ROOT=${PROJECT_ROOT}`, `OUT=tmp/l1check/final`).
- Resources: 4 CPU cores (`taskset -c 124-127`), at most 16 GB address space per process, no GPU (`CUDA_VISIBLE_DEVICES=`).
- Settings: `PYTHONHASHSEED=0`, interpreters `env_gemma` (A/B/F/X rows) and `env_agentpaper` (E2E, soak, slipguard rows).
- **Total runtime: 1,138 s (19.0 min).** One row, `ex_boot`, takes 732 s. Every other row takes under 2.5 min.
- Exit status 0.
- In that run, `e_ext` and `e_awq` were NOT RUN: their registrations were still collecting data.

**Rows `e_ext` and `e_awq`, run after their registered analyses** (each was run once on 2026-11-07, at 06:50:58 and
06:51:34 UTC; `PROGRESS.md`).
- When and where: 2026-11-07, 07:23:06–07:23:31 UTC, on the project tree
  (`bash release/docs_pack/tools/reproduce_level1.sh e_ext e_awq`, `OUT=tmp/l1_eext`, deleted afterwards).
- Resources: 8 CPU cores (`taskset -c 136-143`), at most 16 GB address space per process, no GPU.
- Settings: `PYTHONHASHSEED=0`, interpreter `env_agentpaper`.
- **Both IDENTICAL**: 4 files compared (each row's result JSON and its released printed summary, `*.stdout.txt`).
  Total runtime 25 s; exit status 0.
- `find -newer $OUT/.start` found nothing new under `experiments/` or `data/` except the running PREREG_E_awq2 lanes'
  own files (`endtoend/runs/popAWQr3*`, `logs/proxy_popAWQr*`).

**Row `e_awq2`, run after its registered analysis** (run once on 2026-11-07 at 13:06:15 UTC; `PROGRESS.md`).
- When and where: 2026-11-07, about 20:40 UTC, on the project tree
  (`bash release/docs_pack/tools/reproduce_level1.sh e_awq2`, `OUT` a scratch directory outside the tree).
- Resources: 8 CPU cores (`taskset -c 120-127`), at most 16 GB address space per process, no GPU.
- Settings: `PYTHONHASHSEED=0`, interpreter `env_agentpaper`.
- **IDENTICAL**: 2 files compared (`prereg_E_awq2.json` and its released printed summary `prereg_E_awq2.stdout.txt`).
  Runtime 12.7 s; exit status 0.
- A `find -newer $OUT/.start` over `experiments/` and `data/` (run-record directories of the running studies
  excluded) found only the running harness's own `endtoend/wheelsets/_index/` files.

**Combined tally** (the 37 other rows from the full run of 2026-11-06, plus the three rows above):

| result | rows |
|---|---|
| IDENTICAL | 24 |
| POINTS-IDENTICAL (bootstrap Monte-Carlo noise, explained below) | 8 |
| DIFFERENT | 0 |
| FAILED | 0 |
| NOT RUN (reason below) | 8 |

The 32 rows that ran compared 71 output files (65 in the full run, 4 in the two-row run, 2 in the `e_awq2` run).

No file under `experiments/` or `data/` was written by the run. This was checked with `find -newer $OUT/.start`. The
only new files were the running end-to-end harness's own files (`endtoend/runs`, `logs`, `wheelsets`, `tmp_runs`, `ext/`),
which kept changing after the E2E rows had finished.

**Result classes** (`compare_json.py`):
- **IDENTICAL**: equal after `json.load` (`.jsonl`: line by line). A row lists any keys it ignores; these are run
  metadata only.
- **POINTS-IDENTICAL**: every difference is a declared bootstrap / Monte-Carlo leaf (a CI bound, a bootstrap p, or the
  Holm p derived from it). Every point estimate, count and verdict is equal.
- **DIFFERENT**: anything else. The detail lists the first differing paths.
- **NOT RUN**: the row was not run; the reason is given.

## Rows

Run each command from the repository root. `$OUT` is the scratch directory and `$ROOT` the tree root; `python` is the
interpreter named above. The complete command lists are in `$OUT/summary.tsv`.

| row | registration | command (run from the repository root; `$OUT` = scratch) | result | s |
|---|---|---|---|---|
| v1 | 1 PREREG_v1 (contagion dose/lag) | `not run: experiments/contagion/scripts/prereg_analysis.py` | **NOT RUN** | - |
| epred | 2 E_PREDICTIONS_v1 (evaluation of D's predictions) | `not run: (none)` | **NOT RUN** | - |
| x_disc_ana | 3 X prereg: per-model discovery analyses | `not run: experiments/crossfamily/scripts/discovery/analyze.py` | **NOT RUN** | - |
| x_disc_dec | 3 X prereg: registered decisions (combine.py) | `(cd experiments/crossfamily && python scripts/combine.py $OUT/x_disc_dec/results_x.json)` | **IDENTICAL** | 0.2 |
| x_disc_res | 3 X prereg: results.json assembly (finalize.py) | `not run: experiments/crossfamily/scripts/finalize.py` | **NOT RUN** | - |
| v2 | 4 PREREG_v2 (Gemma C1-C11, all models) | `(cd experiments/contagion && python scripts/confirm_v2_analysis.py --pools data/confirmatory/pools --meta data/confirmatory/meta_S1.jsonl --res31 out/main/rC31b_v2.jsonl --res12 out/main/rC12b_v2.jsonl --rese4 out/main/rCe4b_v2.jsonl --out $OUT/v2/confirm_v2_all_full.json)` | **IDENTICAL** | 10.3 |
| v2_ver | 4 PREREG_v2 verified-only sensitivity | `(cd experiments/contagion && python scripts/confirm_v2_analysis.py --pools data/confirmatory/pools_verified_sensitivity --meta data/confirmatory/meta_S1.jsonl --res31 out/main/rC31b_v2.jsonl --res12 out/main/rC12b_v2.jsonl --rese4 out/main/rCe4b_v2.jsonl --out $OUT/v2_ver/confirm_v2_all_verified_sens.json)` | **IDENTICAL** | 4.4 |
| v2_qwen | 4 PREREG_v2 Qwen arm (X v2_frozen) | `(cd experiments/crossfamily && python scripts/v2_frozen/analyze.py --mk qwen3-8b --manifest $ROOT/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json --gen out/v2/gen_qwen3-8b.jsonl --out $OUT/v2_qwen/v2/ana_qwen3-8b.json)`<br>`(cd experiments/crossfamily && python scripts/v2_frozen/analyze.py --mk qwen3-8b --manifest $ROOT/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json --gen out/v2/gen_qwen3-8b.jsonl --ids out/v2/ids_A1_H1.txt --out $OUT/v2_qwen/v2/ana_qwen3-8b_H1.json)`<br>... (13 commands; all in `$OUT/summary.tsv`) | **IDENTICAL** | 137.1 |
| v21 | 5 PREREG_v2.1 (thinking off) | `not run: experiments/contagion/scripts/analyze_v21_v22.py --battery v21` | **NOT RUN** | - |
| v22 | 6 PREREG_v2.2 S and H | `not run: experiments/contagion/scripts/analyze_v21_v22.py --battery S\|H` | **NOT RUN** | - |
| x_ext | 7 X prereg_ext (4 more families) | `(cd experiments/crossfamily && env TIKTOKEN_RS_CACHE_DIR=$ROOT/experiments/crossfamily/data/tiktoken_cache python scripts/ext_frozen/analyze.py --mk gpt-oss-20b --manifest $ROOT/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json --gen out/ext/gen_gpt-oss-20b.jsonl --out $OUT/x_ext/ext/ana_gpt-oss-20b.json)`<br>`(cd experiments/crossfamily && env TIKTOKEN_RS_CACHE_DIR=$ROOT/experiments/crossfamily/data/tiktoken_cache python scripts/ext_frozen/analyze.py --mk gpt-oss-20b --manifest $ROOT/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json --gen out/ext/gen_gpt-oss-20b.jsonl --ids out/ext/ids_A1_H1.txt --out $OUT/x_ext/ext/ana_gpt-oss-20b_H1.json)`<br>... (13 commands; all in `$OUT/summary.tsv`) | **IDENTICAL** | 134.9 |
| v23 | 8 PREREG_v2.3 (JSON serialization onset) | `(cd experiments/contagion && python scripts/analyze_onset_v23.py --out $OUT/v23/onset_v23_analysis.json)` | **IDENTICAL** | 7.8 |
| e_pop31 | 9 PREREG_E population 31B (co-primary) | `(cd experiments/endtoend && python analysis/prereg_analysis.py population --label 31B --base runs/pop31r1s0_H_base+runs/pop31r1s1_H_base+runs/pop31r2s0_H_base+runs/pop31r2s1_H_base --fullp runs/pop31r1s0_H_fullp+runs/pop31r1s1_H_fullp+runs/pop31r2s0_H_fullp+runs/pop31r2s1_H_fullp --proxy-logs logs/proxy_pop31r1s0 logs/proxy_pop31r1s1 logs/proxy_pop31r2s0 logs/proxy_pop31r2s1 --out $OUT/e_pop31/prereg_pop31.json)` | **POINTS-IDENTICAL** | 3.2 |
| e_br31 | 9 PREREG_E branches 31B (corrected fidelity) | `(cd experiments/endtoend && python analysis/prereg_branch_corrected.py branches --label 31B --group plan=plans/b31a.json,base=runs/b31a_base,quar=runs/b31a_quar,ipd=runs/b31a_ipd,fullp=runs/b31a_fullp --group plan=plans/b31b.json,base=runs/b31b_base,quar=runs/b31b_quar,ipd=runs/b31b_ipd,fullp=runs/b31b_fullp --group plan=plans/b31_2.json,base=runs/b31c_base,quar=runs/b31c_quar,ipd=runs/b31c_ipd,fullp=runs/b31c_fullp --proxy-logs logs/proxy_b31a logs/proxy_b31b logs/proxy_b31c --out $OUT/e_br31/prereg_br31.json)` | **POINTS-IDENTICAL** | 9.3 |
| e_popE4B | 9 PREREG_E population E4B (secondary) | `(cd experiments/endtoend && python analysis/prereg_analysis.py population --label E4B --base runs/popE4r1_H_base --fullp runs/popE4r1_H_fullp --proxy-logs logs/proxy_popE4r1 --out $OUT/e_popE4B/prereg_popE4B.json)` | **POINTS-IDENTICAL** | 2.1 |
| e_pop12B | 9 PREREG_E population 12B (secondary) | `(cd experiments/endtoend && python analysis/prereg_analysis.py population --label 12B --base runs/pop12r1_H_base --fullp runs/pop12r1_H_fullp --proxy-logs logs/proxy_pop12r1 --out $OUT/e_pop12B/prereg_pop12B.json)` | **POINTS-IDENTICAL** | 2.6 |
| e_pop12B6 | 9 PREREG_E population 12B, sec. 6 conforming | `(cd experiments/endtoend && python analysis/prereg_sec6_conforming.py population --label 12B_sec6conforming --base runs/pop12r1_H_base --fullp runs/pop12r1_H_fullp --proxy-logs logs/proxy_pop12r1 --out $OUT/e_pop12B6/prereg_pop12B_sec6conforming.json)` | **POINTS-IDENTICAL** | 2.6 |
| e_br12 | 9 PREREG_E branches 12B (secondary) | `(cd experiments/endtoend && python analysis/prereg_branch_corrected.py branches --label 12B --group plan=plans/b12.json,base=runs/b12_base,quar=runs/b12_quar,ipd=runs/b12_ipd,fullp=runs/b12_fullp --proxy-logs logs/proxy_b12 --out $OUT/e_br12/prereg_br12.json)` | **POINTS-IDENTICAL** | 7.0 |
| e_brE4B | 9 PREREG_E branches E4B (secondary) | `(cd experiments/endtoend && python analysis/prereg_branch_corrected.py branches --label E4B --group plan=plans/bE4.json,base=runs/bE4_base,quar=runs/bE4_quar,ipd=runs/bE4_ipd,fullp=runs/bE4_fullp --proxy-logs logs/proxy_bE4 --out $OUT/e_brE4B/prereg_brE4B.json)` | **POINTS-IDENTICAL** | 5.1 |
| v24 | 10 PREREG_v2.4 (exact-intent repair battery) | `(cd experiments/intent_decoding && python v24/analyze_battery.py v24/battery_run.jsonl --out $OUT/v24/battery_run_analysis.json)` | **IDENTICAL** | 22.8 |
| f_repair | 11 F ANALYSIS_PLAN (weight-space repair) | `not run: experiments/quant_margins/wsa/repair_memit.py (gpu3_C_gate.sh)` | **NOT RUN** | - |
| v25 | 12 PREREG_v2.5 (full stack, 31B) | `(cd experiments/intent_decoding && python v25/analyze_v25.py --out $OUT/v25/analysis_v25.json)` | **IDENTICAL** | 20.8 |
| sweep | 13 F SWEEP_PLAN (frozen sweep_report.py) | `(cd experiments/quant_margins/wsa && python sweep_report.py --out $OUT/sweep/sweep_report.json)`<br>`(cd experiments/quant_margins/wsa && python sweep_report.py --ref e4b_bf16 --out $OUT/sweep/sweep_report_e4bref.json)` | **IDENTICAL** | 5.4 |
| sweep_ship | 13 F SWEEP_PLAN re-scored by shipped code | `(cd . && python slipguard/dev/check_wsa.py experiments/quant_margins/wsa/out > $OUT/sweep_ship/check_wsa.json)` | **POINTS-IDENTICAL** | 4.4 |
| v26 | 14 PREREG_v2.6 (audit pick) | `(cd experiments/contagion && python scripts/analyze_v26_audit.py --out $OUT/v26/v26_audit_analysis.json)` | **IDENTICAL** | 0.8 |
| v25b | 15 PREREG_v2.5b (full stack, E4B) | `(cd experiments/intent_decoding && python v25b/analyze_v25b.py --out $OUT/v25b/analysis_v25b.json)` | **IDENTICAL** | 9.3 |
| v27 | 16 PREREG_v2.7 robustness | `(cd experiments/contagion && python scripts/analyze_v27_robustness.py --out $OUT/v27/v27_robustness_analysis.json)` | **IDENTICAL** | 0.9 |
| v27_pool | 16 PREREG_v2.7 pooled retest (logged deviation) | `(cd experiments/contagion && python scripts/v27_pooled_retest.py --out $OUT/v27_pool/v27_pooled_retest.json)` | **IDENTICAL** | 0.7 |
| soak | 16 PREREG_v2.7 sec. 5 soak | `(cd . && python experiments/soak/soak_analyze.py --dir $ROOT/experiments/soak/out --proxy_logs $ROOT/experiments/soak/out/proxy_logs --proxy_scope ap-soakproxy-731673.scope --stock_scope ap-vllm-g2-731106.scope --plugin_scope ap-vllm-g2-801717.scope --out $OUT/soak/soak_analysis.json)` | **IDENTICAL** | 0.3 |
| v28 | 17 PREREG_v2.8 (TranscriptLab CLI vs C1) | `(cd . && python experiments/contagion/scripts/analyze_v28_cli.py --cli_gen $ROOT/experiments/transcriptlab_cli/run_v28/gen.jsonl --out $OUT/v28/v28_cli_analysis.json)`<br>`(cd . && python $ROOT/experiments/contagion/scripts/analyze_bf16_core.py --res $ROOT/experiments/transcriptlab_cli/run_v28/gen.jsonl --log $ROOT/experiments/transcriptlab_cli/run_v28/run.log --out $OUT/v28/run_v28.analysis.json --B 2000)` | **IDENTICAL** | 1.3 |
| e_ext | 18 PREREG_E_ext (8 fresh replicates; resolve NI) | `(cd experiments/endtoend && python analysis/prereg_E_ext_analysis.py --out $OUT/e_ext/prereg_E_ext.json > $OUT/e_ext/prereg_E_ext.stdout.txt)` | **IDENTICAL** | 10.7 |
| v29 | 19 PREREG_v2.9 (CLI coverage, E2B / E4B) | `(cd . && python $ROOT/experiments/contagion/scripts/analyze_bf16_core.py --res $ROOT/experiments/transcriptlab_cli/run_e2b/gen.jsonl --log $ROOT/experiments/transcriptlab_cli/run_e2b/run.log --out $OUT/v29/experiments/transcriptlab_cli/run_e2b/analysis.json --B 2000)`<br>`(cd . && python $ROOT/experiments/contagion/scripts/analyze_bf16_core.py --res $ROOT/experiments/transcriptlab_cli/run_e4b16/gen.jsonl --log $ROOT/experiments/transcriptlab_cli/run_e4b16/run.log --out $OUT/v29/experiments/transcriptlab_cli/run_e4b16/analysis.json --B 2000)`<br>`(cd $OUT/v29 && python $ROOT/experiments/contagion/scripts/analyze_v29_coverage.py --runs experiments/transcriptlab_cli/run_e2b experiments/transcriptlab_cli/run_e4b16 --out $OUT/v29/v29_coverage.json)` | **IDENTICAL** | 1.5 |
| v210 | 20 PREREG_v2.10 (audit breadth) | `(cd . && python experiments/v210/analyze_v210.py --out $OUT/v210/v210_audit_breadth.json)` | **IDENTICAL** | 0.1 |
| v210_rescore | 20 PREREG_v2.10 audits re-scored from records | `(cd slipguard && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_nvfp4_nvidia.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_nvfp4_nvidia.json)`<br>`(cd slipguard && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_qatawq_cyankiwi.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_qatawq_cyankiwi.json)`<br>`(cd slipguard && env PYTHONPATH=src python -m slipguard audit-weights --from-records $ROOT/experiments/quant_margins/wsa/out/audit_v210_31b_qatnvfp4_melcheikh.records.jsonl --reference $ROOT/experiments/quant_margins/wsa/out/audit_sweep_31b_bf16.records.jsonl --out $OUT/v210_rescore/audit_v210_31b_qatnvfp4_melcheikh.json)` | **IDENTICAL** | 1.3 |
| e_awq | 21 PREREG_E_awq (audit pick end to end) | `(cd experiments/endtoend && python analysis/prereg_E_awq_analysis.py --qat_reps 1 2 3 4 5 6 7 8 9 10 --out $OUT/e_awq/prereg_E_awq.json > $OUT/e_awq/prereg_E_awq.stdout.txt)` | **IDENTICAL** | 14.2 |
| e_awq2 | 22 PREREG_E_awq2 (proxy on the audit pick, 6 fresh replicates) | `(cd experiments/endtoend && python analysis/prereg_E_awq2_analysis.py --out $OUT/e_awq2/prereg_E_awq2.json > $OUT/e_awq2/prereg_E_awq2.stdout.txt)` | **IDENTICAL** | 12.7 |
| bf16 | bf16 row (EXPLORATORY benchmark row) | `(cd experiments/contagion && python scripts/analyze_bf16_core.py --res out/main/rCbf16_v2.jsonl --log logs/ctg-Cbf16.log --out $OUT/bf16/bf16_core_all.json)`<br>`(cd experiments/contagion && python scripts/analyze_bf16_core.py --res out/main/rCbf16_v2.jsonl --log logs/ctg-Cbf16.log --subset le13000 --out $OUT/bf16/bf16_core_le13000.json)` | **IDENTICAL** | 1.4 |
| ex_dist | EXPLORATORY B3/B9/B10 (E2E distributions) | `(cd experiments/endtoend && python analysis/EXPLORATORY_distributions.py --out $OUT/ex_dist/EXPLORATORY_distributions.json)` | **IDENTICAL** | 7.6 |
| ex_boot | EXPLORATORY E2E bootstrap-seed audit | `(cd experiments/endtoend && python analysis/EXPLORATORY_bootseed.py --out $OUT/ex_boot/EXPLORATORY_bootseed.json --procs 4)` | **IDENTICAL** | 732.2 |
| ex_cens | EXPLORATORY B13 (audit censoring) | `not run: experiments/quant_margins/wsa/EXPLORATORY_censoring.py` | **NOT RUN** | - |

## Why 8 rows are POINTS-IDENTICAL

**End to end (7 rows: `e_pop31`, `e_br31`, `e_popE4B`, `e_pop12B`, `e_pop12B6`, `e_br12`, `e_brE4B`).**
- The cause: the frozen `prereg_analysis.py` seeds each paired-difference bootstrap with `hash(key) % 1000`. Python
  randomises str hashes per process, so the released `diff_*/ci95`, `diff_*/p_boot` (and `p_holm`) are one Monte-Carlo
  draw (REPRODUCE.md, "Known non-determinism").
- What differs: only those leaves, by at most 0.049 (population) and 0.104 (branches, malformed calls per branch).
  Every point estimate, ratio CI (fixed seed), count, exclusion list and verdict flag is identical. So are the three
  `*.fidelity.json` files.
- 31B rows: the script also checks that the re-run CIs and p lie inside the range found over all 1,000 possible seeds
  (`EXPLORATORY_bootseed.json`). Both rows pass. Example, Y1 difference CI:
  - re-run: [−3.6106, −1.0265];
  - released: [−3.5973, −1.0310];
  - 1,000-seed range: lower bound −3.6947 to −3.5442, upper bound −1.0664 to −0.9823.
- `PYTHONHASHSEED=0` makes the check itself repeatable, but it does not recover the released draw.
- `EXPLORATORY_bootseed.py` itself (`ex_boot`) is IDENTICAL, because it evaluates every seed.
- The later end-to-end rows `e_ext`, `e_awq` and `e_awq2` call the same frozen functions but pass every bootstrap seed
  as an explicit integer, so they are IDENTICAL.

**Weight audit, re-scored by the shipped code (`sweep_ship`).**
- `slipguard/dev/check_wsa.py` re-scores F's frozen sweep records with the shipped `slipguard.weights` and compares
  the result with `sweep_report.json` and `sweep_report_e4bref.json`.
- Equal across 24 checkpoint rows: every summary field, every median-deficit point, and FLAG/SEVERE.
- Different: the CI bounds, by at most 0.0313 nats. `sweep_report.py` drew all checkpoints from one RNG stream;
  `compare()` reseeds for each comparison.
- The frozen `sweep_report.py` itself (`sweep`) reproduces both reports IDENTICALLY.

## NOT RUN (8 rows)

| row | reason |
|---|---|
| v1 (PREREG_v1) | `scripts/prereg_analysis.py` has no output option. It always writes `experiments/contagion/out/prereg_analysis.json`, the released file. It also reads the main-track discovery contexts (below). |
| epred (E_PREDICTIONS_v1) | `E_predictions_eval.md` is a manual evaluation by the PI; no script exists. Its inputs are rows e_pop31, e_popE4B, e_pop12B6, e_br31, e_br12 and e_brE4B. |
| x_disc_ana (X prereg) | `scripts/discovery/analyze.py` loads the main-track contexts through `arms.load_meta()` / `variants.ROOT`, which points at the data holder's main-track run tree. That tree has moved outside the project and is not released. The registered decision step on the released per-model analyses is row `x_disc_dec`: IDENTICAL to `results.json:registered_decisions`. |
| x_disc_res (X prereg) | `scripts/finalize.py` has no output option. It always writes `experiments/crossfamily/results.json`. |
| v21, v22 (PREREG_v2.1, v2.2) | `scripts/analyze_v21_v22.py` re-reads every main-track context for its copy classes (`variants.load_context`) and, for v2.1, for the P5 template check. Those contexts are not released and are outside the tree. |
| f_repair (F ANALYSIS_PLAN) | `repair_memit.py` re-computes the repair from model weights and extracted activations (`out/hf_*.pt`, 6 GB, and the 31B `model.safetensors`), not from run records. The registered run used `--device cuda:0` and saved adapters into `wsa/adapters`. This is Level 2. |
| ex_cens (EXPLORATORY B13) | `EXPLORATORY_censoring.py` has no output option. It always writes `wsa/out/EXPLORATORY_censoring.json`, the released file. |

## Corrections to REPRODUCE.md §Level 1 (not edited here)

The commands in the table above are the exact ones that ran.

**Several Level-1 commands, run as written, overwrite the released file.** In each case the default output path is the
released file itself:
- `v24/analyze_battery.py battery_run.jsonl` writes `battery_run_analysis.json` and `_states.jsonl` next to its input.
- `v25/analyze_v25.py` and `v25b/analyze_v25b.py` default `--out` to `v25[b]/out/analysis_v25[b].json`.
- `wsa/sweep_report.py` defaults `--out` to `out/sweep_report.json`.

Always pass `--out $OUT/...`.

**Required arguments and working directories that the table leaves out:**
- `confirm_v2_analysis.py` needs `--pools data/confirmatory/pools --meta data/confirmatory/meta_S1.jsonl --res31/--res12/--rese4 out/main/rC*_v2.jsonl`.
  The verified-only sensitivity uses `--pools data/confirmatory/pools_verified_sensitivity`, not `pools/verified_only`.
- `analyze_bf16_core.py` needs `--res out/main/rCbf16_v2.jsonl --log logs/ctg-Cbf16.log`.
- E2E commands run from `experiments/endtoend`.
- The 31B branch analysis has three `--group`s: `b31a`, `b31b` (the split of `plans/b31.json`), and `plans/b31_2.json`
  on lane `b31c`. Its proxy logs are `logs/proxy_b31a`, `logs/proxy_b31b` and `logs/proxy_b31c`. The wrapper also writes
  `<out>.fidelity.json`.
- `EXPLORATORY_bootseed.py` defaults to `--procs 6`; the script passes the core budget.

**Two more mismatches with the table:**
- "Bootstrap CIs use fixed seeds, so the output should be identical" holds for every row except the 8 above.
- The weight audit row: `check_wsa.py` prints a self-comparison and writes no report. The frozen `sweep_report.py`
  is what reproduces `sweep_report.json` exactly.

## Caveats

**Metadata keys ignored.** Each is shown in the row detail:
- `v2_qwen`: `results_v2.json:/ana_dir`, the input directory combine_v2 read from (here, the re-computed analyses).
- `v210_rescore`:
  - `/pack`: `--from-records` cannot know the pack an endpoint run used.
  - `/tool/slipguard`: the audits were written by 0.1.0.dev0 and the tree now ships 0.1.1.
  - All numbers, FLAG and SEVERE are equal.

**Portability.** Many frozen scripts embed absolute `${PROJECT_ROOT}/...` input paths (the data holder's host path), for example
`D = '${PROJECT_ROOT}/experiments/contagion'`. The check script resolves its own paths from `ROOT`, but on an
exported tree those frozen paths must also exist, or be pinned by the export (`FROZEN_EXPORT_PINS.json`).

**ROOT default.** `ROOT` defaults to the nearest ancestor of `tools/` that contains `experiments/`. That is three
levels up in the project tree and one level up in the public repo.

**Write safety.** The check sets `PYTHONDONTWRITEBYTECODE=1` for every run. Without it, `__pycache__` is written into
the frozen script directories. One such file already exists from an earlier run:
`endtoend/analysis/__pycache__/EXPLORATORY_distributions.cpython-312.pyc`.
