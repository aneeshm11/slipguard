#!/bin/bash
# GPU3: after the G4 noise-floor run finishes, stop the repairA gate server and start the T1 sweep (SWEEP_PLAN, amended).
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/quant_margins/wsa
while systemctl --user is-active --quiet ap-qmbyte2-576400.scope; do sleep 15; done
for u in $(systemctl --user list-units --type=scope --no-legend 'ap-vllm-g3-*' | awk '{print $1}'); do systemctl --user stop "$u"; done
echo "[$(date -u +%H:%M:%S)] floor run done; gate server stopped; sweep starts"
G=3 PORT=8304 ./t1_sweep.sh
