#!/bin/bash
# Qwen3-32B v2: same frozen runner/arguments as run_v2_chain.sh, but pool A1 (battery, X1-X4) before pool B1 (census, X5),
# so the registered battery completes first if GPU time runs short. Order does not affect seeds (md5(context_id)).
X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
for S in v2A1 v2B1; do
  for pass in 1 2; do
    echo "=== set $S pass $pass $(date -u +%H:%M:%S)"
    $PY $X/scripts/v2_frozen/run_qwen.py --prompts $X/out/v2/prompts_qwen3-32b.jsonl --out $X/out/v2/gen_qwen3-32b.jsonl --mk qwen3-32b \
        --base http://127.0.0.1:8320/v1 --served qwen3-32b --conc 24 --ctx_conc 4 --sets $S
  done
done
