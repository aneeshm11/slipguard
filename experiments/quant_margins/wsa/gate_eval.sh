#!/bin/bash
# T3 gate on GPU3 (PI-approved slot): vLLM QAT-ct (-ct W4A16 base, text-only) + LoRA adapters on :8304.
# usage: gate_eval.sh <adapter_name>=<adapter_dir> [...]     (first adapter = primary candidate)
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log; B=http://127.0.0.1:8304/v1
ts() { date -u +%H:%M:%S; }
MODS="smoke_zero=$PWD/adapters/smoke_zero smoke_rand=$PWD/adapters/smoke_rand $*"
until [ "$(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 20; done
$P/tools/serve_vllm.sh 3 8304 $P/models/gemma-4-31b-it-qat-w4a16-ct gemma-4-31b --gpu-memory-utilization 0.92 --max-num-seqs 16 \
  --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' --enable-lora --max-lora-rank 256 --max-loras 4 \
  --lora-modules $MODS
for i in $(seq 1 120); do curl -s -m 3 $B/models | grep -q smoke_rand && break; grep -q "Engine core initialization failed\|Traceback" $LOGV && break; sleep 5; done
echo "[$(ts)] server up: $(curl -s -m 3 $B/models | grep -o '"id":"[^"]*"' | tr '\n' ' ')"
$PY lora_smoke.py $B > logs/lora_smoke.log 2>&1; echo "[$(ts)] smoke: $(tail -1 logs/lora_smoke.log)"
for kv in "$@"; do
  name=${kv%%=*}; dir=${kv#*=}
  [ -f $dir/offline_predictions.json ] && $PY lora_validate.py --base $B --model gemma-4-31b --adapter $name --pred $dir/offline_predictions.json --out out/lora_validate_$name.json > logs/lora_validate_$name.log 2>&1 && echo "[$(ts)] validate $name: $(tr -d '\n ' < logs/lora_validate_$name.log | head -c 600)"
done
$PY audit.py --base $B --model gemma-4-31b --out out/audit_qatct_vllm_heldout.json --split heldout --kinds close,slip,protected > logs/audit_qatct.log 2>&1; echo "[$(ts)] audit base done"
for kv in "$@"; do
  name=${kv%%=*}
  $PY audit.py --base $B --model $name --out out/audit_${name}_heldout.json --split heldout --kinds close,slip,protected > logs/audit_$name.log 2>&1; echo "[$(ts)] audit $name done"
  $PY byte_identity.py --base $B --models gemma-4-31b,$name --out out/byte_identity_$name.json --limit 300 > logs/byte_$name.log 2>&1; echo "[$(ts)] byte identity $name: $(grep -o '"byte_identical_to_base": [0-9.]*' logs/byte_$name.log)"
done
echo "[$(ts)] gate evaluation finished (server left running)"
