#!/bin/bash
# The 31B (:8300) chain of workstream A after PREREG_v1 (plan order). Each step: own scope, own output file; governed arms
# run --blind. Usage: launch_31b_chain.sh <first-predecessor-prefix or NONE>
D=${TRANSCRIPTLAB_ROOT:-.}/experiments/contagion; O=$D/out/main; PYX=${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python; R=$D/scripts/run_injection.py
LIM=${TRANSCRIPTLAB_ROOT:-.}/tools/limited.sh; CH=$D/scripts/chain_after.sh; U=http://127.0.0.1:8300/v1
POOL=$O/r31b_old_a.jsonl,$O/r31b_old_b.jsonl,$O/r31b_old_A.jsonl,$O/r31b_old_B.jsonl,$O/r31b_old_G.jsonl,$O/r31b_old_P6.jsonl,$O/r31b_old_A1a.jsonl,$O/r31b_old_L2.jsonl,$O/r31b_old_D.jsonl,$O/r31b_old_P6k.jsonl
FIRST=${1:-NONE}
L(){ QN=VLLM:Worker_D0 NAME=$1 nohup $LIM $CH $2 $PYX $R "${@:3}" --base $U --model gemma-4-31b >> $D/logs/$1.log 2>&1 & sleep 1; }
L ctg-31b-D   $FIRST          --plan $D/data/plan_31b_T3r.jsonl --out $O/r31b_old_D.jsonl --skip_done_from $POOL --blind --conc 32 --ctx_conc 8
L ctg-31b-A1a ap-ctg-31b-D-   --plan $D/data/plan_31b_A1a.jsonl --out $O/r31b_old_A1a.jsonl --skip_done_from $POOL --blind --conc 32 --ctx_conc 16
L ctg-31b-RD  ap-ctg-31b-A1a- --plan $D/data/plan_31b_RD.jsonl --out $O/r31b_rdose.jsonl --blind --conc 32 --ctx_conc 12
L ctg-31b-L2  ap-ctg-31b-RD-  --plan $D/data/plan_31b_L2.jsonl --out $O/r31b_old_L2.jsonl --skip_done_from $POOL --blind --conc 32 --ctx_conc 12
L ctg-31b-P6k ap-ctg-31b-L2-  --plan $D/data/plan_31b_P6k.jsonl --out $O/r31b_old_P6k.jsonl --skip_done_from $POOL --blind --conc 32 --ctx_conc 8
L ctg-31b-A2  ap-ctg-31b-P6k- --plan $D/data/plan_a2_LP5.jsonl --meta $D/data/a2_meta.jsonl --out $O/r31b_a2.jsonl --blind --conc 32 --ctx_conc 12
L ctg-31b-HO  ap-ctg-31b-A2-  --plan $D/data/plan_31b_HO.jsonl --out $O/r31b_heldout.jsonl --blind --conc 32 --ctx_conc 8
L ctg-31b-TRs ap-ctg-31b-HO-  --plan $D/data/plan_31b_TR.jsonl --out $O/r31b_retest_sameseed.jsonl --conc 32 --ctx_conc 12
L ctg-31b-TRn ap-ctg-31b-TRs- --plan $D/data/plan_31b_TR.jsonl --out $O/r31b_retest_newseed.jsonl --seed_offset 7919 --conc 32 --ctx_conc 12
