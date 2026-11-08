#!/bin/bash
# PREREG_v2 run chain for one Qwen model (frozen runner; two passes = retry of transient errors). Run under limited.sh.
# usage: run_v2_chain.sh <model_key> <base_url> <served_name> [conc=24] [ctx_conc=4]
X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
MK=$1; BASE=$2; SERVED=$3; C=${4:-24}; CC=${5:-4}
for pass in 1 2; do
  $PY $X/scripts/v2_frozen/run_qwen.py --prompts $X/out/v2/prompts_$MK.jsonl --out $X/out/v2/gen_$MK.jsonl --mk $MK \
      --base $BASE --served $SERVED --conc $C --ctx_conc $CC --sets v2A1,v2B1
done
