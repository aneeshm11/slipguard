#!/bin/bash
# Workstream X benchmark extension: weight downloads into ${TRANSCRIPTLAB_MODELS:-models} (user-approved location).
# Run under tools/limited.sh. Only the files vLLM needs (no duplicate 'original/' / 'metal/' / mistral-consolidated copies).
export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1 HF_TOKEN_PATH=$HOME/.cache/huggingface/token
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE
M=${TRANSCRIPTLAB_MODELS:-models}; HF=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf
dl() { r=$1; shift; d=$M/$(basename $r)
  $HF download $r --local-dir $d --max-workers 4 "$@" > /dev/null 2>&1 && echo "OK $r $(du -sh $d | cut -f1) $(date -u +%H:%M)" || echo "FAIL $r $(date -u +%H:%M)"; }
dl openai/gpt-oss-20b --exclude "original/*" "metal/*"
dl mistralai/Devstral-Small-2-24B-Instruct-2512 --exclude "consolidated*"
dl Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8
echo ALL_DONE $(date -u +%H:%M)
