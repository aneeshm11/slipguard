#!/bin/bash
# Run slipguard's targets over C's conformance cases in every vLLM env (4 shards each). Dev-time driver.
# usage: conformance/run_all.sh <suite dir> <tokenizer dir> <cases.jsonl> <out dir> [envspec ...]
#   envspec: env_gemma | env_vllm31 | env_vllm31+vllm-0.33.0 | env_vllm31+vllm-0.24.0   (default: all four)
set -u
SUITE=$1; TOK=$2; CASES=$3; OUT=$4; shift 4
SPECS=${@:-env_gemma env_vllm31 env_vllm31+vllm-0.33.0 env_vllm31+vllm-0.24.0}
ENVS=${SLIPGUARD_ENVS:?set SLIPGUARD_ENVS to the directory holding the vLLM venvs}; XR=$ENVS/env_xruntime
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
for spec in $SPECS; do
  env=${spec%%+*}; pkg=""; [[ $spec == *+* ]] && pkg=${spec#*+}
  for s in 0 1 2 3; do
    o="$OUT/$(basename "$CASES" .jsonl)__${spec}__$s.jsonl"
    if [ -n "$pkg" ]; then
      PYTHONPATH=$XR/pkgs/$pkg LD_LIBRARY_PATH=$XR/lib/python3.12/site-packages/nvidia/cu13/lib \
        $ENVS/$env/bin/python "$HERE/gg_targets.py" "$CASES" "$o" $s 4 --suite "$SUITE" --tokenizer "$TOK" --lean 2>"$o.err" &
    else
      $ENVS/$env/bin/python "$HERE/gg_targets.py" "$CASES" "$o" $s 4 --suite "$SUITE" --tokenizer "$TOK" --lean 2>"$o.err" &
    fi
  done
  wait
  echo "$spec done $(date -u +%H:%M:%S)"
done
