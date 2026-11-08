#!/bin/bash
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily
PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
for mk in qwen3-32b qwen3-8b qwen3.5-9b; do $PY scripts/prep_prompts.py $mk 0 300 8 --heldout; done
