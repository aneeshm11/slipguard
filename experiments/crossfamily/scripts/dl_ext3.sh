#!/bin/bash
# Devstral-Small-2: also fetch the mistral-format consolidated weights (vLLM's recommended mistral config/load format;
# the HF-format text_config 'ministral3' has no architectures entry that vLLM 0.19.1's Mistral3 wrapper resolves).
export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE
M=${TRANSCRIPTLAB_MODELS:-models}; HF=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf
r=mistralai/Devstral-Small-2-24B-Instruct-2512; d=$M/Devstral-Small-2-24B-Instruct-2512
$HF download $r --local-dir $d --max-workers 4 --include "consolidated*" > /dev/null 2>&1 && echo "OK $r consolidated $(du -sh $d | cut -f1) $(date -u +%H:%M)" || echo "FAIL $r $(date -u +%H:%M)"
