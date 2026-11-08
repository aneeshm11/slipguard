#!/usr/bin/env bash
# Level-1 re-analysis check (CPU only, no model weights, no GPU).
#
# Re-runs every registered (and labelled exploratory) analysis from its frozen script on the released run records and
# compares each output with the released result file (tools/compare_json.py). Every output goes to $OUT; nothing in
# the tree is written (bytecode caching is off, caches/TMPDIR point into $OUT, released files are checked unmodified
# at the end).
#
#   tools/reproduce_level1.sh              # all rows
#   tools/reproduce_level1.sh v26 bf16     # selected rows (ids: tools/reproduce_level1.sh --list)
#
# Environment (all optional):
#   ROOT     tree root that holds experiments/ (default: the nearest ancestor of tools/ that has experiments/:
#            three levels up in the project tree (release/docs_pack/tools), one level up in the public repo (tools/))
#   OUT      output directory (default: a new mktemp directory under $ROOT/tmp)
#   PY_G     interpreter with numpy/scipy and vLLM 0.19.1 (A's gemma_protocol imports vLLM's gemma4 tool parser)
#   PY_A     interpreter with numpy (end-to-end, soak, slipguard rows);  PY_C: interpreter for compare_json.py
#            (defaults: $TRANSCRIPTLAB_ENVS/env_gemma/bin/python and $TRANSCRIPTLAB_ENVS/env_agentpaper/bin/python if they
#            exist, else python3 on PATH)
#   CORES    CPU list for taskset (default 124-127);  MEM_GB  address-space limit per process (default 16)
#   HASHSEED PYTHONHASHSEED for every run (default 0; see the end-to-end rows)
# Exit status: 0 if every row that ran is IDENTICAL or POINTS-IDENTICAL; 1 if any row is DIFFERENT or FAILED, or if a
# released file changed during the run.
set -u -o pipefail

TOOLS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ -z "${ROOT:-}" ]; then
  ROOT=$(cd "$TOOLS/.." && pwd)
  for up in "$TOOLS/.." "$TOOLS/../.." "$TOOLS/../../.."; do
    if [ -d "$up/experiments/contagion" ]; then ROOT=$(cd "$up" && pwd); break; fi
  done
