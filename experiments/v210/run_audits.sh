#!/bin/bash
# PREREG_v2.10 runner (PI). usage: experiments/v210/run_audits.sh <gpu> <vcores> <cli_cores>
# Audits each downloaded checkpoint with the shipped `slipguard audit-weights` (gate: < 2 GB used, 0 compute apps).
set -u
G=$1; VC=$2; CC=$3; PORT=$((8390 + G)); P=${TRANSCRIPTLAB_ROOT:-.}; LOG=$P/experiments/v210/run_audits.log; LIM=$P/tools/limited.sh
PYA=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python; O=$P/experiments/quant_margins/wsa/out; REF=$O/audit_sweep_31b_bf16.records.jsonl
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOG; }
gate() { local used uuid apps
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $G | tr -d ' ')
  uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $G | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
  [ "${used:-99999}" -lt 2048 ] && [ "$apps" -eq 0 ]; }
stop_srv() { systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | awk '{print $1}' | xargs -r -n1 systemctl --user stop; }
for spec in cyankiwi/gemma-4-31B-it-qat-AWQ-INT4:qatawq_cyankiwi nvidia/Gemma-4-31B-IT-NVFP4:nvfp4_nvidia \
            unsloth/gemma-4-31B-it-unsloth-bnb-4bit:bnb4_unsloth unsloth/gemma-4-31B-it-NVFP4:nvfp4_unsloth \
            melcheikh/gemma-4-31B-it-qat-NVFP4-Blackwell:qatnvfp4_melcheikh; do
  RID=${spec%%:*}; NAME=31b_${spec##*:}; MD=$P/models/community/${RID//\//_}
  for i in $(seq 1 360); do grep -q " $RID rev " $P/logs/dl/v210.log 2>/dev/null && break; sleep 30; done
  grep -q " $RID rev " $P/logs/dl/v210.log || { say "$NAME: download not finished -> skipped"; continue; }
  for i in $(seq 1 60); do gate && break; sleep 10; done
  gate || { say "GATE FAILED on GPU $G before $NAME"; exit 3; }
  say "gate OK on GPU $G; $NAME"
  VCORES=$VC $P/tools/serve_vllm.sh $G $PORT $MD $NAME --max-num-seqs 32 \
    --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' | tee -a $LOG
  ok=0; for i in $(seq 1 120); do curl -s -m 3 http://127.0.0.1:$PORT/v1/models >/dev/null && { ok=1; break; }
    systemctl --user list-units "ap-vllm-g$G-*" --no-legend --plain --state=active | grep -q . || break; sleep 10; done
  if [ $ok -ne 1 ]; then say "$NAME: NOT SERVABLE (vLLM 0.19.1, H100)"; grep -iE "error|exception|not supported" $P/logs/vllm/g${G}_${PORT}.log | tail -8 >> $LOG; stop_srv; sleep 20; continue; fi
  grep -m1 "non-default args" $P/logs/vllm/g${G}_${PORT}.log >> $LOG
  say "$NAME audit start"
  ( cd $P/release/lib && TMPDIR=$P/tmp PYTHONPATH=src NAME=aud$G QN=VLLM:Worker_D$G MEM=20G CORES=$CC $LIM $PYA -m slipguard audit-weights \
      --endpoint http://127.0.0.1:$PORT/v1 --served-name $NAME --pnc $P/data/pnc --tokenizer $P/models/gemma-4-31b-it \
      --records $O/audit_v210_$NAME.records.jsonl --reference $REF --out $O/audit_v210_$NAME.json --conc 2 >> $LOG 2>&1 )
  say "$NAME audit exited rc=$?"
  stop_srv; sleep 20
done
say "v210 audits done"
( cd $P && $PYA experiments/v210/analyze_v210.py --out $P/experiments/quant_margins/wsa/out/v210_audit_breadth.json >> $LOG 2>&1 )
say "v210 verdicts: H_QAT $(grep -o '"H_QAT": "[^"]*"' $P/experiments/quant_margins/wsa/out/v210_audit_breadth.json)"
