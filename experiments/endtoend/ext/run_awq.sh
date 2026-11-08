#!/bin/bash
# PREREG_E_awq launcher (PI): AWQ server on GPU6 :8306 (bf16, text-only), then the two halves with PREREG_E's frozen
# run_population.sh / run_chain.sh. Gate: < 2 GB used, 0 compute apps on GPU6.
set -u
G=6; P=${TRANSCRIPTLAB_ROOT:-.}; E=$P/experiments/endtoend; LOG=$E/ext/run_awq.log
AWQ=$P/models/community/cyankiwi_gemma-4-31B-it-AWQ-4bit; QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct
say() { echo "[$(date -u +%H:%M:%S)] $*" >> $LOG; }
used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $G | tr -d ' ')
uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $G | tr -d ' ')
apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
{ [ "$used" -lt 2048 ] && [ "$apps" -eq 0 ]; } || { say "GATE FAILED on GPU $G"; exit 3; }
say "gate OK on GPU $G"
VCORES=112-115 $P/tools/serve_vllm.sh $G 8306 $AWQ gemma-4-31b --dtype bfloat16 --max-num-seqs 64 \
  --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' \
  --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 >> $LOG 2>&1
for i in $(seq 1 180); do curl -s -m 3 http://127.0.0.1:8306/v1/models >/dev/null && break; sleep 10; done
curl -s -m 3 http://127.0.0.1:8306/v1/models >/dev/null || { say "AWQ server not ready"; exit 4; }
grep -m1 "non-default args" $P/logs/vllm/g${G}_8306.log >> $LOG; grep -o "dtype=torch.bfloat16" $P/logs/vllm/g${G}_8306.log | head -1 >> $LOG
cd $E
bash run_population.sh http://127.0.0.1:8306/v1 gemma-4-31b $QAT subs/sample_noadapter popAWQr1s0 configs/eligible_113_half0.txt 8520 3 popAWQr1 >> $LOG 2>&1
say "popAWQr1s0 launched; chaining popAWQr1s1"
N0=$(wc -w < configs/eligible_113_half0.txt)
bash run_chain.sh popAWQr1s0 $N0 -- http://127.0.0.1:8306/v1 gemma-4-31b $QAT subs/sample_noadapter popAWQr1s1 configs/eligible_113_half1.txt 8521 3 popAWQr1 >> $LOG 2>&1
say "chain launched popAWQr1s1 (rc=$?)"
N1=$(wc -w < configs/eligible_113_half1.txt)
bash run_chain.sh popAWQr1s1 $N1 -- http://127.0.0.1:8306/v1 gemma-4-31b $QAT subs/sample_noadapter popAWQr2s0 configs/eligible_113_half0.txt 8522 3 popAWQr2 >> $LOG 2>&1
say "chain launched popAWQr2s0 (rc=$?)"
bash run_chain.sh popAWQr2s0 $N0 -- http://127.0.0.1:8306/v1 gemma-4-31b $QAT subs/sample_noadapter popAWQr2s1 configs/eligible_113_half1.txt 8523 3 popAWQr2 >> $LOG 2>&1
say "chain launched popAWQr2s1 (rc=$?); waiting for completion"
while true; do
  nb=$(cat runs/popAWQr2s1_H_base/per_task.jsonl 2>/dev/null | wc -l); nf=$(cat runs/popAWQr2s1_H_fullp/per_task.jsonl 2>/dev/null | wc -l)
  live=$(systemctl --user list-units --no-legend --plain --state=active,activating "ap-e2e-popAWQr2s1-base*" "ap-e2e-popAWQr2s1-fullp*" | wc -l)
  [ "$live" -eq 0 ] && break; sleep 120; done
say "popAWQr2s1 harness exited (base $nb, fullp $nf of $N1)"
systemctl --user list-units --no-legend --plain --state=active "ap-e2e-popAWQr2s1-proxy*" "ap-vllm-g$G-*" | awk '{print $1}' | xargs -r -n1 systemctl --user stop
say "E_awq lanes done; server stopped (analysis waits for E_ext's final set)"
