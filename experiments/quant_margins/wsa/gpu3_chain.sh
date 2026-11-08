#!/bin/bash
# GPU3 job chain for the weight-space audit/repair (F, 2026-11-05).
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log
ts() { date -u +%H:%M:%S; }
until [ "$(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 30; done
echo "[$(ts)] GPU3 free"
# 1. LoRA smoke test over the W4A16 base
$P/tools/serve_vllm.sh 3 8304 $P/models/gemma-4-31b-it-qat-w4a16-ct gemma-4-31b --gpu-memory-utilization 0.90 --max-num-seqs 16 \
  --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' --enable-lora --max-lora-rank 128 --max-loras 2 \
  --lora-modules smoke_zero=$PWD/adapters/smoke_zero smoke_rand=$PWD/adapters/smoke_rand
for i in $(seq 1 120); do curl -s -m 3 http://127.0.0.1:8304/v1/models | grep -q smoke_rand && break; grep -q "Engine core initialization failed\|Traceback" $LOGV && break; sleep 5; done
echo "[$(ts)] server: $(curl -s -m 3 http://127.0.0.1:8304/v1/models | head -c 300)"
$PY lora_smoke.py http://127.0.0.1:8304/v1 > logs/lora_smoke.log 2>&1; tail -1 logs/lora_smoke.log
cp $LOGV logs/vllm_lora_smoke.log
for u in $(systemctl --user list-units --type=scope --no-legend 'ap-vllm-g3*' | awk '{print $1}'); do systemctl --user stop "$u"; done
until [ "$(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 5; done
# 2-4. HF extractions
for arm in bf16 qatct ptq; do
  echo "[$(ts)] HF extraction $arm"
  CUDA_VISIBLE_DEVICES=3 $PY hf_extract.py --arm $arm --out out/hf_$arm.pt > logs/hf_$arm.log 2>&1
  echo "[$(ts)] HF $arm done: $(tail -1 logs/hf_$arm.log)"
done
