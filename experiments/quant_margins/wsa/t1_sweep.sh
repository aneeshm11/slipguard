#!/bin/bash
# T1 checkpoint sweep on GPU3 (run only with PI approval): each checkpoint served by vLLM 0.19.1 (text-only) on :8304,
# endpoint audit (audit.py) on the held-out PNC items with prompt+completion <= 16.4k tokens (fits every server), then stopped.
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
G=${G:-3}; PORT=${PORT:-8304}; LOGV=$P/logs/vllm/g${G}_${PORT}.log; B=http://127.0.0.1:$PORT/v1
ts() { date -u +%H:%M:%S; }
OV='{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'
LIST=${LIST:-"31b_bf16|$M/gemma-4-31b-it|0.96|1
31b_qatct|$M/gemma-4-31b-it-qat-w4a16-ct|0.90|3
31b_ptq_q40|$P/experiments/quant_margins/models_tmp/gemma-4-31b-it-fakeq4_0|0.96|1
31b_qatunq|$M/gemma-4-31b-it-qat-q4_0-unquantized|0.96|1
31b_awq_quanttrio|$M/community/QuantTrio_gemma-4-31B-it-AWQ|0.90|3
31b_awq_cyankiwi|$M/community/cyankiwi_gemma-4-31B-it-AWQ-4bit|0.90|3
31b_autoround_intel|$M/community/Intel_gemma-4-31B-it-int4-AutoRound|0.90|3
31b_fp8_redhat|$M/community/RedHatAI_gemma-4-31B-it-FP8-dynamic|0.92|2
31b_nvfp4_redhat|$M/community/RedHatAI_gemma-4-31B-it-NVFP4|0.90|3
12b_qatct|$M/gemma-4-12b-it-qat-w4a16-ct|0.90|4
e4b_bf16|$M/gemma-4-e4b-it|0.90|4
e4b_qatct|$M/gemma-4-e4b-it-qat-w4a16-ct|0.90|4"}
echo "$LIST" | while IFS='|' read name dir util conc; do
  [ -z "$name" ] && continue
  [ -f out/audit_sweep_$name.json ] && { echo "[$(ts)] $name already done"; continue; }
  [ -f PAUSE_SWEEP_G$G ] && { echo "[$(ts)] PAUSE_SWEEP_G$G present: sweep paused before $name"; break; }
  [ -f out/audit_sweep_$name.claim ] && { echo "[$(ts)] $name claimed by another GPU"; continue; }
  echo G$G > out/audit_sweep_$name.claim
  until [ "$(nvidia-smi -i $G --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 10; done
  $P/tools/serve_vllm.sh $G $PORT $dir $name --gpu-memory-utilization $util --max-num-seqs 16 --hf-overrides "$OV" > /dev/null
  ok=0
  for i in $(seq 1 150); do curl -s -m 3 $B/models | grep -q "\"$name\"" && { ok=1; break; }; grep -q "Engine core initialization failed\|Traceback" $LOGV && break; sleep 5; done
  cp $LOGV logs/vllm_sweep_${name}_g$G.log
  if [ $ok = 1 ]; then
    kv=$(grep -m1 'GPU KV cache size' $LOGV | grep -oE '[0-9,]+ tokens' | tr -d ', tokens'); cap=$((kv - 600)); [ $cap -gt 32000 ] && cap=32000
    echo "[$(ts)] $name up (KV $kv, cap $cap)"
    $PY audit.py --base $B --model $name --items data/audit_items_16k.jsonl --split heldout --kinds close,slip --max_total $cap --conc ${conc:-2} \
        --out out/audit_sweep_$name.json > logs/audit_sweep_$name.log 2>&1
    echo "[$(ts)] $name audited: $(grep -o '"E_slip_T1": \[[^]]*\]' out/audit_sweep_$name.json | head -1)"
  else
    echo "[$(ts)] $name FAILED to start: $(grep -m2 -E 'Error|error' $LOGV | cut -c1-200)"
  fi
  for u in $(systemctl --user list-units --type=scope --no-legend "ap-vllm-g$G-*" | awk '{print $1}'); do systemctl --user stop "$u"; done
  [ -f out/audit_sweep_$name.json ] || rm -f out/audit_sweep_$name.claim
done
echo "[$(ts)] sweep finished"
