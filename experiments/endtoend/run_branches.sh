#!/bin/bash
# Branch-at-onset campaign (closed loop): ONE replay proxy + four official-harness arms on the plan's tasks.
# usage: bash run_branches.sh <plan.json> <backend_v1_url> <served> <model_dir> <sub_dir_40calls> <tag> <proxy_port> <per_arm_conc>
#   arms (env ARMS, default "base quar ipd fullp"); each arm: runs/<tag>_<arm>, its own containers (label e2e_run)
# Every replayed request is fidelity-checked (logs/proxy_<tag>/proxy_<arm>.jsonl: replay.fidelity); requests after the
# onset are generated live with common per-request seeds (sha1(branch_id:i)) shared by the four arms.
set -euo pipefail
PLAN=$1; BACKEND=$2; SERVED=$3; MD=$4; SUB=$5; TAG=$6; PORT=$7; CONC=${8:-1}
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
case "$BACKEND" in *:8300*) G=0;; *:8301*|*:8311*) G=1;; *:8302*) G=2;; *:8303*|*:8313*) G=3;; *) G=0;; esac
cd $E
mkdir -p $E/tmp_runs $E/logs/proxy_$TAG $E/runs
export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1
QN=VLLM:Worker_D$G NAME=e2e-${TAG}-proxy CORES=140-149 nohup $L $PY $E/proxy/e2e_proxy.py --port $PORT --backend $BACKEND \
   --served $SERVED --model-dir $MD --logdir $E/logs/proxy_$TAG --replay-plan $PLAN --max-backend-conc ${PROXY_CONC:-32} --call-timeout ${CALL_TIMEOUT:-3600} \
   > $E/logs/proxy_$TAG.out 2>&1 &
for i in $(seq 1 90); do curl -s -m 2 http://127.0.0.1:$PORT/health >/dev/null && break; sleep 2; done
curl -s -m 2 http://127.0.0.1:$PORT/health >/dev/null || { echo "proxy did not start"; exit 1; }
for c in ${ARMS:-base quar ipd fullp}; do
  QN=VLLM:Worker_D$G NAME=e2e-${TAG}-$c CORES=140-149 nohup $L $PY $E/harness/run_harness.py --cfg $c \
     --proxy http://127.0.0.1:$PORT --tasks @${PLAN%.json}.tasks.txt --out $E/runs/${TAG}_$c --sub $SUB --concurrency $CONC \
     > $E/logs/${TAG}_$c.out 2>&1 &
done
sleep 3
systemctl --user list-units --type=scope --no-legend "ap-e2e-${TAG}*" | awk '{print $1}'
