#!/bin/bash
# GPU3: candidate C calib-only behaviour gate (calib calls 101-200; CANDIDATE_C.md). If PASS: B_/C_ held-out steps follow
# (offline held-out evaluation on CPU, G5 validation, G4 on the 200 fresh held-out calls) on the same server.
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; B=http://127.0.0.1:8304/v1
ts() { date -u +%H:%M:%S; }
until [ "$(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 5; done
$P/tools/serve_vllm.sh 3 8304 $P/models/gemma-4-31b-it-qat-w4a16-ct gemma-4-31b --gpu-memory-utilization 0.92 --max-num-seqs 16 \
  --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' --enable-lora --max-lora-rank 256 --max-loras 4 \
  --lora-modules smoke_zero=$PWD/adapters/smoke_zero repairC=$PWD/adapters/repairC
for i in $(seq 1 120); do curl -s -m 3 $B/models | grep -q repairC && break; sleep 5; done
echo "[$(ts)] C gate server up"
$PY byte_identity.py --base $B --models gemma-4-31b,smoke_zero,repairC --items data/items_calib_valid.jsonl --split calib --skip 100 --limit 100 --conc 4 \
   --out out/byte_identity_repairC_calib.json > logs/byte_repairC_calib.log 2>&1
PASS=$($PY -c "
import json; s=json.load(open('out/byte_identity_repairC_calib.json'))['summary']['repairC']
print(int(s['byte_identical_to_base'] >= 0.95 and s['valid_rate'] >= s['base_valid_rate']))")
echo "[$(ts)] C calib gate: $(tr -d '\n ' < logs/byte_repairC_calib.log | grep -o '"smoke_zero":{[^}]*}\|"repairC":{[^}]*}' | tr '\n' ' ') PASS=$PASS"
if [ "$PASS" = "1" ]; then
  touch C_CALIB_GATE_PASSED
  QN=VLLM:Worker_D3 $PY repair_memit.py --output_span la_only --eval_split heldout --lams 1000 --rhos 0 --alphas 1.0 --target_modes la_rel_dq_onesided --p_min 0 \
     --save_adapter adapters/repairC_eval --out out/repairC_heldout_final.json > logs/repairC_heldout.log 2>&1
  echo "[$(ts)] C held-out offline evaluation done"
  $PY lora_validate.py --base $B --model gemma-4-31b --adapter repairC --pred adapters/repairC_eval/offline_predictions.json --out out/lora_validate_repairC.json > logs/lora_validate_repairC.log 2>&1
  echo "[$(ts)] C G5: $(tr -d '\n ' < logs/lora_validate_repairC.log | head -c 500)"
  $PY byte_identity.py --base $B --models gemma-4-31b,smoke_zero,repairC --items data/items_heldout_g4_fresh.jsonl --split heldout --limit 200 --conc 4 \
     --out out/byte_identity_repairC_heldout_fresh.json > logs/byte_repairC_heldout.log 2>&1
  echo "[$(ts)] C held-out G4 (fresh 200): $(tr -d '\n ' < logs/byte_repairC_heldout.log | grep -o '"smoke_zero":{[^}]*}\|"repairC":{[^}]*}' | tr '\n' ' ')"
fi
echo "[$(ts)] C gate script finished (server left running)"
