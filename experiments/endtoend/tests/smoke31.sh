#!/bin/bash
# Nov 5 11:00-12:00 (UPGRADE_PLAN §3): 31B smoke of the freeze candidate on :8300 — 2 tasks x {base, fullp}, 1 SB per arm.
# usage: bash tests/smoke31.sh [backend_url]      then: python tests/smoke_qa.py logs/proxy_smoke31
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend
printf 'requests_7309\nrich_4006\n' > $E/configs/smoke31_tasks.txt
bash $E/run_population.sh ${1:-http://127.0.0.1:8300/v1} gemma-4-31b ${TRANSCRIPTLAB_MODELS:-models}/gemma-4-31b-it-qat-w4a16-ct \
     $E/subs/sample_noadapter smoke31 $E/configs/smoke31_tasks.txt 8449 1 smoke31
