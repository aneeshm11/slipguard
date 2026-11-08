#!/bin/bash
# GPU2 window (PI-approved; HARD STOP 15:50 UTC): candidate B's in-string line-end hard negatives, QAT-ct, calib valid items only.
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
END=$(date -u -d '2026-11-05 15:48:00' +%s); LEFT=$(( END - $(date -u +%s) ))
[ $LEFT -lt 300 ] && { echo "window too short ($LEFT s)"; exit 1; }
until [ "$(nvidia-smi -i 2 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 5; [ $(date -u +%s) -gt $END ] && exit 1; done
CUDA_VISIBLE_DEVICES=2 timeout $(( END - $(date -u +%s) )) ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python hf_extract.py --arm qatct --lineend_only --no_resid \
  --items data/items_calib_valid.jsonl --out out/hf_qatct_lineend_calib.pt > logs/hf_qatct_lineend_calib.log 2>&1
echo "[$(date -u +%H:%M:%S)] exit $? ; GPU2 memory now $(nvidia-smi -i 2 --query-gpu=memory.used --format=csv,noheader,nounits) MiB"
