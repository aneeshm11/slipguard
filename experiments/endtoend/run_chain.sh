#!/bin/bash
# Chain one population campaign after another on the same lane (PREREG_E §3: replicate 2 follows replicate 1).
# usage: bash run_chain.sh <done_tag> <expected_tasks> -- <run_population.sh args...>
#   waits until runs/<done_tag>_H_base and runs/<done_tag>_H_fullp both have <expected_tasks> per_task lines AND their
#   harness scopes have exited, then stops the <done_tag> proxy scope and launches run_population.sh with the args.
#   Runs as its own limited scope (NAME=e2e-chain-<done_tag>); stop that scope to cancel the chain.
set -uo pipefail
DONE=$1; N=$2; shift 2; [ "$1" == "--" ] && shift
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; cd $E
while true; do
  nb=$(cat runs/${DONE}_H_base/per_task.jsonl 2>/dev/null | wc -l); nf=$(cat runs/${DONE}_H_fullp/per_task.jsonl 2>/dev/null | wc -l)
  live=$(systemctl --user list-units --no-legend --state=active,activating "ap-e2e-${DONE}-base*" "ap-e2e-${DONE}-fullp*" | wc -l)
  if [ "$nb" -ge "$N" ] && [ "$nf" -ge "$N" ] && [ "$live" -eq 0 ]; then break; fi
  if [ "$live" -eq 0 ] && { [ "$nb" -lt "$N" ] || [ "$nf" -lt "$N" ]; }; then
    echo "$(date -u +%FT%T) $DONE harness exited early (base $nb, fullp $nf of $N): chain NOT launched"; exit 1; fi
  sleep 120
done
for u in $(systemctl --user list-units --no-legend "ap-e2e-${DONE}-proxy*" | awk '{print $1}'); do systemctl --user stop $u; done
echo "$(date -u +%FT%T) $DONE complete (base $nb, fullp $nf); proxy stopped; launching: run_population.sh $*"
bash $E/run_population.sh "$@"
