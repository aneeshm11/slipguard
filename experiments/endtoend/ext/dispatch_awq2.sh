#!/bin/bash
# PREREG_E_awq2 lane dispatcher (PI, 2026-11-07; orchestration only, frozen with the prereg). Adapted from dispatch_ext.sh.
# Lanes popAWQr3s0, r3s1, ..., r8s1 (replicate order), one lane at a time per GPU slot. Each slot keeps one cyankiwi
# AWQ server (PREREG_E_awq args: bf16, text-only) on port 8300+G and runs PREREG_E's frozen run_population.sh unchanged
# with the QAT-ct proxy model dir (per-arm conc 3 -> 6 sandboxes; proxy port 8530+lane index). GPU6's server: cores 112-115.
# A slot takes a GPU only when it passes the user's gate (< 2 GB used, 0 compute apps) for NEED polls of 30 s.
# A lane is complete when base and fullp have one per_task line per task of its half AND its harness scopes have
# exited; then its proxy is stopped and the slot takes the next lane.
# usage: experiments/endtoend/ext/dispatch_awq2.sh "<gpu list>"   e.g. "0 1 2 6"
set -u
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; P=${TRANSCRIPTLAB_ROOT:-.}; LOG=$E/ext/dispatch_awq2.log
QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; AWQ=$P/models/community/cyankiwi_gemma-4-31B-it-AWQ-4bit; GPUS=(${1:-0 1 2 6}); NEED=${NEED:-2}
LANES=(); for k in 3 4 5 6 7 8; do for h in 0 1; do LANES+=("$k:$h"); done; done
say() { echo "[$(date -u +%H:%M:%S)] $*" >> $LOG; }
gate() { local g=$1 used uuid apps
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $g | tr -d ' ')
  uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $g | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
  [ "${used:-99999}" -lt 2048 ] && [ "$apps" -eq 0 ]; }
units() { systemctl --user list-units --no-legend --plain --state=active,activating "$1" | awk '{print $1}'; }
declare -A srv lane free
next=0
say "dispatcher start: GPUs ${GPUS[*]}; ${#LANES[@]} lanes"
while true; do
  active=0
  for g in "${GPUS[@]}"; do
    # 1. server
    if [ -z "${srv[$g]:-}" ]; then
      [ $next -ge ${#LANES[@]} ] && continue
      if gate $g; then free[$g]=$(( ${free[$g]:-0} + 1 )); else free[$g]=0; fi
      if [ "${free[$g]}" -ge "$NEED" ]; then
        vc=""; [ "$g" -ge 6 ] && vc=112-115
        VCORES=$vc $P/tools/serve_vllm.sh $g $((8300 + g)) $AWQ gemma-4-31b --dtype bfloat16 --max-num-seqs 64 \
          --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' \
          --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 >> $LOG 2>&1
        srv[$g]=starting; say "GPU $g: server :$((8300 + g)) launching"
      fi
      continue
    fi
    if [ "${srv[$g]}" = starting ]; then
      if curl -s -m 3 http://127.0.0.1:$((8300 + g))/v1/models >/dev/null; then srv[$g]=up; say "GPU $g: server up"; else continue; fi
    fi
    # 2. lane
    if [ -n "${lane[$g]:-}" ]; then
      active=$((active + 1))
      IFS=: read k h i <<< "${lane[$g]}"; tag=popAWQr${k}s${h}
      n=$(wc -w < $E/configs/eligible_113_half${h}.txt)
      nb=$(cat $E/runs/${tag}_H_base/per_task.jsonl 2>/dev/null | wc -l); nf=$(cat $E/runs/${tag}_H_fullp/per_task.jsonl 2>/dev/null | wc -l)
      live=$(units "ap-e2e-${tag}-base*"; units "ap-e2e-${tag}-fullp*")
      if [ -z "$live" ]; then
        if [ "$nb" -ge "$n" ] && [ "$nf" -ge "$n" ]; then say "lane $tag COMPLETE (base $nb, fullp $nf of $n) on GPU $g"
        else say "lane $tag EXITED EARLY (base $nb, fullp $nf of $n) on GPU $g -- needs PI attention"; fi
        units "ap-e2e-${tag}-proxy*" | xargs -r -n1 systemctl --user stop
        lane[$g]=""; active=$((active - 1))
      else continue; fi
    fi
    if [ $next -lt ${#LANES[@]} ]; then
      IFS=: read k h <<< "${LANES[$next]}"; tag=popAWQr${k}s${h}; port=$((8530 + next))
      ( cd $E && bash run_population.sh http://127.0.0.1:$((8300 + g))/v1 gemma-4-31b $QAT subs/sample_noadapter $tag \
          configs/eligible_113_half${h}.txt $port 3 popAWQr${k} >> $E/ext/lanes_awq2.out 2>&1 )
      lane[$g]="$k:$h:$next"; say "lane $tag launched on GPU $g (proxy :$port)"; next=$((next + 1)); active=$((active + 1))
    elif [ "${srv[$g]}" = up ]; then
      units "ap-vllm-g$g-*" | xargs -r -n1 systemctl --user stop; srv[$g]=done; say "GPU $g: no lanes left, server stopped"
    fi
  done
  if [ $next -ge ${#LANES[@]} ] && [ $active -eq 0 ]; then
    busy=0; for g in "${GPUS[@]}"; do [ -n "${lane[$g]:-}" ] && busy=1; done
    [ $busy -eq 0 ] && break
  fi
  sleep 60
done
for g in "${GPUS[@]}"; do units "ap-vllm-g$g-*" | xargs -r -n1 systemctl --user stop; done
say "dispatcher done"
