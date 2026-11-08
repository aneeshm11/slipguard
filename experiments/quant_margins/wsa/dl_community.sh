#!/bin/bash
# Community 4/8-bit quants of gemma-4-31b-it servable by vLLM 0.19.1 (PI T1 list). Every download is logged in wsa/DOWNLOADS.log.
export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1
cd ${TRANSCRIPTLAB_ROOT:-.}
for r in QuantTrio/gemma-4-31B-it-AWQ cyankiwi/gemma-4-31B-it-AWQ-4bit Intel/gemma-4-31B-it-int4-AutoRound RedHatAI/gemma-4-31B-it-FP8-dynamic RedHatAI/gemma-4-31B-it-NVFP4; do
  d=models/community/$(echo $r | tr '/' '__')
  rev=$(${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/python -c "from huggingface_hub import HfApi; print(HfApi().model_info('$r').sha)" 2>/dev/null)
  if ${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf download $r --revision $rev --local-dir $d --max-workers 4 > /dev/null 2>&1; then
    echo "$(date -u +%F' '%H:%M) downloaded $r @$rev -> $d ($(du -sh $d | cut -f1))" >> experiments/quant_margins/wsa/DOWNLOADS.log
  else
    echo "$(date -u +%F' '%H:%M) FAILED $r @$rev" >> experiments/quant_margins/wsa/DOWNLOADS.log
  fi
done
