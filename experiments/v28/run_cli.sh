#!/bin/bash
# PREREG_v2.8_cli runner (PI). usage: experiments/v28/run_cli.sh   (GPU6, user-approved 2026-11-06 ~17:25 UTC)
# Gate: < 2 GB used and 0 compute apps on GPU6 (user rule). Server :8376 on cores 112-115; CLI on cores 116-117.
set -u
G=6; PORT=8376; P=${TRANSCRIPTLAB_ROOT:-.}; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct
OUT=$P/experiments/transcriptlab_cli/run_v28; LOG=$P/experiments/v28/run_cli.log; LIM=$P/tools/limited.sh
PYG=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOG; }
used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $G | tr -d ' ')
uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $G | tr -d ' ')
apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
{ [ "$used" -lt 2048 ] && [ "$apps" -eq 0 ]; } || { say "GATE FAILED on GPU $G (used $used, apps $apps)"; exit 3; }
say "gate OK on GPU $G"
VCORES=112-115 $P/tools/serve_vllm.sh $G $PORT $QAT gemma-4-31b --max-num-seqs 64 --enable-auto-tool-choice \
  --tool-call-parser gemma4 --reasoning-parser gemma4 | tee -a $LOG
for i in $(seq 1 180); do curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null && break; sleep 10; done
curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null || { say "server not ready"; systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop; exit 4; }
grep -m1 "non-default args" $P/logs/vllm/g${G}_${PORT}.log >> $LOG
cli() { ( cd $P/release/transcriptlab && TMPDIR=$P/tmp TRANSCRIPTLAB_ROOT=$P PYTHONPATH=src NAME=tlcli QN=VLLM:Worker_D$G MEM=40G CORES=116-117 \
          $LIM $PYA -m transcriptlab "$@" ); }
say "CLI run start"
cli run --base http://127.0.0.1:$PORT/v1 --model gemma-4-31b --tokenizer $QAT --pool A1 --arms P0,P1,P6,P8a --out $OUT --python $PYG >> $LOG 2>&1
say "CLI run exited rc=$?; resume pass"
cli run --base http://127.0.0.1:$PORT/v1 --model gemma-4-31b --tokenizer $QAT --pool A1 --arms P0,P1,P6,P8a --out $OUT --python $PYG >> $LOG 2>&1
say "resume pass exited rc=$?; gen lines $(wc -l < $OUT/gen.jsonl)"
systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop
cli report $OUT --python $PYG >> $LOG 2>&1; say "CLI report rc=$?"
# frozen v2.8 analysis, run once
( cd $P && TMPDIR=$P/tmp NAME=v28ana CORES=116-117 MEM=8G $LIM $PYG experiments/contagion/scripts/analyze_v28_cli.py \
    --cli_gen $OUT/gen.jsonl --out $P/experiments/contagion/out/confirmatory/v28_cli_analysis.json >> $LOG 2>&1 )
say "v28 analysis done: $(grep -o '"verdict": "[^"]*"' $P/experiments/contagion/out/confirmatory/v28_cli_analysis.json)"
