#!/bin/bash
# PREREG_v2.15: one checkpoint on one GPU via the released CLI 0.1.3. usage: run_one.sh <qatawq|qatnvfp4|nvnvfp4> <gpu> <port>
set -u
C=$1; G=$2; PORT=$3; P=${TRANSCRIPTLAB_ROOT:-.}; LIM=$P/tools/limited.sh; CM=$P/models/community; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct
case $C in qatawq) d=cyankiwi_gemma-4-31B-it-qat-AWQ-INT4;; qatnvfp4) d=melcheikh_gemma-4-31B-it-qat-NVFP4-Blackwell;; nvnvfp4) d=nvidia_Gemma-4-31B-IT-NVFP4;; *) exit 9;; esac
OUT=$P/experiments/transcriptlab_cli/run_v215_$C; LOG=$P/experiments/v215/run_$C.log
PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python
TXT='{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'
say() { echo "[$(date -u +%H:%M:%S)] [$C g$G] $*" | tee -a $LOG; }
gate() { local used uuid apps
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $G | tr -d ' ')
  uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $G | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
  [ "${used:-99999}" -lt 2048 ] && [ "$apps" -eq 0 ]; }
stop_srv() { systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop; }
notrun() { mkdir -p $OUT; echo "$*" > $OUT/NOT_RUN; say "NOT RUN: $*"; stop_srv; exit 4; }
say "waiting for GPU $G (2 min free)"; ok=0
for i in $(seq 1 1440); do if gate; then ok=$((ok+1)); else ok=0; fi; [ $ok -ge 4 ] && break; sleep 30; done
[ $ok -ge 4 ] || notrun "GPU never free"
say "gate OK"
$P/tools/serve_vllm.sh $G $PORT $CM/$d gemma-4-31b --dtype bfloat16 --max-num-seqs 64 --hf-overrides "$TXT" --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 | tee -a $LOG
for i in $(seq 1 240); do curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null && break; sleep 10; done
curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null || notrun "server not ready within 40 min"
grep -m1 "non-default args" $P/logs/vllm/g${G}_${PORT}.log | sed 's/.*non-default args/non-default args/' >> $LOG
ARGS="--base http://127.0.0.1:$PORT/v1 --model gemma-4-31b --tokenizer $QAT --pool A1 --arms P0,P1,P6,P8a --out $OUT --python $PYG"
CO=$((108 + 2*(G-4)))-$((109 + 2*(G-4)))
say "CLI run start"; ( cd $P/release/transcriptlab && TMPDIR=$P/tmp TRANSCRIPTLAB_ROOT=$P PYTHONPATH=src NAME=tl215$C QN=VLLM:Worker_D$G MEM=40G CORES=$CO $LIM $PYA -m transcriptlab run $ARGS ) >> $LOG 2>&1; say "CLI run exited rc=$?"
ERRF=$($PYA -c "import json; r=[json.loads(l) for l in open('$OUT/gen.jsonl')]; print(round(sum(1 for x in r if x.get('error'))/max(1,len(r)),4))" 2>/dev/null || echo 1)
if $PYA -c "import sys; sys.exit(0 if float('$ERRF') > 0.05 else 1)"; then notrun "error fraction $ERRF > 0.05 after the first pass"; fi
say "error fraction after first pass: $ERRF; resume pass"
( cd $P/release/transcriptlab && TMPDIR=$P/tmp TRANSCRIPTLAB_ROOT=$P PYTHONPATH=src NAME=tl215$C QN=VLLM:Worker_D$G MEM=40G CORES=$CO $LIM $PYA -m transcriptlab run $ARGS ) >> $LOG 2>&1; say "resume pass rc=$?; gen lines $(wc -l < $OUT/gen.jsonl)"
stop_srv
( cd $P/release/transcriptlab && TMPDIR=$P/tmp TRANSCRIPTLAB_ROOT=$P PYTHONPATH=src $PYA -m transcriptlab report $OUT --python $PYG ) >> $LOG 2>&1; say "report rc=$?"
say "DONE"
