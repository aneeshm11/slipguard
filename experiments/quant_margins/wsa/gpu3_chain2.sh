#!/bin/bash
# GPU3, after the main extractions (PI-approved afternoon plan): BOS-correct wikitext reruns (bf16, QAT-ct), then the T1 sweep
# (pausable with PAUSE_SWEEP so the T3 gate server can start as soon as the adapter exists).
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; ts() { date -u +%H:%M:%S; }
while systemctl --user is-active --quiet ap-qmg3chain-433912.scope; do sleep 20; done
until [ "$(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 10; done
for arm in bf16 qatct; do
  CUDA_VISIBLE_DEVICES=3 $PY hf_extract.py --arm $arm --wikitext_only --no_resid --out out/hf_${arm}_wiki.pt > logs/hf_${arm}_wiki.log 2>&1
  echo "[$(ts)] wikitext $arm: $(tail -1 logs/hf_${arm}_wiki.log)"
done
./t1_sweep.sh
