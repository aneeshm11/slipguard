#!/bin/bash
# pre-render all prompts (CPU) for the three Qwen models; run under tools/limited.sh
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily
PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
$PY scripts/prep_prompts.py qwen3-32b 300 300 8
$PY scripts/prep_prompts.py qwen3-8b 600 300 8
$PY scripts/prep_prompts.py qwen3.5-9b 600 300 8
