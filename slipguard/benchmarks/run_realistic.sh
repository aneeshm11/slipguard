#!/bin/bash
# Realistic-traffic parser cost: 4 vLLM versions x {builtin, slipguard}, each process on its OWN core (limited.sh).
# usage: benchmarks/run_realistic.sh <PNC dir> <tokenizer dir> <suite dir> <out dir> [stride]
set -u
PNC=$1; TOK=$2; SUITE=$3; OUT=$4; STRIDE=${5:-1}
ENVS=${SLIPGUARD_ENVS:?set SLIPGUARD_ENVS}; XR=$ENVS/env_xruntime; L=${LIMITED:?set LIMITED to tools/limited.sh}
HERE=$(cd "$(dirname "$0")" && pwd)
CORES_LIST=(${REALISTIC_CORES:-136 137 138 139 171 172 173 174})
mkdir -p "$OUT"
i=0
for spec in env_gemma env_vllm31 env_vllm31+vllm-0.32.0 env_vllm31+vllm-0.33.0; do
  env=${spec%%+*}; pkg=""; [[ $spec == *+* ]] && pkg=${spec#*+}
  for impl in builtin slipguard; do
    core=${CORES_LIST[$i]}; i=$((i+1))
    o="$OUT/${spec//+/_}__$impl.jsonl"
    if [ -n "$pkg" ]; then
      EXTRA="PYTHONPATH=$XR/pkgs/$pkg LD_LIBRARY_PATH=$XR/lib/python3.12/site-packages/nvidia/cu13/lib"
    else
      EXTRA="PYTHONPATH="
    fi
    NAME=librt$i CORES=$core $L env $EXTRA $ENVS/$env/bin/python "$HERE/realistic.py" --pnc "$PNC" --tokenizer "$TOK" \
      --suite "$SUITE" --impl $impl --out "$o" --stride $STRIDE > "$o.log" 2>&1 &
  done
done
wait
echo "all done $(date -u +%H:%M:%S)"
