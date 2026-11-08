#!/bin/bash
# Closed-loop branch-mode test: test proxy (replay plan, mock backend) + official harness, cfgs base and fullp.
# usage: bash tests/run_branch_test.sh <plan.json> <mock_port> <proxy_port> <model_dir> <served> <sub_dir> <outdir>
set -euo pipefail
PLAN=$1; MPORT=$2; PPORT=$3; MD=$4; SERVED=$5; SUB=$6; OUT=$7
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
cd $E
mkdir -p $OUT
export TMPDIR=$E/tmp HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1
QN=VLLM:Worker_D1 NAME=e2e-bproxy CORES=140-149 nohup $L $PY $E/proxy/e2e_proxy.py --port $PPORT \
  --backend http://127.0.0.1:$MPORT/v1 --served $SERVED --model-dir $MD --logdir $OUT/proxy --replay-plan $PLAN \
  --max-backend-conc 4 > $OUT/proxy.out 2>&1 &
for i in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:$PPORT/health >/dev/null && break; sleep 2; done
curl -s -m 2 http://127.0.0.1:$PPORT/health >/dev/null || { echo "proxy did not start"; exit 1; }
export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs
for c in ${ARMS:-base fullp}; do
  QN=VLLM:Worker_D1 NAME=e2e-btest-$c CORES=140-149 nohup $L $PY $E/harness/run_harness.py --cfg $c \
    --proxy http://127.0.0.1:$PPORT --tasks @${PLAN%.json}.tasks.txt --out $OUT/bt_$c --sub $SUB --concurrency 1 \
    > $OUT/bt_$c.out 2>&1 &
done
sleep 2
echo launched
