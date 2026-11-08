#!/bin/bash
# PREREG_v2.11 runner r2 (PI; deviation 2026-11-08: --corpus takes the S1 manifest.json, gate 2 min). Original: Waits (<= 12 h) until GPU 4 passes the user's gate (< 2 GB used, 0 compute apps) for 20
# consecutive 30-s polls (10 min), then: QAT-ct server :8384, released CLI on the masked PNC, resume pass, report, analysis once.
set -u
G=4; PORT=8384; P=${TRANSCRIPTLAB_ROOT:-.}; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; LIM=$P/tools/limited.sh
MASK=$P/release/package/pnc_v1.1_masked; META=$P/tmp/wp_pnc/meta_S1_masked.jsonl
OUT=$P/experiments/transcriptlab_cli/run_v211_masked; LOG=$P/experiments/v211/run_masked.log
PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOG; }
gate() { local used uuid apps
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $G | tr -d ' ')
  uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $G | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
  [ "${used:-99999}" -lt 2048 ] && [ "$apps" -eq 0 ]; }
say "r2: waiting for GPU $G (2 min free)"; ok=0
for i in $(seq 1 1440); do if gate; then ok=$((ok+1)); else ok=0; fi; [ $ok -ge 4 ] && break; sleep 30; done
[ $ok -ge 4 ] || { say "GPU $G never free for 2 min within 12 h -> NOT RUN"; exit 3; }
say "gate OK on GPU $G"
$P/tools/serve_vllm.sh $G $PORT $QAT gemma-4-31b --max-num-seqs 64 --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 | tee -a $LOG
for i in $(seq 1 180); do curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null && break; sleep 10; done
curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null || { say "server not ready"; systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop; exit 4; }
grep -m1 "non-default args" $P/logs/vllm/g${G}_${PORT}.log >> $LOG
cli() { ( cd $P/release/transcriptlab && TMPDIR=$P/tmp TRANSCRIPTLAB_ROOT=$P PYTHONPATH=src NAME=tlmask QN=VLLM:Worker_D$G MEM=40G CORES=116-117 $LIM $PYA -m transcriptlab "$@" ); }
ARGS="--base http://127.0.0.1:$PORT/v1 --model gemma-4-31b --tokenizer $QAT --pool A1 --arms P0,P1,P6,P8a --corpus $MASK/contexts/P-swebench-31b-S1-v1/manifest.json --meta $META --out $OUT --python $PYG"
say "CLI run start"; cli run $ARGS >> $LOG 2>&1; say "CLI run exited rc=$?; resume pass"
cli run $ARGS >> $LOG 2>&1; say "resume pass rc=$?; gen lines $(wc -l < $OUT/gen.jsonl)"
systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop
cli report $OUT --python $PYG >> $LOG 2>&1; say "report rc=$?"
( cd $P && TMPDIR=$P/tmp NAME=v211ana CORES=116-117 MEM=8G $LIM $PYG experiments/contagion/scripts/analyze_v211_masked.py --cli_gen $OUT/gen.jsonl --out $P/experiments/contagion/out/confirmatory/v211_masked_analysis.json >> $LOG 2>&1 )
say "v211 analysis done: $(grep -o '"verdict": "[^"]*"' $P/experiments/contagion/out/confirmatory/v211_masked_analysis.json)"
