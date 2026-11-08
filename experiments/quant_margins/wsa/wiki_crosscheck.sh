#!/bin/bash
# GPU3 (PI-approved): general-text cross-check (descriptive): wikitext-2 test NLL via endpoint prompt_logprobs for 4 checkpoints.
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
P=${TRANSCRIPTLAB_ROOT:-.}; M=$P/models; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LOGV=$P/logs/vllm/g3_8304.log; B=http://127.0.0.1:8304/v1
OV='{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'
for u in $(systemctl --user list-units --type=scope --no-legend 'ap-vllm-g3-*' | awk '{print $1}'); do systemctl --user stop "$u"; done
for spec in "31b_bf16|$M/gemma-4-31b-it|0.96" "31b_qatct|$M/gemma-4-31b-it-qat-w4a16-ct|0.90" "31b_awq_cyankiwi|$M/community/cyankiwi_gemma-4-31B-it-AWQ-4bit|0.90" "31b_autoround_intel|$M/community/Intel_gemma-4-31B-it-int4-AutoRound|0.90"; do
  IFS='|' read name dir util <<< "$spec"
  until [ "$(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')" -lt 3000 ]; do sleep 5; done
  $P/tools/serve_vllm.sh 3 8304 $dir $name --gpu-memory-utilization $util --max-num-seqs 16 --hf-overrides "$OV" > /dev/null
  for i in $(seq 1 150); do curl -s -m 3 $B/models | grep -q "\"$name\"" && break; sleep 5; done
  $PY wiki_nll_endpoint.py --base $B --model $name --chat_wrap --out out/wiki_nll_chat_$name.json 2>&1 | tail -1
  for u in $(systemctl --user list-units --type=scope --no-legend 'ap-vllm-g3-*' | awk '{print $1}'); do systemctl --user stop "$u"; done
done
echo "[$(date -u +%H:%M:%S)] wiki cross-check finished"
