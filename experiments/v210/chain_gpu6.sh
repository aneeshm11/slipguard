#!/bin/bash
# GPU6 chain (PI): wait (<= 90 min) until v2.8 has finished on GPU6 and the gate passes, then v2.9, then v2.10.
P=${TRANSCRIPTLAB_ROOT:-.}
for i in $(seq 1 540); do grep -q "v28 analysis done" $P/experiments/v28/run_cli.log && [ "$(grep -c 'v28 analysis done' $P/experiments/v28/run_cli.log)" -ge 2 ] && break; sleep 10; done
$P/experiments/v29/run_cov.sh 6 112-115 116-117
$P/experiments/v210/run_audits.sh 6 112-115 116-117
