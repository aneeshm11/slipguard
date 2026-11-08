#!/bin/bash
# Post-run analysis for one v2 model: frozen analyze.py (full, H1, H2), exploratory protocol_failure, lenient sensitivity,
# then combine_v2 + finalize. usage: post_v2.sh <mk>   (run under limited.sh; <=4 cores)
X=${TRANSCRIPTLAB_ROOT:-.}/experiments/crossfamily; PY=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python
MAN=${TRANSCRIPTLAB_ROOT:-.}/data/pnc/contexts/P-swebench-31b-S1-v1/manifest.json; MK=$1
export HF_HUB_OFFLINE=1
$PY $X/scripts/v2_frozen/analyze.py --mk $MK --manifest $MAN --gen $X/out/v2/gen_$MK.jsonl --out $X/out/v2/ana_$MK.json > $X/logs/v2_ana_$MK.log 2>&1 &
$PY $X/scripts/v2_frozen/analyze.py --mk $MK --manifest $MAN --gen $X/out/v2/gen_$MK.jsonl --ids $X/out/v2/ids_A1_H1.txt --out $X/out/v2/ana_${MK}_H1.json > $X/logs/v2_ana_${MK}_H1.log 2>&1 &
$PY $X/scripts/v2_frozen/analyze.py --mk $MK --manifest $MAN --gen $X/out/v2/gen_$MK.jsonl --ids $X/out/v2/ids_A1_H2.txt --out $X/out/v2/ana_${MK}_H2.json > $X/logs/v2_ana_${MK}_H2.log 2>&1 &
$PY $X/scripts/protocol_failure.py --gen $X/out/v2/gen_$MK.jsonl --prompts $X/out/v2/prompts_$MK.jsonl --out $X/out/v2/pf_$MK.json > $X/logs/v2_pf_$MK.log 2>&1 &
wait
$PY $X/scripts/sensitivity_reasoning.py $X/out/v2/gen_$MK.jsonl $X/out/v2/prompts_$MK.jsonl > $X/logs/v2_sens_$MK.log 2>&1
$PY $X/scripts/v2_frozen/analyze.py --mk $MK --manifest $MAN --gen $X/out/v2/gen_${MK}_lenient.jsonl --out $X/out/v2/ana_${MK}_lenient.json > $X/logs/v2_ana_${MK}_lenient.log 2>&1
$PY $X/scripts/combine_v2.py $X/out/v2/results_v2.json $X/out/v2 > $X/logs/v2_combine.log 2>&1
$PY $X/scripts/finalize.py > $X/logs/finalize.log 2>&1
echo "post_v2 $MK done $(date -u +%H:%M:%S)"
