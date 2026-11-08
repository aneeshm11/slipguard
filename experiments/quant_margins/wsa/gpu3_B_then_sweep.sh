#!/bin/bash
# GPU3: noise-floor run -> candidate B calib-only behaviour gate (100 calib calls) -> [if PASS] B's fresh held-out G4 (200 calls)
# on the same server -> T1 sweep. (CANDIDATE_B.md; SWEEP_PLAN amended.)
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; B=http://127.0.0.1:8304/v1; LOGV=$P/logs/vllm/g3_8304.log
ts() { date -u +%H:%M:%S; }
while systemctl --user is-active --quiet ap-qmbyte2-576400.scope; do sleep 15; done
echo "[$(ts)] noise-floor run finished"
until [ -f adapters/repairB/adapter_model.safetensors ]; do sleep 15; done
for u in $(systemctl --user list-units --type=scope --no-legend 'ap-vllm-g3-*' | awk '{print $1}'); do systemctl --user stop "$u"; done
until [ "$(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 5; done
$P/tools/serve_vllm.sh 3 8304 $P/models/gemma-4-31b-it-qat-w4a16-ct gemma-4-31b --gpu-memory-utilization 0.92 --max-num-seqs 16 \
  --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' --enable-lora --max-lora-rank 256 --max-loras 4 \
  --lora-modules smoke_zero=$PWD/adapters/smoke_zero repairB=$PWD/adapters/repairB
for i in $(seq 1 120); do curl -s -m 3 $B/models | grep -q repairB && break; sleep 5; done
echo "[$(ts)] B gate server up"
$PY byte_identity.py --base $B --models gemma-4-31b,smoke_zero,repairB --items data/items_calib_valid.jsonl --split calib --limit 100 --conc 4 \
   --out out/byte_identity_repairB_calib.json > logs/byte_repairB_calib.log 2>&1
PASS=$($PY -c "
import json; s=json.load(open('out/byte_identity_repairB_calib.json'))['summary']['repairB']
print(int(s['byte_identical_to_base'] >= 0.95 and s['valid_rate'] >= s['base_valid_rate']))")
echo "[$(ts)] B calib gate: $(tr -d '\n ' < logs/byte_repairB_calib.log | grep -o '"repairB":{[^}]*}') PASS=$PASS"
if [ "$PASS" = "1" ]; then
  touch B_CALIB_GATE_PASSED
  $PY byte_identity.py --base $B --models gemma-4-31b,smoke_zero,repairB --items data/items_heldout_g4_fresh.jsonl --split heldout --limit 200 --conc 4 \
     --out out/byte_identity_repairB_heldout_fresh.json > logs/byte_repairB_heldout.log 2>&1
  echo "[$(ts)] B held-out G4 (fresh 200): $(tr -d '\n ' < logs/byte_repairB_heldout.log | grep -o '"repairB":{[^}]*}')"
fi
for u in $(systemctl --user list-units --type=scope --no-legend 'ap-vllm-g3-*' | awk '{print $1}'); do systemctl --user stop "$u"; done
echo "[$(ts)] starting T1 sweep"
G=3 PORT=8304 ./t1_sweep.sh
