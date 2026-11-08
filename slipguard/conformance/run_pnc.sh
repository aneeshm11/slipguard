#!/bin/bash
# Public-input conformance: every PNC turn through slipguard's targets AND the built-in parsers (C's worker), in every
# vLLM version. Jobs run through a fixed-size queue (-P), one process per core.
# usage: SLIPGUARD_ENVS=<venvs dir> conformance/run_pnc.sh <C's conformance dir> <tokenizer dir> <cases.jsonl> <out dir> [P]
set -u
SUITE=$1; TOK=$2; CASES=$3; OUT=$4; P=${5:-8}
ENVS=${SLIPGUARD_ENVS:?set SLIPGUARD_ENVS to the directory holding the vLLM venvs}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
BIG=100000000   # no stream length cap: every turn is streamed token by token
job() {  # kind spec shard nshards
  kind=$1; spec=$2; s=$3; n=$4
  env=${spec%%+*}; pkg=""; [[ $spec == *+* ]] && pkg=${spec#*+}
  case $spec in env_gemma) v=019;; env_vllm31) v=031;; *) v=$(echo "$pkg" | sed -E 's/vllm-0\.([0-9]+)\..*/0\1/');; esac
  o="$OUT/${kind}__${spec}__$s.jsonl"
  if [ -n "$pkg" ]; then
    export PYTHONPATH=$ENVS/env_xruntime/pkgs/$pkg LD_LIBRARY_PATH=$ENVS/env_xruntime/lib/python3.12/site-packages/nvidia/cu13/lib
  fi
  if [ "$kind" = gg ]; then
    t="gg.vllm$v.server,gg.vllm$v.stream"; [ "$spec" = env_gemma ] && t="$t,gg.completion,gg.extract,gg.repair,gg.stream"
    "$ENVS/$env/bin/python" "$HERE/gg_targets.py" "$CASES" "$o" "$s" "$n" --suite "$SUITE" --tokenizer "$TOK" \
      --targets "$t" --stream-max-chars $BIG --lean 2>"$o.err"
  else
    t="vllm$v.server,vllm$v.stream"; [ -z "$pkg" ] && t="$t,hf513.template,hf517.template,ref"
    (cd "$SUITE" && "$ENVS/$env/bin/python" diff/worker.py "$CASES" "$o" "$s" "$n" --targets "$t" \
      --stream-max-chars $BIG --lean 2>"$o.err")
  fi
  echo "$kind $spec $s/$n done $(date -u +%H:%M:%S)"
}
export -f job; export SUITE TOK CASES OUT ENVS HERE BIG
{
  for s in 0 1 2 3; do echo "gg env_gemma $s 4"; done
  for spec in env_gemma env_vllm31 env_vllm31+vllm-0.24.0 env_vllm31+vllm-0.32.0 env_vllm31+vllm-0.33.0; do
    for s in 0 1; do echo "builtin $spec $s 2"; done
  done
  for spec in env_vllm31 env_vllm31+vllm-0.24.0 env_vllm31+vllm-0.32.0 env_vllm31+vllm-0.33.0; do
    for s in 0 1; do echo "gg $spec $s 2"; done
  done
} | xargs -P "$P" -L 1 bash -c 'job "$@"' _
