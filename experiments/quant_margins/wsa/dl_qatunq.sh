#!/bin/bash
# Re-download Google's QAT-unquantized 31B release (restoring a logged deletion; PI-approved 2026-11-05).
export HF_HOME=${TRANSCRIPTLAB_ROOT:-.}/hf_cache HF_HUB_DISABLE_TELEMETRY=1
cd ${TRANSCRIPTLAB_ROOT:-.}
${TRANSCRIPTLAB_ENVS:-envs}/env_gemma/bin/hf download google/gemma-4-31b-it-qat-q4_0-unquantized --revision 1e4d8beecacb8b7590c1d8bedd7335f687bf311f \
  --local-dir models/gemma-4-31b-it-qat-q4_0-unquantized --max-workers 4 > experiments/quant_margins/wsa/logs/dl_qatunq.out 2>&1 \
  && echo "OK $(date -u +%H:%M) $(du -sh models/gemma-4-31b-it-qat-q4_0-unquantized | cut -f1)" || echo "FAIL $(date -u +%H:%M)"
