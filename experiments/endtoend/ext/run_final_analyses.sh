#!/bin/bash
# PI, 2026-11-08: run the registered PREREG_E_audit and PREREG_E_comp analyses ONCE (§3 of each: at the earlier of
# "every queued lane finished" or 2026-11-08 14:00 UTC). Refuses if an output already exists. CPU only, <= 8 cores.
set -u
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; P=${TRANSCRIPTLAB_ROOT:-.}; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_agentpaper/bin/python
cd $E
for f in analysis/prereg_E_audit.json analysis/prereg_E_comp.json analysis/prereg_E_audit.stdout.txt analysis/prereg_E_comp.stdout.txt; do
  [ -e "$f" ] && { echo "REFUSE: $f exists (the analysis runs once)"; exit 2; }
done
now=$(date -u +%s); cut=$(date -u -d '2026-11-08 14:00:00' +%s)
running=$(systemctl --user list-units 'ap-e2e-*' --no-legend --plain --state=active | grep -c . || true)
queued=0; for t in $(grep -v '^#' ext/queue_single.txt | cut -d'|' -f1); do [ -d "ext/claims/$t" ] || queued=$((queued+1)); done
echo "[$(date -u +%T)] queued (unclaimed) $queued; active lane units $running; cutoff passed: $([ $now -ge $cut ] && echo yes || echo no)"
if [ $now -lt $cut ] && { [ $running -gt 0 ] || [ $queued -gt 0 ]; }; then echo "NOT YET: lanes still queued or running before the cutoff"; exit 3; fi
if [ $running -gt 0 ]; then echo "cutoff: stopping still-running lanes (not analysed, PREREG §3)"; systemctl --user list-units 'ap-e2e-*' --no-legend --plain --state=active | awk '{print $1}' | tee -a $E/ext/cutoff_stopped_lanes.txt | xargs -r -n1 systemctl --user stop; fi
for s in E_audit E_comp; do
  echo "== $s status (completeness only) =="; TMPDIR=$P/tmp taskset -c 120-127 $PY analysis/prereg_${s}_analysis.py --out /dev/null --status_only
done
for s in E_audit E_comp; do
  echo "== $s ANALYSIS (once) $(date -u +%T) =="
  TMPDIR=$P/tmp taskset -c 120-127 $PY analysis/prereg_${s}_analysis.py --out analysis/prereg_${s}.json 2>&1 | tee analysis/prereg_${s}.stdout.txt
  echo "rc=${PIPESTATUS[0]}"
done
sha256sum analysis/prereg_E_audit.json analysis/prereg_E_comp.json
echo "- $(date -u '+%Y-%m-%d %H:%M:%S') UTC — PI ran the registered PREREG_E_audit and PREREG_E_comp analyses ONCE (ext/run_final_analyses.sh): analysis/prereg_E_audit.json, analysis/prereg_E_comp.json (+ .stdout.txt)." >> $P/PROGRESS.md
