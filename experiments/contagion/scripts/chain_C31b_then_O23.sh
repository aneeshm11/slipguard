#!/bin/bash
# After the 31B confirmatory runner finishes: one resume pass (re-runs only transient errors; no-op otherwise), then the
# PREREG_v2.3 onset transplant (O0/O1, 1,200 jobs) on the same server. Never two A runners on the server at once.
cd ${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion
C=${TRANSCRIPTLAB_ROOT:-.}/data/pnc/contexts/P-swebench-31b-S1-v1; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; LIM=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh
until grep -q "^finished" logs/ctg-C31b.log && ! systemctl --user list-units --no-legend 'ap-ctg-C31b*' | grep -q running; do sleep 30; done
echo "== resume pass $(date -u +%H:%M:%S)" >> logs/ctg-C31b.log
NAME=ctg-C31b QN=VLLM:Worker_D3 MEM=40G $LIM $PY scripts/run_injection.py --manifest $C/manifest.json --meta data/confirmatory/meta_S1.jsonl \
  --plan data/confirmatory/plans/plan_v2_31b.jsonl --out out/main/rC31b_v2.jsonl --template $C/chat_template.jinja --blind --conc 24 \
  --base http://127.0.0.1:8303/v1 --model gemma-4-31b >> logs/ctg-C31b.log 2>&1
echo "== O23 start $(date -u +%H:%M:%S) | renderer $(sha256sum ${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend/export/quarantine_renderer.py | cut -c1-16) | run_onset $(sha256sum scripts/run_onset.py | cut -c1-16)" >> logs/ctg-O23.log
NAME=ctg-O23 QN=VLLM:Worker_D3 MEM=40G $LIM $PY scripts/run_onset.py --manifest $C/manifest.json --meta data/confirmatory/meta_S1.jsonl \
  --plan data/onset/plan_O_v23.jsonl --out out/main/rO_v23.jsonl --template $C/chat_template.jinja --blind --conc 24 \
  --base http://127.0.0.1:8303/v1 --model gemma-4-31b >> logs/ctg-O23.log 2>&1
echo "chain done $(date -u +%H:%M:%S)" >> logs/ctg-chainO23.log
