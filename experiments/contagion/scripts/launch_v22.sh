#!/bin/bash
# PREREG_v2.2 on one server, sequentially (never more than one A runner on the server): arm set S (1,200 jobs), then arm set H
# (600 jobs). Optional 3rd step EXPLORATORY SON (flag ON + closed thought; P0/P1, 600 jobs) only if RUN_SON=1.
# usage: launch_v22.sh <port> <gpu>   (run with nohup ... &)
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion
PORT=${1:-8302}; GPU=${2:-2}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LIM=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh
NAME=ctg-31b-v22S QN=VLLM:Worker_D$GPU MEM=30G $LIM $PY scripts/with_paths.py scripts/run_cond.py --cond S --plan data/plan_v22_S.jsonl --out out/main/r31b_v22S.jsonl \
  --blind --conc 24 --base http://127.0.0.1:$PORT/v1 --model gemma-4-31b >> logs/ctg-31b-v22S.log 2>&1
NAME=ctg-31b-v22H QN=VLLM:Worker_D$GPU MEM=30G $LIM $PY scripts/with_paths.py scripts/run_cond.py --cond H --plan data/plan_v22_H.jsonl --out out/main/r31b_v22H.jsonl \
  --blind --conc 24 --base http://127.0.0.1:$PORT/v1 --model gemma-4-31b >> logs/ctg-31b-v22H.log 2>&1
if [ "${RUN_SON:-0}" = "1" ]; then
  NAME=ctg-31b-v22SON QN=VLLM:Worker_D$GPU MEM=30G $LIM $PY scripts/with_paths.py scripts/run_cond.py --cond SON --plan data/plan_v22_SON_explor.jsonl --out out/main/r31b_v22SON_explor.jsonl \
    --blind --conc 24 --base http://127.0.0.1:$PORT/v1 --model gemma-4-31b >> logs/ctg-31b-v22SON.log 2>&1
fi
echo "launch_v22 chain done $(date -u +%H:%M:%S)" >> logs/ctg-31b-v22chain.log
