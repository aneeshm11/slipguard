#!/bin/bash
X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
POOLS=${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion/data/confirmatory/pools
$PY $X/scripts/v2_frozen/v2_prepare.py $POOLS $X/out/v2 qwen3-32b 6 && cp $X/out/v2/v2_prepare_manifest.json $X/out/v2/v2_prepare_manifest_32b.json
mkdir -p $X/out/ext
$PY $X/scripts/ext_frozen/ext_prepare.py $POOLS $X/out/ext gpt-oss-20b,qwen3-coder-30b,devstral-24b,qwen3.8-27b 6
echo PREP_REST_DONE $(date -u +%H:%M)
