#!/bin/bash
# Post-run analysis for one extension model (prereg_ext.md): frozen ext_frozen/analyze.py (full, H1, H2), exploratory
# protocol_failure for Qwen thinking models, then combine_ext + finalize. usage: post_ext.sh <mk>
X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
MAN=${TRANSCRIPTLAB_ROOT:-.}/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json; MK=$1
export HF_HUB_OFFLINE=1 TIKTOKEN_RS_CACHE_DIR=$X/data/tiktoken_cache
$PY $X/scripts/ext_frozen/analyze.py --mk $MK --manifest $MAN --gen $X/out/ext/gen_$MK.jsonl --out $X/out/ext/ana_$MK.json > $X/logs/ext_ana_$MK.log 2>&1 &
$PY $X/scripts/ext_frozen/analyze.py --mk $MK --manifest $MAN --gen $X/out/ext/gen_$MK.jsonl --ids $X/out/ext/ids_A1_H1.txt --out $X/out/ext/ana_${MK}_H1.json > $X/logs/ext_ana_${MK}_H1.log 2>&1 &
$PY $X/scripts/ext_frozen/analyze.py --mk $MK --manifest $MAN --gen $X/out/ext/gen_$MK.jsonl --ids $X/out/ext/ids_A1_H2.txt --out $X/out/ext/ana_${MK}_H2.json > $X/logs/ext_ana_${MK}_H2.log 2>&1 &
if [ "$MK" = "qwen3.8-27b" ]; then
  $PY $X/scripts/ext_frozen/protocol_failure.py --gen $X/out/ext/gen_$MK.jsonl --prompts $X/out/ext/prompts_$MK.jsonl --out $X/out/ext/pf_$MK.json > $X/logs/ext_pf_$MK.log 2>&1 &
fi
wait
$PY $X/scripts/combine_ext.py $X/out/ext/results_ext.json $X/out/ext > $X/logs/ext_combine.log 2>&1
$PY $X/scripts/finalize.py > $X/logs/finalize.log 2>&1
echo "post_ext $MK done $(date -u +%H:%M:%S)"
