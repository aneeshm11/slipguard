#!/bin/bash
# Run benchmarks/perf.py in each vLLM env, one after another, on ONE core (pin with limited.sh CORES=...).
# usage: benchmarks/run_perf.sh <suite dir> <tokenizer dir> <out dir> [timeout_s]
set -u
SUITE=$1; TOK=$2; OUT=$3; TO=${4:-60}
ENVS=${SLIPGUARD_ENVS:?set SLIPGUARD_ENVS to the directory holding the vLLM venvs}; XR=$ENVS/env_xruntime
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
for spec in env_gemma env_vllm31 env_vllm31+vllm-0.33.0; do
  env=${spec%%+*}; pkg=""; [[ $spec == *+* ]] && pkg=${spec#*+}
  o="$OUT/perf_${spec//+/_}.json"
  if [ -n "$pkg" ]; then
    PYTHONPATH=$XR/pkgs/$pkg LD_LIBRARY_PATH=$XR/lib/python3.12/site-packages/nvidia/cu13/lib \
      $ENVS/$env/bin/python "$HERE/perf.py" "$o" --suite "$SUITE" --tokenizer "$TOK" --timeout "$TO" > "$o.log" 2>&1
  else
    $ENVS/$env/bin/python "$HERE/perf.py" "$o" --suite "$SUITE" --tokenizer "$TOK" --timeout "$TO" > "$o.log" 2>&1
  fi
  echo "$spec done $(date -u +%H:%M:%S) rc=$?"
done
