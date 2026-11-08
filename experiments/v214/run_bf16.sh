#!/bin/bash
# PREREG_v2.14 runner (PI): Gemma-4-31B bf16, TP2 on GPUs 4+5, TranscriptLab via the released CLI 0.1.3, analysis once.
set -u
GA=4; GB=5; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models/gemma-4-31b-it; LIM=$P/tools/limited.sh
OUT=$P/experiments/transcriptlab_cli/run_v214_bf16; LOG=$P/experiments/v214/run_bf16.log
PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOG; }
free1() { local g=$1 used uuid apps
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $g | tr -d ' ')
  uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $g | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
  [ "${used:-99999}" -lt 2048 ] && [ "$apps" -eq 0 ]; }
stop_srv() { systemctl --user list-units "ap-vllm-tp-g${GA}g${GB}*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop; }
say "waiting for GPUs $GA,$GB (2 min free)"; ok=0
for i in $(seq 1 1440); do if free1 $GA && free1 $GB; then ok=$((ok+1)); else ok=0; fi; [ $ok -ge 4 ] && break; sleep 30; done
[ $ok -ge 4 ] || { say "GPUs never free -> NOT RUN"; exit 3; }
say "gate OK on GPUs $GA,$GB"
$P/tools/serve_vllm_tp2.sh $GA $GB $PORT $M gemma-4-31b --max-num-seqs 64 --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 | tee -a $LOG
for i in $(seq 1 240); do curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null && break; sleep 10; done
curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null || { say "server not ready -> NOT RUN"; stop_srv; exit 4; }
grep -m1 "non-default args" $P/logs/vllm/tp_g${GA}g${GB}_${PORT}.log | sed 's/.*non-default args/non-default args/' >> $LOG
cli() { ( cd $P/release/transcriptlab && TMPDIR=$P/tmp TRANSCRIPTLAB_ROOT=$P PYTHONPATH=src NAME=tlbf16 QN=VLLM:Worker_D$GA MEM=40G CORES=116-117 $LIM $PYA -m transcriptlab "$@" ); }
ARGS="--base http://127.0.0.1:$PORT/v1 --model gemma-4-31b --tokenizer $M --pool A1 --arms P0,P1,P6,P8a --out $OUT --python $PYG"
say "CLI run start"; cli run $ARGS >> $LOG 2>&1; say "CLI run exited rc=$?"
ERRF=$($PYA -c "import json; r=[json.loads(l) for l in open('$OUT/gen.jsonl')]; print(round(sum(1 for x in r if x.get('error'))/max(1,len(r)),4))" 2>/dev/null || echo 1)
if $PYA -c "import sys; sys.exit(0 if float('$ERRF') > 0.05 else 1)"; then say "error fraction $ERRF > 0.05 -> stopped before report/analysis (guard) -> NOT RUN"; stop_srv; exit 5; fi
say "error fraction after first pass: $ERRF; resume pass"
cli run $ARGS >> $LOG 2>&1; say "resume pass rc=$?; gen lines $(wc -l < $OUT/gen.jsonl 2>/dev/null)"
stop_srv
cli report $OUT --python $PYG >> $LOG 2>&1; say "report rc=$?"
( cd $P && TMPDIR=$P/tmp NAME=v214ana CORES=116-119 MEM=8G $LIM $PYG experiments/v214/analyze_v214_bf16.py --cli_gen $OUT/gen.jsonl --out $P/experiments/contagion/out/confirmatory/v214_bf16_analysis.json >> $LOG 2>&1 )
say "v214 verdict: $(grep -o '"verdict_[AB]": "[^"]*"' $P/experiments/contagion/out/confirmatory/v214_bf16_analysis.json | tr '\n' ' ')"
