#!/bin/bash
# retry of gpt-oss-20b (the first attempt passed two patterns to one --exclude flag)
export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE
M=${TRANSCRIPTLAB_MODELS:-models}; HF=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf
r=openai/gpt-oss-20b; d=$M/gpt-oss-20b
$HF download $r --local-dir $d --max-workers 4 --exclude "original/*" --exclude "metal/*" > /dev/null 2>&1 && echo "OK $r $(du -sh $d | cut -f1) $(date -u +%H:%M)" || echo "FAIL $r $(date -u +%H:%M)"
