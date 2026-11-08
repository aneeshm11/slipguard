#!/bin/bash
# Workstream X GPU chain for one model (run under tools/limited.sh):
#   primary tier (battery x 6 arms + census, interleaved), a retry pass, then the held-out tier (+ retry pass).
# usage: run_chain.sh <model_key> <base_url> <served_name> [conc=24] [ctx_conc=4] [primary_only=0]
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily
PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
MK=$1; BASE=$2; SERVED=$3; C=${4:-24}; CC=${5:-4}; PO=${6:-0}
for pass in 1 2; do
  $PY scripts/discovery/run_qwen.py --prompts data/prompts_$MK.jsonl --out out/gen_$MK.jsonl --mk $MK --base $BASE \
      --served $SERVED --conc $C --ctx_conc $CC
done
[ "$PO" = "1" ] && exit 0
for pass in 1 2; do
  $PY scripts/discovery/run_qwen.py --prompts data/prompts_${MK}_heldout.jsonl --out out/gen_${MK}_heldout.jsonl --mk $MK \
      --base $BASE --served $SERVED --conc $C --ctx_conc $CC --sets heldout
done
