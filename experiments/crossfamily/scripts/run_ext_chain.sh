#!/bin/bash
# Extension models (prereg_ext.md): frozen scripts/ext_frozen/run_ext.py, pool A1 (battery) to completion before pool B1
# (census), two passes each (pass 2 retries failed jobs). Order only (logged pre-data in PREREG_DEVIATIONS.md); seeds are
# md5(context_id). usage: run_ext_chain.sh <mk> <base_url> <served> [conc=24] [ctx_conc=4] [limit_ctx=0 -> full]
X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
MK=$1; BASE=$2; SERVED=$3; C=${4:-24}; CC=${5:-4}; LIM=${6:-0}
export TIKTOKEN_RS_CACHE_DIR=$X/data/tiktoken_cache HF_HUB_OFFLINE=1
if [ "$LIM" != "0" ]; then
  echo "=== pilot extA1 limit_ctx $LIM $(date -u +%H:%M:%S)"
  $PY $X/scripts/ext_frozen/run_ext.py --prompts $X/out/ext/prompts_$MK.jsonl --out $X/out/ext/gen_$MK.jsonl --mk $MK \
      --base $BASE --served $SERVED --conc $C --ctx_conc $CC --sets extA1 --limit_ctx $LIM
  exit $?
fi
for S in extA1 extB1; do
  for pass in 1 2; do
    echo "=== set $S pass $pass $(date -u +%H:%M:%S)"
    $PY $X/scripts/ext_frozen/run_ext.py --prompts $X/out/ext/prompts_$MK.jsonl --out $X/out/ext/gen_$MK.jsonl --mk $MK \
        --base $BASE --served $SERVED --conc $C --ctx_conc $CC --sets $S
  done
done
