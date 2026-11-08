#!/bin/bash
# Code-freeze manifest for PREREG_E.md: sha256 of every code/config file + one digest over the manifest.
# usage: bash tools_freeze.sh [label]   -> PREREG_E_manifest[_label].txt
E=${TRANSCRIPTLAB_ROOT:-.}/experiments/endtoend; cd $E
OUT=PREREG_E_manifest${1:+_$1}.txt
{ echo "# workstream E code manifest  $(date -u +%Y-%m-%dT%H:%M:%SZ)  label=${1:-freeze}"
  find proxy export harness client analysis configs tests -type f \( -name '*.py' -o -name '*.json' -o -name '*.txt' -o -name '*.sh' -o -name '*.jinja' \) \
       ! -path '*/__pycache__/*' | sort | xargs sha256sum
  sha256sum run_*.sh tools_freeze.sh PREREG_E.md PREREG_DEVIATIONS.md RUNBOOK.md proxy/VENDOR_B.txt acceptance/FREEZE_CANDIDATE.txt acceptance/final_code_sha256.txt
  sha256sum subs/*/agent.yaml subs/*/eval_config.yaml subs/*/configs/sampling.yaml subs/*/prompts/*.md subs/*/sub_agents/*.yaml 2>/dev/null
} > $OUT
d=$(grep -v '^#' $OUT | sha256sum | awk '{print $1}')
echo "# DIGEST $d" >> $OUT
echo "$OUT digest $d"
