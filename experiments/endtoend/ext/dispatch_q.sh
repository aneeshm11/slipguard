#!/bin/bash
# Shared-queue lane dispatcher for PREREG_E_audit and PREREG_E_comp (PI, 2026-11-07; orchestration only, frozen with both).
# Derived from dispatch_ext.sh / dispatch_awq2.sh; adds per-lane models, tensor-parallel slots and a shared queue.
# usage: dispatch_q.sh "<slots>" <queue file> <log name>
#   slot: one GPU ("1") or a tensor-parallel pair ("0+2"). A TP slot takes only bf16tp2 lanes; a single slot takes the rest.
#   queue lines: TAG|MODEL|LAUNCHER|HALF|SALT|PROXYPORT  ('#' starts a comment). LAUNCHER: pop = run_population.sh
#   (arms base, fullp; frozen PREREG_E launcher) or qi = run_population_qi.sh (arms quar, ipd).
#   Lanes are claimed in file order by an atomic mkdir in ext/claims/, so several dispatchers can share one queue.
#   No lane is claimed after LAST_START (default 2026-11-08T11:30:00Z), so lanes end before the Nov 8 14:00 UTC cutoff.
#   A slot (re)starts its server when the claimed lane's model differs from the one running, only after the user's gate
#   (< 2 GB used and 0 compute apps on every GPU of the slot) has held for NEED polls of 60 s.
#   A lane is complete when both arms have one per_task line per task of its half and its harness scopes have exited;
#   then its proxy is stopped and the slot claims the next lane. A server that is not up within 40 min marks its model
#   bad for this dispatcher (its lanes are skipped and logged).
set -u
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; P=${TRANSCRIPTLAB_ROOT:-.}
SLOTS=($1); Q=$2; LOG=$E/ext/$3.log; CL=$E/ext/claims; NEED=${NEED:-2}; LAST_START=${LAST_START:-2026-11-08T11:30:00Z}
QAT=$P/models/gemma-4-31b-it-qat-w4a16-ct; CM=$P/models/community
TXT='{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}'
PARSERS="--enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4"
mkdir -p $CL
say() { echo "[$(date -u +%H:%M:%S)] $*" >> $LOG; }
gate1() { local g=$1 used uuid apps
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $g | tr -d ' ')
  uuid=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i $g | tr -d ' ')
  apps=$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | tr -d ' ' | grep -c "$uuid")
  [ "${used:-99999}" -lt 2048 ] && [ "$apps" -eq 0 ]; }
gate() { local g; for g in ${1//+/ }; do gate1 $g || return 1; done; return 0; }
units() { systemctl --user list-units --no-legend --plain --state=active,activating "$1" | awk '{print $1}'; }
is_tp() { [[ "$1" == *+* ]]; }
port_of() { if is_tp $1; then echo 8305; else echo $((8300 + $1)); fi; }
stop_srv() { local s=$1
  if is_tp $s; then units "ap-vllm-tp-g${s%%+*}g${s##*+}-*"; else units "ap-vllm-g$s-*"; fi | xargs -r -n1 systemctl --user stop; }
start_srv() { local s=$1 m=$2 port d vc; port=$(port_of $s)
  case $m in
    qat) $P/tools/serve_vllm.sh $s $port $QAT gemma-4-31b --max-num-seqs 64 $PARSERS ;;
    qatawq|qatnvfp4|nvnvfp4)
      case $m in qatawq) d=cyankiwi_gemma-4-31B-it-qat-AWQ-INT4;; qatnvfp4) d=melcheikh_gemma-4-31B-it-qat-NVFP4-Blackwell;;
                 nvnvfp4) d=nvidia_Gemma-4-31B-IT-NVFP4;; esac
      vc=""; [ "$s" -ge 6 ] && vc=112-115
      VCORES=$vc $P/tools/serve_vllm.sh $s $port $CM/$d gemma-4-31b --dtype bfloat16 --max-num-seqs 64 --hf-overrides "$TXT" $PARSERS ;;
    bf16tp2) $P/tools/serve_vllm_tp2.sh ${s%%+*} ${s##*+} $port $P/models/gemma-4-31b-it gemma-4-31b --max-num-seqs 64 $PARSERS ;;
    *) say "unknown model $m"; return 1 ;;
  esac >> $LOG 2>&1; }
