#!/bin/bash
# GPU3 (PI-approved): after the paused sweep releases the GPU, extract wikitext-2 VALIDATION windows for QAT-ct (selection set).
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; ts() { date -u +%H:%M:%S; }
while systemctl --user is-active --quiet ap-qmg3chain2-3925290.scope; do sleep 10; done
until [ "$(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 5; done
CUDA_VISIBLE_DEVICES=3 $PY hf_extract.py --arm qatct --wikitext_only --wikitext_split validation --no_resid --out out/hf_qatct_wikival.pt > logs/hf_qatct_wikival.log 2>&1
echo "[$(ts)] wikival qatct: $(tail -1 logs/hf_qatct_wikival.log)"
