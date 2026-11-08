#!/bin/bash
# Wait until no user scope whose name starts with $1 is active, then exec the remaining command (already inside a
# limited.sh scope, so the masking/memory/CPU settings are inherited).
# usage: chain_after.sh <scope-prefix> cmd args...
P=$1; shift
while systemctl --user list-units --type=scope --no-legend "${P}*" | grep -q .; do sleep 30; done
echo "[$(date -u +%H:%M:%S)] predecessor ${P}* finished; starting: $*"
exec "$@"