fi
ROOT=$(cd "$ROOT" && pwd)
pick() { for p in "$@"; do if [ -n "$p" ] && [ -x "$p" ]; then echo "$p"; return; fi; done; command -v python3; }
PY_G=$(pick "${PY_G:-}" ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python)
PY_A=$(pick "${PY_A:-}" ${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python)
PY_C=$(pick "${PY_C:-}" "$PY_A")
CORES=${CORES:-124-127}; MEM_GB=${MEM_GB:-16}; HASHSEED=${HASHSEED:-0}
NCORES=$("$PY_C" -c "import sys;print(sum(int(b)-int(a)+1 if b else 1 for a,_,b in (p.partition('-') for p in sys.argv[1].split(','))))" "$CORES")
TASKSET=""; if command -v taskset >/dev/null 2>&1 && taskset -c "$CORES" true 2>/dev/null; then TASKSET="taskset -c $CORES"; fi

C=experiments/contagion; E=experiments/endtoend; B=experiments/intent_decoding; X=experiments/crossfamily
W=experiments/quant_margins/wsa; T=experiments/transcriptlab_cli
MAN=$ROOT/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json

# --------------------------------------------------------------------------------------------------- row registry
ROWS=(
  # id          registration (PREREGISTRATIONS.md #)            function
  "v1|1 PREREG_v1 (contagion dose/lag)|nr_v1"
  "epred|2 E_PREDICTIONS_v1 (evaluation of D's predictions)|nr_epred"
  "x_disc_ana|3 X prereg: per-model discovery analyses|nr_x_disc_ana"
  "x_disc_dec|3 X prereg: registered decisions (combine.py)|r_x_disc_dec"
  "x_disc_res|3 X prereg: results.json assembly (finalize.py)|nr_x_disc_res"
  "v2|4 PREREG_v2 (Gemma C1-C11, all models)|r_v2"
  "v2_ver|4 PREREG_v2 verified-only sensitivity|r_v2_ver"
  "v2_qwen|4 PREREG_v2 Qwen arm (X v2_frozen)|r_v2_qwen"
  "v21|5 PREREG_v2.1 (thinking off)|nr_v21"
  "v22|6 PREREG_v2.2 S and H|nr_v22"
  "x_ext|7 X prereg_ext (4 more families)|r_x_ext"
  "v23|8 PREREG_v2.3 (JSON serialization onset)|r_v23"
  "e_pop31|9 PREREG_E population 31B (co-primary)|r_e_pop31"
  "e_br31|9 PREREG_E branches 31B (corrected fidelity)|r_e_br31"
  "e_popE4B|9 PREREG_E population E4B (secondary)|r_e_popE4B"
  "e_pop12B|9 PREREG_E population 12B (secondary)|r_e_pop12B"
  "e_pop12B6|9 PREREG_E population 12B, sec. 6 conforming|r_e_pop12B6"
  "e_br12|9 PREREG_E branches 12B (secondary)|r_e_br12"
  "e_brE4B|9 PREREG_E branches E4B (secondary)|r_e_brE4B"
  "v24|10 PREREG_v2.4 (exact-intent repair battery)|r_v24"
  "f_repair|11 F ANALYSIS_PLAN (weight-space repair)|nr_f_repair"
  "v25|12 PREREG_v2.5 (full stack, 31B)|r_v25"
  "sweep|13 F SWEEP_PLAN (frozen sweep_report.py)|r_sweep"
  "sweep_ship|13 F SWEEP_PLAN re-scored by shipped code|r_sweep_ship"
  "v26|14 PREREG_v2.6 (audit pick)|r_v26"
  "v25b|15 PREREG_v2.5b (full stack, E4B)|r_v25b"
  "v27|16 PREREG_v2.7 robustness|r_v27"
  "v27_pool|16 PREREG_v2.7 pooled retest (logged deviation)|r_v27_pool"
  "soak|16 PREREG_v2.7 sec. 5 soak|r_soak"
  "v28|17 PREREG_v2.8 (TranscriptLab CLI vs C1)|r_v28"
  "e_ext|18 PREREG_E_ext (8 fresh replicates; resolve NI)|r_e_ext"
  "v29|19 PREREG_v2.9 (CLI coverage, E2B / E4B)|r_v29"
  "v210|20 PREREG_v2.10 (audit breadth)|r_v210"
  "v210_rescore|20 PREREG_v2.10 audits re-scored from records|r_v210_rescore"
  "e_awq|21 PREREG_E_awq (audit pick end to end)|r_e_awq"
  "e_awq2|22 PREREG_E_awq2 (proxy on the audit pick, 6 fresh replicates)|r_e_awq2"
  "bf16|bf16 row (EXPLORATORY benchmark row)|r_bf16"
  "ex_dist|EXPLORATORY B3/B9/B10 (E2E distributions)|r_ex_dist"
  "ex_boot|EXPLORATORY E2E bootstrap-seed audit|r_ex_boot"
  "ex_cens|EXPLORATORY B13 (audit censoring)|nr_ex_cens"
)

if [ "${1:-}" = "--list" ]; then for r in "${ROWS[@]}"; do IFS='|' read -r id reg fn <<<"$r"; printf '%-14s %s\n' "$id" "$reg"; done; exit 0; fi
SEL=" $* "

mkdir -p "$ROOT/tmp"
OUT=${OUT:-$(mktemp -d -p "$ROOT/tmp" l1.XXXXXX)}
mkdir -p "$OUT" && OUT=$(cd "$OUT" && pwd)
case "$OUT/" in "$ROOT/experiments/"*|"$ROOT/release/"*|"$ROOT/data/"*) echo "refusing OUT inside the tree: $OUT" >&2; exit 2;; esac
mkdir -p "$OUT/logs" "$OUT/cmp" "$OUT/.tmp" "$OUT/.cache" "$OUT/.config"
SUMMARY=$OUT/summary.tsv; : >"$SUMMARY"; touch "$OUT/.start"; RELEASED=()
echo "ROOT=$ROOT"; echo "OUT=$OUT"; echo "PY_G=$PY_G  PY_A=$PY_A  cores=${TASKSET:-none}  mem=${MEM_GB}G  PYTHONHASHSEED=$HASHSEED"

