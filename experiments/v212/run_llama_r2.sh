#!/bin/bash
# PREREG_v2.12 runner r2 (PI; deviation 1 2026-11-08: transcriptlab 0.1.3 request adapter; no v2.11 wait; gate 2 min). Original: after PREREG_v2.11's analysis line appears, wait for GPU 4 free 10 min, then Hermes-3 run.
set -u
G=4; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models/community/NousResearch_Hermes-3-Llama-3.1-8B; LIM=$P/tools/limited.sh
OUT=$P/experiments/transcriptlab_cli/run_v212_hermes3; LOG=$P/experiments/v212/run_llama.log
PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOG; }
gate() { local used uuid apps
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $G | tr -d ' ')
  uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $G | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
  [ "${used:-99999}" -lt 2048 ] && [ "$apps" -eq 0 ]; }
say "r2 (deviation 1): v2.11 already done"
: # r2: no wait for v2.11
say "r2: waiting for GPU $G (2 min free)"; ok=0
for i in $(seq 1 1080); do if gate; then ok=$((ok+1)); else ok=0; fi; [ $ok -ge 4 ] && break; sleep 30; done
[ $ok -ge 4 ] || { say "GPU $G never free -> NOT RUN"; exit 3; }
say "gate OK on GPU $G"
$P/tools/serve_vllm.sh $G $PORT $M hermes3-8b --max-num-seqs 64 | tee -a $LOG
for i in $(seq 1 180); do curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null && break; sleep 10; done
curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null || { say "server not ready"; systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop; exit 4; }
grep -m1 "non-default args" $P/logs/vllm/g${G}_${PORT}.log >> $LOG
cli() { ( cd $P/release/transcriptlab && TMPDIR=$P/tmp TRANSCRIPTLAB_ROOT=$P PYTHONPATH=src NAME=tlllama QN=VLLM:Worker_D$G MEM=40G CORES=116-117 $LIM $PYA -m transcriptlab "$@" ); }
ARGS="--format hermes --base http://127.0.0.1:$PORT/v1 --model hermes3-8b --tokenizer $M --no-thinking --pool A1 --arms P0,P1,P6,P8a --out $OUT --python $PYG"
say "CLI run start"; cli run $ARGS >> $LOG 2>&1; say "CLI run exited rc=$?; resume pass"
cli run $ARGS >> $LOG 2>&1; say "resume pass rc=$?; gen lines $(wc -l < $OUT/gen.jsonl 2>/dev/null)"
systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop
cli report $OUT --python $PYG >> $LOG 2>&1; say "report rc=$?"
( cd $P && $PYA experiments/v212/analyze_v212.py --run $OUT --out $P/experiments/contagion/out/confirmatory/v212_llama.json >> $LOG 2>&1 )
say "v212 verdict done: $(grep -o '"verdict": "[^"]*"' $P/experiments/contagion/out/confirmatory/v212_llama.json)"
