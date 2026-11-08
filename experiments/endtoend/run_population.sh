#!/bin/bash
# PREREG_E population runs (a): official harness, arms base + fullp, common per-request seeds within a replicate.
# usage: bash run_population.sh <backend_v1_url> <served> <model_dir> <sub_dir> <tag> <tasks_file> <proxy_port> <per_arm_conc> <seed_salt>
#   e.g. 31B replicate 1, server half 0:
#   bash run_population.sh http://127.0.0.1:8300/v1 gemma-4-31b ${TRANSCRIPTLAB_MODELS:-models}/gemma-4-31b-it-qat-w4a16-ct \
#        subs/sample_noadapter pop31r1s0 configs/eligible_113_half0.txt 8450 4 pop31r1
#   (both server halves of a replicate use the SAME seed_salt; each half has its own tag/proxy/logs)
set -euo pipefail
BACKEND=$1; SERVED=$2; MD=$3; SUB=$4; TAG=$5; TASKS=$6; PORT=$7; CONC=$8; SALT=$9
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
case "$BACKEND" in *:8300*) G=0;; *:8301*|*:8311*) G=1;; *:8302*) G=2;; *:8303*|*:8313*) G=3;; *) G=0;; esac
cd $E
mkdir -p $E/tmp_runs $E/logs/proxy_$TAG $E/runs
export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1
QN=VLLM:Worker_D$G NAME=e2e-${TAG}-proxy CORES=140-149 nohup $L $PY $E/proxy/e2e_proxy.py --port $PORT --backend $BACKEND \
   --served $SERVED --model-dir $MD --logdir $E/logs/proxy_$TAG --seed-salt $SALT --max-backend-conc ${PROXY_CONC:-32} --call-timeout ${CALL_TIMEOUT:-3600} \
   > $E/logs/proxy_$TAG.out 2>&1 &
for i in $(seq 1 90); do curl -s -m 2 http://127.0.0.1:$PORT/health >/dev/null && break; sleep 2; done
curl -s -m 2 http://127.0.0.1:$PORT/health >/dev/null || { echo "proxy did not start"; exit 1; }
for c in base fullp; do
  QN=VLLM:Worker_D$G NAME=e2e-${TAG}-$c CORES=140-149 nohup $L $PY $E/harness/run_harness.py --cfg $c \
     --proxy http://127.0.0.1:$PORT --tasks @$TASKS --out $E/runs/${TAG}_H_$c --sub $SUB --concurrency $CONC \
     > $E/logs/${TAG}_H_$c.out 2>&1 &
done
sleep 3
systemctl --user list-units --type=scope --no-legend "ap-e2e-${TAG}*" | awk '{print $1}'
