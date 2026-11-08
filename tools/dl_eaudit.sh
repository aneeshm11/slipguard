#!/bin/bash
# Re-download the PREREG_v2.10 checkpoints for the end-to-end audit validation (pinned revisions from logs/dl/v210.log).
cd ${TRANSCRIPTLAB_ROOT:-.}; LOG=logs/dl/eaudit.log
for spec in cyankiwi/gemma-4-31B-it-qat-AWQ-INT4:b0af25ee5b9802d5a5fc84da316c2daea28839f8 \
            nvidia/Gemma-4-31B-IT-NVFP4:4135a98a9b728a548947683219633b25682223ac \
            melcheikh/gemma-4-31B-it-qat-NVFP4-Blackwell:4f01d2c46d00ad66cdaf1e58992749c4d4f0023f; do
  r=${spec%%:*}; rev=${spec##*:}; d=models/community/$(echo $r | tr '/' '_'); t0=$(date +%s)
  HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/cache/hf ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf download $r --revision $rev --local-dir $d --max-workers 4 >> $LOG.raw 2>&1 \
    && echo "$(date -u +%H:%M:%S) OK $r rev $rev -> $d ($(( $(date +%s) - t0 )) s, $(du -sh $d | cut -f1))" >> $LOG \
    || echo "$(date -u +%H:%M:%S) FAIL $r rev $rev" >> $LOG
done
echo "$(date -u +%H:%M:%S) all done" >> $LOG
