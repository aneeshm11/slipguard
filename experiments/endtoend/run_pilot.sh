#!/bin/bash
# Workstream E — end-to-end pilot launcher (31B plan; also used for the 12B pilot via env overrides) (official swegemma harness + no-nudge client, baseline vs full fixes).
# usage: bash run_pilot.sh <backend_v1_url> [served_name] [tag] [task_file] [proxy_port] [per_run_concurrency]
#   e.g. bash run_pilot.sh http://127.0.0.1:8302/v1 gemma-4-31b p31a
#   two servers (each runs ALL four conditions on half the tasks -> no server x condition confound):
#        bash run_pilot.sh http://127.0.0.1:8300/v1 gemma-4-31b p31a_s0 configs/pilot_tasks_half0.txt 8420 2
#        bash run_pilot.sh http://127.0.0.1:8302/v1 gemma-4-31b p31a_s1 configs/pilot_tasks_half1.txt 8421 2
# Starts ONE proxy (port 8420) and 4 runs concurrently, 4 sandboxes each (16 total), same task order in every run:
#   H-<cfg> : official harness (ADK, nudges, ToolErrorPlugin) via proxy cfg <cfg>   (default cfgs: base fullp)
#   C-<cfg> : no-nudge ReAct client via proxy cfg <cfg>
#   NOTE: the exploratory pilots p12a/p4a were launched with cfgs "base full" where full = full_order (order+quar+ipd)
# Every process goes through tools/limited.sh (masked title, 50 GB cap, pinned cores). Stop with:
#   systemctl --user stop $(systemctl --user list-units --type=scope --no-legend 'ap-e2e-p31*' | awk '{print $1}')
set -euo pipefail
BACKEND=${1:?backend url}; SERVED=${2:-gemma-4-31b}; TAG=${3:-p31a}; TASKS=${4:-configs/pilot_tasks.txt}; PORT=${5:-8420}; CONC=${6:-4}
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; L=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh
PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
# env overrides: MODEL_DIR, SUB, PROXY_CONC, MASKG (mask tag follows the GPU of the backend server)
MODEL_DIR=${MODEL_DIR:-${TRANSCRIPTLAB_MODELS:-models}/gemma-4-31b-it-qat-w4a16-ct}
SUB=${SUB:-subs/sample_noadapter}; PROXY_CONC=${PROXY_CONC:-32}
case "$BACKEND" in *:8300*) G=0;; *:8301*|*:8311*) G=1;; *:8302*) G=2;; *:8303*|*:8313*) G=3;; *) G=0;; esac
G=${MASKG:-$G}
cd $E
mkdir -p tmp_runs logs/proxy_$TAG runs
export E2E_TMP=$E/tmp_runs TMPDIR=$E/tmp_runs HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf HF_HUB_OFFLINE=1
if ! curl -s -m 3 http://127.0.0.1:$PORT/health >/dev/null; then
  QN=VLLM:Worker_D$G NAME=e2e-${TAG}-proxy CORES=140-149 nohup $L $PY proxy/e2e_proxy.py --port $PORT --backend $BACKEND \
     --served $SERVED --model-dir $MODEL_DIR \
     --logdir $E/logs/proxy_$TAG --max-backend-conc $PROXY_CONC --call-timeout ${CALL_TIMEOUT:-3600} ${SEED_SALT:+--seed-salt $SEED_SALT} > logs/proxy_$TAG.out 2>&1 &
  for i in $(seq 1 90); do curl -s -m 2 http://127.0.0.1:$PORT/health >/dev/null && break; sleep 2; done
fi
curl -s -m 3 http://127.0.0.1:$PORT/health >/dev/null || { echo "proxy did not start"; exit 1; }
T=@$TASKS
for c in ${ARMS:-base fullp}; do   # ARMS env: proxy cfgs to run (pre-registered: base fullp)
  QN=VLLM:Worker_D$G NAME=e2e-${TAG}-H$c CORES=140-149 nohup $L $PY harness/run_harness.py --cfg $c --proxy http://127.0.0.1:$PORT \
     --tasks $T --out runs/${TAG}_H_$c --sub $SUB --concurrency $CONC > logs/${TAG}_H_$c.out 2>&1 &
  QN=VLLM:Worker_D$G NAME=e2e-${TAG}-C$c CORES=140-149 nohup $L $PY client/nonudge_client.py --cfg $c --proxy http://127.0.0.1:$PORT \
     --tasks $T --out runs/${TAG}_C_$c --sub $SUB --concurrency $CONC > logs/${TAG}_C_$c.out 2>&1 &
done
sleep 3
systemctl --user list-units --type=scope --no-legend "ap-e2e-${TAG}*" | awk '{print $1}'
echo "analysis: $PY analysis/analyze.py --runs runs/${TAG}_H_base runs/${TAG}_H_full runs/${TAG}_C_base runs/${TAG}_C_full \\"
echo "          --proxy-logs logs/proxy_$TAG --pairs 0:1 2:3 0:2 --out analysis/${TAG}.json"
