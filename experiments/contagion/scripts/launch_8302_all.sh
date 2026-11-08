#!/bin/bash
# Resume after the 18:18 HOLD (user approved the moved data path): v2.1 remainder, then S, then H, sequentially on one server
# via scripts/with_paths.py (never more than one A runner on the server). usage: launch_8302_all.sh <port> <gpu>
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion
PORT=${1:-8302}; GPU=${2:-2}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LIM=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh
echo "== resume $(date -u +%H:%M:%S) on :$PORT after the HOLD (user approved the moved path)" >> logs/ctg-31b-v21.log
NAME=ctg-31b-v21 QN=VLLM:Worker_D$GPU MEM=30G $LIM $PY scripts/with_paths.py scripts/run_cond.py --cond OFF --plan data/plan_v21_off.jsonl --out out/main/r31b_v21off.jsonl \
  --blind --conc 24 --base http://127.0.0.1:$PORT/v1 --model gemma-4-31b >> logs/ctg-31b-v21.log 2>&1
echo "== resume $(date -u +%H:%M:%S) on :$PORT after the HOLD" >> logs/ctg-31b-v22S.log
NAME=ctg-31b-v22S QN=VLLM:Worker_D$GPU MEM=30G $LIM $PY scripts/with_paths.py scripts/run_cond.py --cond S --plan data/plan_v22_S.jsonl --out out/main/r31b_v22S.jsonl \
  --blind --conc 24 --base http://127.0.0.1:$PORT/v1 --model gemma-4-31b >> logs/ctg-31b-v22S.log 2>&1
NAME=ctg-31b-v22H QN=VLLM:Worker_D$GPU MEM=30G $LIM $PY scripts/with_paths.py scripts/run_cond.py --cond H --plan data/plan_v22_H.jsonl --out out/main/r31b_v22H.jsonl \
  --blind --conc 24 --base http://127.0.0.1:$PORT/v1 --model gemma-4-31b >> logs/ctg-31b-v22H.log 2>&1
echo "chain done $(date -u +%H:%M:%S)" >> logs/ctg-31b-8302chain.log
