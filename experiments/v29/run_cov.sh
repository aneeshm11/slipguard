#!/bin/bash
# PREREG_v2.9 runner (PI). usage: experiments/v29/run_cov.sh <gpu> <vcores> <cli_cores>   e.g. 6 112-115 116-117
# Runs RE2B then RE4B16 through the released transcriptlab CLI on one GPU (gate: < 2 GB used, 0 compute apps).
set -u
G=$1; VC=$2; CC=$3; PORT=$((8380 + G)); P=${TRANSCRIPTLAB_ROOT:-.}; LOG=$P/experiments/v29/run_cov.log; LIM=$P/tools/limited.sh
PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOG; }
gate() { local used uuid apps
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $G | tr -d ' ')
  uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $G | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
  [ "${used:-99999}" -lt 2048 ] && [ "$apps" -eq 0 ]; }
stop_srv() { systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop; }
cli() { ( cd $P/release/transcriptlab && TMPDIR=$P/tmp TRANSCRIPTLAB_ROOT=$P PYTHONPATH=src NAME=tlcov QN=VLLM:Worker_D$G MEM=40G CORES=$CC \
          $LIM $PYA -m transcriptlab "$@" ); }
for spec in "run_e2b:$P/models/gemma-4-e2b-it-qat-w4a16-ct:gemma-4-e2b" "run_e4b16:$P/models/gemma-4-e4b-it:gemma-4-e4b-bf16"; do
  IFS=: read RUN MD NAME <<< "$spec"; OUT=$P/experiments/transcriptlab_cli/$RUN
  for i in $(seq 1 60); do gate && break; sleep 10; done
  gate || { say "GATE FAILED on GPU $G before $RUN"; exit 3; }
  say "gate OK on GPU $G; $RUN"
  VCORES=$VC $P/tools/serve_vllm.sh $G $PORT $MD $NAME --max-num-seqs 64 --enable-auto-tool-choice \
    --tool-call-parser gemma4 --reasoning-parser gemma4 | tee -a $LOG
  for i in $(seq 1 180); do curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null && break; sleep 10; done
  curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null || { say "$RUN server not ready"; tail -20 $P/logs/vllm/g${G}_${PORT}.log >> $LOG; stop_srv; continue; }
  grep -m1 "non-default args" $P/logs/vllm/g${G}_${PORT}.log >> $LOG
  say "$RUN CLI run start"
  cli run --base http://127.0.0.1:$PORT/v1 --model $NAME --tokenizer $MD --pool A1 --arms P0,P1,P6,P8a --out $OUT --python $PYG >> $LOG 2>&1
  say "$RUN CLI run exited rc=$?; resume pass"
  cli run --base http://127.0.0.1:$PORT/v1 --model $NAME --tokenizer $MD --pool A1 --arms P0,P1,P6,P8a --out $OUT --python $PYG >> $LOG 2>&1
  say "$RUN resume pass exited rc=$?; gen lines $(wc -l < $OUT/gen.jsonl 2>/dev/null)"
  stop_srv; sleep 20
  cli report $OUT --python $PYG >> $LOG 2>&1; say "$RUN report rc=$?"
done
( cd $P && $PYA experiments/contagion/scripts/analyze_v29_coverage.py --runs experiments/transcriptlab_cli/run_e2b \
    experiments/transcriptlab_cli/run_e4b16 --out experiments/contagion/out/confirmatory/v29_coverage.json >> $LOG 2>&1 )
say "v29 verdicts done: $(grep -o '"verdict": "[^"]*"' $P/experiments/contagion/out/confirmatory/v29_coverage.json | tr '\n' ' ')"