# ------------------------------------------------------------------------------------------------------- helpers
# show: printable command (interpreters as "python", $OUT and $ROOT kept symbolic); showdir: workdir relative to ROOT
show() { local s="$*"; s=${s//$PY_G/python}; s=${s//$PY_A/python}; s=${s//$OUT/\$OUT}; s=${s//$ROOT\//\$ROOT/}; echo "$s"; }
showdir() { if [ "$1" = "$ROOT" ]; then echo .; else case "$1" in "$OUT"*) show "$1";; "$ROOT"/*) echo "${1#$ROOT/}";; *) show "$1";; esac; fi; }

# pyrun <workdir (relative to ROOT, or absolute)> <command...>: runs with the resource limits and a write-safe
# environment; stdout+stderr to the row log (stdout to $PYRUN_STDOUT if set).
pyrun() {
  local wd=$1; shift
  case "$wd" in /*) ;; *) wd=$ROOT/$wd;; esac
  ROW_CMDS+=("(cd $(showdir "$wd") && $(show "$@")${PYRUN_STDOUT:+ > $(show "$PYRUN_STDOUT")})")
  echo "\$ (cd $wd && $*)" >>"$LOG"
  local so=${PYRUN_STDOUT:-$LOG}
  ( cd "$wd" || exit 97
    ulimit -v $((MEM_GB * 1024 * 1024)) 2>/dev/null || true
    exec env PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED="$HASHSEED" CUDA_VISIBLE_DEVICES= TRANSCRIPTLAB_ROOT="$ROOT" \
      OMP_NUM_THREADS="$NCORES" OPENBLAS_NUM_THREADS="$NCORES" MKL_NUM_THREADS="$NCORES" NUMEXPR_NUM_THREADS="$NCORES" \
      TOKENIZERS_PARALLELISM=false TMPDIR="$OUT/.tmp" XDG_CACHE_HOME="$OUT/.cache" XDG_CONFIG_HOME="$OUT/.config" \
      HF_HOME="$OUT/.cache/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MPLCONFIGDIR="$OUT/.config/mpl" \
      VLLM_CACHE_ROOT="$OUT/.cache/vllm" VLLM_CONFIG_ROOT="$OUT/.config/vllm" VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 \
      TRITON_CACHE_DIR="$OUT/.cache/triton" TORCHINDUCTOR_CACHE_DIR="$OUT/.cache/inductor" \
      $TASKSET "$@" ) >>"$so" 2>>"$LOG"
  local rc=$?
  if [ $rc -ne 0 ] && [ -z "${ALLOW_RC:-}" ]; then ROW_FAIL=1; ROW_DET+="command failed (rc=$rc, see logs/$ROW.log); "; fi
  return $rc
}

# cmpj <released file (relative to ROOT)> <new file> [compare_json.py options]
cmpj() {
  local rel=$1 new=$2; shift 2
  RELEASED+=("$ROOT/$rel")
  local line res det
  line=$("$PY_C" "$TOOLS/compare_json.py" "$ROOT/$rel" "$new" --report "$OUT/cmp/$ROW.$(basename "$new").json" "$@")
  res=${line%%$'\t'*}; det=${line#*$'\t'}; [ "$det" = "$line" ] && det=""
  echo "   ${rel#experiments/}: $res${det:+  ($det)}" | tee -a "$LOG"
  ROW_N=$((ROW_N + 1))
  case "$res" in
    IDENTICAL) [ -n "$det" ] && ROW_DET+="$(basename "$rel"): $det; ";;
    POINTS-IDENTICAL) [ "$ROW_RES" = DIFFERENT ] || ROW_RES=POINTS-IDENTICAL; ROW_DET+="$(basename "$rel"): $det; ";;
    *) ROW_RES=DIFFERENT; ROW_DET+="$(basename "$rel"): $det; ";;
  esac
}

record() {  # record <result> <seconds> <detail>
  local cmd; cmd=$(printf '%s; ' ${ROW_CMDS[@]+"${ROW_CMDS[@]}"}); cmd=${cmd%; }
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$ROW" "$ROW_REG" "$1" "$2" "${cmd:--}" "$3" >>"$SUMMARY"
  echo "-> $ROW: $1 (${2}s)"
}

notrun() {  # notrun <frozen script (not run)> <released file> <reason>
  ROW_CMDS=("not run: $(show "$1")"); record "NOT RUN" 0 "$3 [released: $2]"
}

# ---------------------------------------------------------------------------------------------- NOT RUN rows
nr_v1() { notrun "$C/scripts/prereg_analysis.py" "$C/out/prereg_analysis.json" "scripts/prereg_analysis.py has no output option: it always writes $C/out/prereg_analysis.json (would overwrite the released file); it also reads the main-track discovery contexts (variants.ROOT, outside the project tree, not released)"; }
nr_epred() { notrun "(none)" "$E/analysis/E_predictions_eval.md" "manual evaluation by the PI (Markdown, no script); its inputs are rows e_pop31, e_popE4B, e_pop12B6, e_br31, e_br12, e_brE4B"; }
nr_x_disc_ana() { notrun "$X/scripts/discovery/analyze.py" "$X/out/ana_<model>[_heldout].json" "scripts/discovery/analyze.py reads the main-track contexts through arms.load_meta()/variants.ROOT (the data holder's main-track run tree, outside the project tree; not released)"; }
nr_x_disc_res() { notrun "$X/scripts/finalize.py" "$X/results.json" "scripts/finalize.py has no output option: it always writes $X/results.json; its registered part (registered_decisions) is row x_disc_dec"; }
nr_v21() { notrun "$C/scripts/analyze_v21_v22.py --battery v21" "$C/out/v21_analysis.json" "scripts/analyze_v21_v22.py re-reads every main-track context (variants.load_context -> the data holder's main-track run tree, outside the project tree; not released) for its copy classes and P5 template check"; }
nr_v22() { notrun "$C/scripts/analyze_v21_v22.py --battery S|H" "$C/out/v22S_analysis.json, v22H_analysis.json" "same script as v2.1 (analyze_v21_v22.py --battery S|H): needs the main-track contexts (not released)"; }
nr_f_repair() { notrun "$W/repair_memit.py (gpu3_C_gate.sh)" "$W/out/repair_heldout_final.json, repairC_heldout_final.json" "re-computes the repair from model weights and extracted activations (out/hf_qatct.pt, out/hf_bf16.pt, 6 GB; the 31B model.safetensors), not from run records; the registered run used --device cuda:0 and --save_adapter into $W/adapters: Level 2"; }
nr_ex_cens() { notrun "$W/EXPLORATORY_censoring.py" "$W/out/EXPLORATORY_censoring.json" "EXPLORATORY_censoring.py has no output option: it always writes $W/out/EXPLORATORY_censoring.json (would overwrite the released file)"; }

# ---------------------------------------------------------------------------------------------- contagion (A)
r_v2() {
  pyrun $C "$PY_G" scripts/confirm_v2_analysis.py --pools data/confirmatory/pools --meta data/confirmatory/meta_S1.jsonl \
    --res31 out/main/rC31b_v2.jsonl --res12 out/main/rC12b_v2.jsonl --rese4 out/main/rCe4b_v2.jsonl --out "$D/confirm_v2_all_full.json"
  cmpj $C/out/confirmatory/confirm_v2_all_full.json "$D/confirm_v2_all_full.json"
}
r_v2_ver() {
  pyrun $C "$PY_G" scripts/confirm_v2_analysis.py --pools data/confirmatory/pools_verified_sensitivity --meta data/confirmatory/meta_S1.jsonl \
    --res31 out/main/rC31b_v2.jsonl --res12 out/main/rC12b_v2.jsonl --rese4 out/main/rCe4b_v2.jsonl --out "$D/confirm_v2_all_verified_sens.json"
  cmpj $C/out/confirmatory/confirm_v2_all_verified_sens.json "$D/confirm_v2_all_verified_sens.json"
}
r_v23() {
  pyrun $C "$PY_G" scripts/analyze_onset_v23.py --out "$D/onset_v23_analysis.json"
  cmpj $C/out/onset_v23_analysis.json "$D/onset_v23_analysis.json"
}
r_v26() {
  pyrun $C "$PY_G" scripts/analyze_v26_audit.py --out "$D/v26_audit_analysis.json"
  cmpj $C/out/confirmatory/v26_audit_analysis.json "$D/v26_audit_analysis.json"
}
r_v27() {
  pyrun $C "$PY_G" scripts/analyze_v27_robustness.py --out "$D/v27_robustness_analysis.json"
  cmpj $C/out/confirmatory/v27_robustness_analysis.json "$D/v27_robustness_analysis.json"
}
r_v27_pool() {
  pyrun $C "$PY_G" scripts/v27_pooled_retest.py --out "$D/v27_pooled_retest.json"
  cmpj $C/out/confirmatory/v27_pooled_retest.json "$D/v27_pooled_retest.json"
}
r_bf16() {
  pyrun $C "$PY_G" scripts/analyze_bf16_core.py --res out/main/rCbf16_v2.jsonl --log logs/ctg-Cbf16.log --out "$D/bf16_core_all.json"
  cmpj $C/out/confirmatory/bf16_core_all.json "$D/bf16_core_all.json"
  pyrun $C "$PY_G" scripts/analyze_bf16_core.py --res out/main/rCbf16_v2.jsonl --log logs/ctg-Cbf16.log --subset le13000 --out "$D/bf16_core_le13000.json"
  cmpj $C/out/confirmatory/bf16_core_le13000.json "$D/bf16_core_le13000.json"
}
r_v28() {   # experiments/v28/run_cli.sh; plus the CLI's own report analysis (run_v28/report.log)
  pyrun . "$PY_G" $C/scripts/analyze_v28_cli.py --cli_gen "$ROOT/$T/run_v28/gen.jsonl" --out "$D/v28_cli_analysis.json"
  cmpj $C/out/confirmatory/v28_cli_analysis.json "$D/v28_cli_analysis.json"
  pyrun . "$PY_G" "$ROOT/$C/scripts/analyze_bf16_core.py" --res "$ROOT/$T/run_v28/gen.jsonl" --log "$ROOT/$T/run_v28/run.log" \
    --out "$D/run_v28.analysis.json" --B 2000
  cmpj $T/run_v28/analysis.json "$D/run_v28.analysis.json"
}
r_v29() {   # experiments/v29/run_cov.sh: transcriptlab report (analyze_bf16_core.py) per run, then the frozen verdicts
  local r
  for r in run_e2b run_e4b16; do
    mkdir -p "$D/$T/$r"
    pyrun . "$PY_G" "$ROOT/$C/scripts/analyze_bf16_core.py" --res "$ROOT/$T/$r/gen.jsonl" --log "$ROOT/$T/$r/run.log" \
      --out "$D/$T/$r/analysis.json" --B 2000
    cmpj $T/$r/analysis.json "$D/$T/$r/analysis.json"
  done
  # same relative --runs arguments as the registered run, resolved inside $D (so the verdicts read the re-computed files)
  pyrun "$D" "$PY_A" "$ROOT/$C/scripts/analyze_v29_coverage.py" --runs $T/run_e2b $T/run_e4b16 --out "$D/v29_coverage.json"
  cmpj $C/out/confirmatory/v29_coverage.json "$D/v29_coverage.json"
}

# --------------------------------------------------------------------------------------- intent decoding (B)
r_v24() {
  pyrun $B "$PY_G" v24/analyze_battery.py v24/battery_run.jsonl --out "$D/battery_run_analysis.json"
  cmpj $B/v24/battery_run_analysis.json "$D/battery_run_analysis.json"
  cmpj $B/v24/battery_run_analysis_states.jsonl "$D/battery_run_analysis_states.jsonl"
}
r_v25() {
  pyrun $B "$PY_G" v25/analyze_v25.py --out "$D/analysis_v25.json"
  cmpj $B/v25/out/analysis_v25.json "$D/analysis_v25.json"
}
r_v25b() {
  pyrun $B "$PY_G" v25b/analyze_v25b.py --out "$D/analysis_v25b.json"
  cmpj $B/v25b/out/analysis_v25b.json "$D/analysis_v25b.json"
}

# ------------------------------------------------------------------------------------------- weights (F)
r_sweep() {
  pyrun $W "$PY_G" sweep_report.py --out "$D/sweep_report.json"
  cmpj $W/out/sweep_report.json "$D/sweep_report.json"
  pyrun $W "$PY_G" sweep_report.py --ref e4b_bf16 --out "$D/sweep_report_e4bref.json"
  cmpj $W/out/sweep_report_e4bref.json "$D/sweep_report_e4bref.json"
}
r_sweep_ship() {   # the shipped slipguard.weights code re-scores F's frozen sweep records (prints one JSON summary)
  PYRUN_STDOUT="$D/check_wsa.json" ALLOW_RC=1 pyrun . "$PY_A" slipguard/dev/check_wsa.py $W/out
  RELEASED+=("$ROOT/$W/out/sweep_report.json" "$ROOT/$W/out/sweep_report_e4bref.json")
  local line res det
  line=$("$PY_C" "$TOOLS/compare_json.py" --wsa-check "$D/check_wsa.json" --mc-tol 0.05 --report "$OUT/cmp/$ROW.json")
  res=${line%%$'\t'*}; det=${line#*$'\t'}; ROW_N=1; echo "   check_wsa: $res ($det)" | tee -a "$LOG"
  case "$res" in IDENTICAL) ;; POINTS-IDENTICAL) ROW_RES=$res; ROW_DET+="$det; ";; *) ROW_RES=DIFFERENT; ROW_DET+="$det; ";; esac
}
r_v210() {   # experiments/v210/run_audits.sh (last line)
  pyrun . "$PY_A" experiments/v210/analyze_v210.py --out "$D/v210_audit_breadth.json"
  cmpj $W/out/v210_audit_breadth.json "$D/v210_audit_breadth.json"
}
r_v210_rescore() {  # slipguard audit-weights --from-records (CPU) on each released v2.10 record file
  local f n
  for f in "$ROOT/$W"/out/audit_v210_*.records.jsonl; do
    n=$(basename "$f" .records.jsonl)
    pyrun slipguard env PYTHONPATH=src "$PY_A" -m slipguard audit-weights --from-records "$f" \
      --reference "$ROOT/$W/out/audit_sweep_31b_bf16.records.jsonl" --out "$D/$n.json"
    # run metadata only: --from-records cannot know which pack the endpoint run used (no "pack" block), and
    # tool.slipguard is the version string of the package that wrote the report (audits ran with 0.1.0.dev0)
    cmpj $W/out/$n.json "$D/$n.json" --ignore '^/pack$|^/tool/slipguard$'
  done
}

# ---------------------------------------------------------------------------------------------- soak (v2.7 sec. 5)
r_soak() {   # experiments/v27/soak.sh (frozen analysis line); the unit names are the ones soak.sh saved
  local O=$ROOT/experiments/soak/out
  pyrun . "$PY_A" experiments/soak/soak_analyze.py --dir "$O" --proxy_logs "$O/proxy_logs" \
    --proxy_scope "$(cat "$O/proxy_scope.txt")" --stock_scope "$(cat "$O/stock_scope.txt")" \
    --plugin_scope "$(cat "$O/plugin_scope.txt")" --out "$D/soak_analysis.json"
  cmpj experiments/soak/out/soak_analysis.json "$D/soak_analysis.json"
}

# --------------------------------------------------------------------------------------------- end to end (E)
# The frozen prereg_analysis.py seeds each paired-difference bootstrap with hash(key) % 1000; str hashes are
# randomised per process, so these leaves (and the Holm p derived from them) are one Monte-Carlo draw.
E_MC='(diff_fullp_minus_base|diff_vs_base)/(ci95\[[01]\]|p_boot)$|/p_holm$'
P31B="runs/pop31r1s0_H_base+runs/pop31r1s1_H_base+runs/pop31r2s0_H_base+runs/pop31r2s1_H_base"
P31F="runs/pop31r1s0_H_fullp+runs/pop31r1s1_H_fullp+runs/pop31r2s0_H_fullp+runs/pop31r2s1_H_fullp"
grp() { echo "plan=plans/$1.json,base=runs/$2_base,quar=runs/$2_quar,ipd=runs/$2_ipd,fullp=runs/$2_fullp"; }
# seedrange <new 31B output> <population_31B|branches_31B>: are the re-run's hash-seeded CIs / p inside the range that
# EXPLORATORY_bootseed.json found over all 1,000 possible seeds? (explains the POINTS-IDENTICAL; outside -> DIFFERENT)
seedrange() {
  local ok
  ok=$("$PY_C" - "$ROOT/$E/analysis/EXPLORATORY_bootseed.json" "$1" "$2" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))[sys.argv[3]]; n = json.load(open(sys.argv[2]))
pop = sys.argv[3] == 'population_31B'
bad = []
for k, r in s.items():
    if not isinstance(r, dict) or 'ci_lo_range' not in r:
        continue
    d = (n['co_primary'][k]['diff_fullp_minus_base'] if pop else n['post_onset'][k]['diff_vs_base'])
    lo, hi = d['ci95']
    if not (r['ci_lo_range'][0] <= lo <= r['ci_lo_range'][1] and r['ci_hi_range'][0] <= hi <= r['ci_hi_range'][1]
            and d['p_boot'] <= r['p_boot_max']):
        bad.append(k)
print('ok' if not bad else 'outside for ' + ','.join(bad))
PY
)
  echo "   all-seed range check ($2): $ok" | tee -a "$LOG"
  if [ "$ok" = ok ]; then ROW_DET+="re-run CIs and p inside the 1,000-seed range of EXPLORATORY_bootseed.json; "
  else ROW_RES=DIFFERENT; ROW_DET+="re-run CI $ok the 1,000-seed range of EXPLORATORY_bootseed.json; "; fi
}
r_e_pop31() {   # experiments/endtoend/RUNBOOK.md (unblinding sequence)
  pyrun $E "$PY_A" analysis/prereg_analysis.py population --label 31B --base $P31B --fullp $P31F \
    --proxy-logs logs/proxy_pop31r1s0 logs/proxy_pop31r1s1 logs/proxy_pop31r2s0 logs/proxy_pop31r2s1 --out "$D/prereg_pop31.json"
  cmpj $E/analysis/prereg_pop31.json "$D/prereg_pop31.json" --mc "$E_MC"
  seedrange "$D/prereg_pop31.json" population_31B
}
r_e_popE4B() {
  pyrun $E "$PY_A" analysis/prereg_analysis.py population --label E4B --base runs/popE4r1_H_base --fullp runs/popE4r1_H_fullp \
    --proxy-logs logs/proxy_popE4r1 --out "$D/prereg_popE4B.json"
  cmpj $E/analysis/prereg_popE4B.json "$D/prereg_popE4B.json" --mc "$E_MC"
}
r_e_pop12B() {
  pyrun $E "$PY_A" analysis/prereg_analysis.py population --label 12B --base runs/pop12r1_H_base --fullp runs/pop12r1_H_fullp \
    --proxy-logs logs/proxy_pop12r1 --out "$D/prereg_pop12B.json"
  cmpj $E/analysis/prereg_pop12B.json "$D/prereg_pop12B.json" --mc "$E_MC"
}
r_e_pop12B6() {   # PREREG_DEVIATIONS.md: sec. 6 wrapper (context-length errors are outcomes)
  pyrun $E "$PY_A" analysis/prereg_sec6_conforming.py population --label 12B_sec6conforming --base runs/pop12r1_H_base \
    --fullp runs/pop12r1_H_fullp --proxy-logs logs/proxy_pop12r1 --out "$D/prereg_pop12B_sec6conforming.json"
  cmpj $E/analysis/prereg_pop12B_sec6conforming.json "$D/prereg_pop12B_sec6conforming.json" --mc "$E_MC"
}
r_e_br31() {   # groups as in EXPLORATORY_distributions.py (BR31): b31a / b31b (= plans/b31.json split) and b31_2 on lane b31c
  pyrun $E "$PY_A" analysis/prereg_branch_corrected.py branches --label 31B --group "$(grp b31a b31a)" --group "$(grp b31b b31b)" \
    --group "$(grp b31_2 b31c)" --proxy-logs logs/proxy_b31a logs/proxy_b31b logs/proxy_b31c --out "$D/prereg_br31.json"
  cmpj $E/analysis/prereg_br31.json "$D/prereg_br31.json" --mc "$E_MC"
  seedrange "$D/prereg_br31.json" branches_31B
  cmpj $E/analysis/prereg_br31.json.fidelity.json "$D/prereg_br31.json.fidelity.json"
}
r_e_br12() {
  pyrun $E "$PY_A" analysis/prereg_branch_corrected.py branches --label 12B --group "$(grp b12 b12)" --proxy-logs logs/proxy_b12 \
    --out "$D/prereg_br12.json"
  cmpj $E/analysis/prereg_br12.json "$D/prereg_br12.json" --mc "$E_MC"
  cmpj $E/analysis/prereg_br12.json.fidelity.json "$D/prereg_br12.json.fidelity.json"
}
r_e_brE4B() {
  pyrun $E "$PY_A" analysis/prereg_branch_corrected.py branches --label E4B --group "$(grp bE4 bE4)" --proxy-logs logs/proxy_bE4 \
    --out "$D/prereg_brE4B.json"
  cmpj $E/analysis/prereg_brE4B.json "$D/prereg_brE4B.json" --mc "$E_MC"
  cmpj $E/analysis/prereg_brE4B.json.fidelity.json "$D/prereg_brE4B.json.fidelity.json"
}
# PREREG_E_ext and PREREG_E_awq pass every bootstrap seed explicitly (no hash seeding), so they must be IDENTICAL.
# Each was run once (PROGRESS.md, 2026-11-07 06:50:58 and 06:51:34 UTC); their printed summaries were released as
# *.stdout.txt and are compared too.
r_e_ext() {   # analysis set r3..r10 (the script finds it from the completed replicates; defaults --first 3 --last 10)
  PYRUN_STDOUT="$D/prereg_E_ext.stdout.txt" pyrun $E "$PY_A" analysis/prereg_E_ext_analysis.py --out "$D/prereg_E_ext.json"
  cmpj $E/analysis/prereg_E_ext.json "$D/prereg_E_ext.json"
  cmpj $E/analysis/prereg_E_ext.stdout.txt "$D/prereg_E_ext.stdout.txt"
}
r_e_awq() {   # QAT comparator = PREREG_E's r1, r2 + PREREG_E_ext's final analysis set r3..r10 (PREREG_E_awq sec. 3)
  PYRUN_STDOUT="$D/prereg_E_awq.stdout.txt" pyrun $E "$PY_A" analysis/prereg_E_awq_analysis.py --qat_reps 1 2 3 4 5 6 7 8 9 10 \
    --out "$D/prereg_E_awq.json"
  cmpj $E/analysis/prereg_E_awq.json "$D/prereg_E_awq.json"
  cmpj $E/analysis/prereg_E_awq.stdout.txt "$D/prereg_E_awq.stdout.txt"
}
# PREREG_E_awq2: run once on 2026-11-07 13:06:15 UTC (PROGRESS.md); explicit integer seeds, so it must be IDENTICAL.
r_e_awq2() {   # analysis set r3..r8 (fresh AWQ replicates; script defaults --first 3 --last 8); S4 comparator pop31 r1..r10
  PYRUN_STDOUT="$D/prereg_E_awq2.stdout.txt" pyrun $E "$PY_A" analysis/prereg_E_awq2_analysis.py --out "$D/prereg_E_awq2.json"
  cmpj $E/analysis/prereg_E_awq2.json "$D/prereg_E_awq2.json"
  cmpj $E/analysis/prereg_E_awq2.stdout.txt "$D/prereg_E_awq2.stdout.txt"
}
r_ex_dist() {
  pyrun $E "$PY_A" analysis/EXPLORATORY_distributions.py --out "$D/EXPLORATORY_distributions.json"
  cmpj $E/analysis/EXPLORATORY_distributions.json "$D/EXPLORATORY_distributions.json"
}
r_ex_boot() {   # all 1,000 seeds x 5 contrasts x B = 10,000 (the slow row); --procs = the CPU budget
  pyrun $E "$PY_A" analysis/EXPLORATORY_bootseed.py --out "$D/EXPLORATORY_bootseed.json" --procs "$NCORES"
  cmpj $E/analysis/EXPLORATORY_bootseed.json "$D/EXPLORATORY_bootseed.json"
}

# --------------------------------------------------------------------------------------------- cross-family (X)
r_x_disc_dec() {   # scripts/combine.py (registered md5 d5e869fc) on the released per-model analyses
  pyrun $X "$PY_G" scripts/combine.py "$D/results_x.json"
  cmpj $X/results.json "$D/results_x.json" --released-key registered_decisions
  cmpj $X/out/results_x.json "$D/results_x.json"
}
r_v2_qwen() {   # scripts/post_v2.sh: frozen v2 analyze.py (full, H1, H2, lenient) per model, then combine_v2.py
  local mk; mkdir -p "$D/v2"
  for mk in qwen3-8b qwen3-32b qwen3.5-9b; do
    pyrun $X "$PY_G" scripts/v2_frozen/analyze.py --mk $mk --manifest "$MAN" --gen out/v2/gen_$mk.jsonl --out "$D/v2/ana_$mk.json"
    pyrun $X "$PY_G" scripts/v2_frozen/analyze.py --mk $mk --manifest "$MAN" --gen out/v2/gen_$mk.jsonl --ids out/v2/ids_A1_H1.txt --out "$D/v2/ana_${mk}_H1.json"
    pyrun $X "$PY_G" scripts/v2_frozen/analyze.py --mk $mk --manifest "$MAN" --gen out/v2/gen_$mk.jsonl --ids out/v2/ids_A1_H2.txt --out "$D/v2/ana_${mk}_H2.json"
    pyrun $X "$PY_G" scripts/v2_frozen/analyze.py --mk $mk --manifest "$MAN" --gen out/v2/gen_${mk}_lenient.jsonl --out "$D/v2/ana_${mk}_lenient.json"
    for s in "" _H1 _H2 _lenient; do cmpj $X/out/v2/ana_$mk$s.json "$D/v2/ana_$mk$s.json"; done
  done
  pyrun $X "$PY_G" scripts/v2_frozen/combine_v2.py "$D/results_v2.json" "$D/v2"
  # ana_dir records where combine_v2.py read the per-model analyses from (here: the re-computed ones in $D/v2)
  cmpj $X/out/v2/results_v2.json "$D/results_v2.json" --ignore '^/ana_dir$'
}
r_x_ext() {   # scripts/post_ext.sh: frozen ext analyze.py (full, H1, H2) per model, then combine_ext.py
  local mk; mkdir -p "$D/ext"
  for mk in gpt-oss-20b qwen3-coder-30b devstral-24b qwen3.8-27b; do
    pyrun $X env TIKTOKEN_RS_CACHE_DIR="$ROOT/$X/data/tiktoken_cache" "$PY_G" scripts/ext_frozen/analyze.py --mk $mk --manifest "$MAN" --gen out/ext/gen_$mk.jsonl --out "$D/ext/ana_$mk.json"
    pyrun $X env TIKTOKEN_RS_CACHE_DIR="$ROOT/$X/data/tiktoken_cache" "$PY_G" scripts/ext_frozen/analyze.py --mk $mk --manifest "$MAN" --gen out/ext/gen_$mk.jsonl --ids out/ext/ids_A1_H1.txt --out "$D/ext/ana_${mk}_H1.json"
    pyrun $X env TIKTOKEN_RS_CACHE_DIR="$ROOT/$X/data/tiktoken_cache" "$PY_G" scripts/ext_frozen/analyze.py --mk $mk --manifest "$MAN" --gen out/ext/gen_$mk.jsonl --ids out/ext/ids_A1_H2.txt --out "$D/ext/ana_${mk}_H2.json"
    for s in "" _H1 _H2; do cmpj $X/out/ext/ana_$mk$s.json "$D/ext/ana_$mk$s.json"; done
  done
  pyrun $X "$PY_G" scripts/combine_ext.py "$D/results_ext.json" "$D/ext"
  cmpj $X/out/ext/results_ext.json "$D/results_ext.json"
}

# ------------------------------------------------------------------------------------------------------ main
# (one compound command: bash parses it whole before running, so editing this file mid-run cannot break the run)
{
T0=$(date +%s)
for r in "${ROWS[@]}"; do
  IFS='|' read -r ROW ROW_REG fn <<<"$r"
  if [ "$SEL" != "  " ] && [[ "$SEL" != *" $ROW "* ]]; then continue; fi
  D=$OUT/$ROW; LOG=$OUT/logs/$ROW.log; ROW_RES=IDENTICAL; ROW_DET=""; ROW_CMDS=(); ROW_N=0; ROW_FAIL=0
  echo "== $ROW  [$ROW_REG]"
  case "$fn" in nr_*) "$fn"; continue;; esac
  # public tree: the end-to-end run records (experiments/endtoend/runs, logs, plans) are not released (competition
  # task text and repository code, Kaggle competition terms); these rows then report NOT RUN with the reason.
  case "$fn" in r_e_*|r_ex_dist|r_ex_boot)
    if [ ! -d "$ROOT/$E/runs" ]; then
      ROW_CMDS=("not run: $E/runs/ is not in this release")
      record "NOT RUN" 0 "needs the end-to-end run records ($E/runs/, $E/logs/, $E/plans/), which the public release does not include: they hold the competition task text, its sample prompt and repository code (Kaggle competition terms); runs from the project layout [released: $E/analysis/*.json]"
      continue
    fi;;
  esac
  mkdir -p "$D"; t0=$(date +%s.%N)
  "$fn"
  secs=$("$PY_C" -c "import sys;print(round(float(sys.argv[2])-float(sys.argv[1]),1))" "$t0" "$(date +%s.%N)")
  if [ "$ROW_FAIL" = 1 ]; then ROW_RES=FAILED; elif [ "$ROW_N" = 0 ]; then ROW_RES=FAILED; ROW_DET+="no comparison made; "; fi
  record "$ROW_RES" "$secs" "$ROW_N file(s) compared${ROW_DET:+; ${ROW_DET%; }}"
done
TOTAL=$(( $(date +%s) - T0 ))

# released files must be untouched by the run
CHANGED=0
for f in ${RELEASED[@]+"${RELEASED[@]}"}; do
  if [ -e "$f" ] && [ "$f" -nt "$OUT/.start" ]; then echo "WARNING: released file modified during the run: $f"; CHANGED=1; fi
done

echo
echo "================================ Level-1 summary (OUT=$OUT, total ${TOTAL}s)"
awk -F'\t' '{printf "%-13s %-17s %7s  %s\n", $1, $3, $4, $2}' "$SUMMARY"
{ echo "| row | registration | result | seconds | command | detail |"; echo "|---|---|---|---|---|---|"
  awk -F'\t' '{gsub(/\|/, "\\|"); printf "| %s | %s | %s | %s | `%s` | %s |\n", $1, $2, $3, $4, $5, $6}' "$SUMMARY"
  echo; echo "Total runtime: ${TOTAL} s"; } >"$OUT/summary.md"
for k in IDENTICAL POINTS-IDENTICAL DIFFERENT FAILED "NOT RUN"; do
  printf '%-17s %s\n' "$k" "$(awk -F'\t' -v k="$k" '$3==k' "$SUMMARY" | wc -l)"
done
echo "summary: $OUT/summary.tsv, $OUT/summary.md; logs: $OUT/logs/; comparison reports: $OUT/cmp/"
if [ "$CHANGED" = 1 ] || awk -F'\t' '$3=="DIFFERENT" || $3=="FAILED"{f=1} END{exit !f}' "$SUMMARY"; then exit 1; fi
exit 0
}
