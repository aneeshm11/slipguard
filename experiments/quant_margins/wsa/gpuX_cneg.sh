#!/bin/bash
# Candidate C hard negatives (postopen, nlclose) on calib valid items, HF QAT-ct, on GPU $1 (PI-approved window).
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
G=$1
until [ "$(nvidia-smi -i $G --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 10; done
CUDA_VISIBLE_DEVICES=$G ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python hf_extract.py --arm qatct --cneg_only --no_resid \
  --items data/items_calib_valid.jsonl --out out/hf_qatct_cneg_calib.pt > logs/hf_qatct_cneg_calib.log 2>&1
echo "[$(date -u +%H:%M:%S)] exit $? ; GPU$G memory $(nvidia-smi -i $G --query-gpu=memory.used --format=csv,noheader,nounits) MiB"
