#!/bin/bash
# In-process targets over C's real valid calls (2 shards). usage: conformance/run_rv.sh <suite dir> <out dir> <python>
SUITE=$1; OUT=$2; PY=$3; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
for s in 0 1; do
  "$PY" "$HERE/gg_targets.py" "$SUITE/work/real_valid/cases_real_valid.jsonl" "$OUT/rv_$s.jsonl" $s 2 --suite "$SUITE" \
    --targets gg.completion,gg.extract --lean 2>/dev/null &
done
wait