arms_of() { case $1 in pop) echo "base fullp";; qi) echo "quar ipd";; esac; }
launcher_of() { case $1 in pop) echo run_population.sh;; qi) echo run_population_qi.sh;; esac; }
BAD=" "
claim() {   # $1 slot -> prints the claimed queue line (or nothing)
  local s=$1 line tag m
  [ "$(date -u +%s)" -ge "$(date -u -d "$LAST_START" +%s)" ] && return 0
  while IFS= read -r line; do
    line=${line%%#*}; [ -z "${line// /}" ] && continue
    IFS='|' read -r tag m _ <<< "$line"
    if is_tp $s; then [ "$m" = bf16tp2 ] || continue; else [ "$m" = bf16tp2 ] && continue; fi
    [[ "$BAD" == *" $m "* ]] && continue
    [ -d "$CL/$tag" ] && continue
    if mkdir "$CL/$tag" 2>/dev/null; then echo "$(date -u +%FT%T) slot $s $LOG" > "$CL/$tag/by"; echo "$line"; return 0; fi
  done < "$Q"
  return 0; }
declare -A srvm srvst t0 lane pend free done_
say "dispatcher start: slots ${SLOTS[*]}; queue $Q; LAST_START $LAST_START"
while true; do
  alive=0
  for s in "${SLOTS[@]}"; do
    [ -n "${done_[$s]:-}" ] && continue
    alive=1
    # 1. running lane
    if [ -n "${lane[$s]:-}" ]; then
      IFS='|' read -r tag m L h salt pp <<< "${lane[$s]}"
      n=$(wc -w < $E/configs/eligible_113_half${h}.txt); live=""; cnt=""; ok=1
      for a in $(arms_of $L); do
        live+=$(units "ap-e2e-${tag}-${a}*")
        c=$(cat $E/runs/${tag}_H_${a}/per_task.jsonl 2>/dev/null | wc -l); cnt+="$a $c, "; [ "$c" -ge "$n" ] || ok=0
      done
      [ -n "$live" ] && continue
      if [ $ok -eq 1 ]; then say "lane $tag COMPLETE (${cnt}of $n) on slot $s"; else say "lane $tag EXITED EARLY (${cnt}of $n) on slot $s -- needs PI attention"; fi
      units "ap-e2e-${tag}-proxy*" | xargs -r -n1 systemctl --user stop
      lane[$s]=""
    fi
    # 2. next lane
    if [ -z "${pend[$s]:-}" ]; then
      pend[$s]=$(claim $s)
      if [ -z "${pend[$s]}" ]; then
        [ -n "${srvm[$s]:-}" ] && { stop_srv $s; say "slot $s: no lanes left, server stopped"; }
        done_[$s]=1; srvm[$s]=""; continue
      fi
      say "slot $s claimed ${pend[$s]%%|*}"
    fi
    IFS='|' read -r tag m L h salt pp <<< "${pend[$s]}"
    # 3. server for the lane's model
    if [ "${srvm[$s]:-}" != "$m" ]; then
      if [ -n "${srvm[$s]:-}" ]; then stop_srv $s; say "slot $s: stopped ${srvm[$s]} server (next lane needs $m)"; srvm[$s]=""; free[$s]=0; fi
      if gate $s; then free[$s]=$(( ${free[$s]:-0} + 1 )); else free[$s]=0; fi
      if [ "${free[$s]}" -ge "$NEED" ]; then
        start_srv $s $m && { srvm[$s]=$m; srvst[$s]=starting; t0[$s]=$(date +%s); say "slot $s: $m server :$(port_of $s) launching"; }
      fi
      continue
    fi
    if [ "${srvst[$s]}" = starting ]; then
      if curl -s -m 3 http://127.0.0.1:$(port_of $s)/v1/models >/dev/null; then srvst[$s]=up; say "slot $s: $m server up"
      elif [ $(( $(date +%s) - ${t0[$s]} )) -gt 2400 ]; then
        say "slot $s: $m server NOT READY after 40 min -- model marked bad; lane $tag released unrun"; stop_srv $s
        BAD+="$m "; echo "server not ready" > "$CL/$tag/NOT_RUN"; srvm[$s]=""; pend[$s]=""; free[$s]=0; continue
      else continue; fi
    fi
    # 4. launch
    ( cd $E && bash $E/$(launcher_of $L) http://127.0.0.1:$(port_of $s)/v1 gemma-4-31b $QAT subs/sample_noadapter $tag \
        configs/eligible_113_half${h}.txt $pp 3 $salt >> $E/ext/lanes_q.out 2>&1 )
    lane[$s]="${pend[$s]}"; pend[$s]=""; say "lane $tag ($m, $(arms_of $L)) launched on slot $s (proxy :$pp, salt $salt)"
  done
  [ $alive -eq 0 ] && break
  sleep 60
done
say "dispatcher done (slots ${SLOTS[*]})"
