#!/bin/bash
# PREREG_v2.15 driver: after PREREG_v2.14 ends, QAT-AWQ on GPU 4 and QAT-NVFP4 on GPU 5 in parallel; nvidia NVFP4 on whichever
# GPU frees first; then the analysis ONCE.
set -u
P=${TRANSCRIPTLAB_ROOT:-.}; V=$P/experiments/v215; LOG=$V/driver.log
say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a $LOG; }
say "waiting for PREREG_v2.14 to end"
for i in $(seq 1 1440); do grep -q "v214 verdict\|NOT RUN" $P/experiments/v214/run_bf16.log 2>/dev/null && break; sleep 30; done
say "v2.14 ended: $(tail -1 $P/experiments/v214/run_bf16.log)"
bash $V/run_one.sh qatawq 4 8385 & A=$!
bash $V/run_one.sh qatnvfp4 5 8386 & B=$!
wait -n $A $B; 
if kill -0 $A 2>/dev/null; then G3=5; P3=8386; else G3=4; P3=8385; fi
say "first run ended; nvidia NVFP4 on GPU $G3"
bash $V/run_one.sh nvnvfp4 $G3 $P3
wait
say "all three ended; analysis once"
( cd $P && TMPDIR=$P/tmp taskset -c 120-123 ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python $V/analyze_v215.py --out $P/experiments/contagion/out/confirmatory/v215_audit_panel.json >> $LOG 2>&1 )
say "v215 verdict: $(grep -o '"verdict": "[^"]*"' $P/experiments/contagion/out/confirmatory/v215_audit_panel.json | head -1)"
