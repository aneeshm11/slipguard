#!/bin/bash
# Stop MY ap-ctg* scopes that have 0 tasks: systemd's inotify limit is exhausted on this host, so a finished scope
# can linger as "active". Only empty scopes are stopped; nothing with a live process is ever touched.
end=$(( $(date +%s) + ${1:-21600} ))
while [ $(date +%s) -lt $end ]; do
  for u in $(systemctl --user list-units --no-legend 'ap-ctg*' | awk '{print $1}'); do
    t=$(systemctl --user show -p TasksCurrent --value "$u" 2>/dev/null)
    if [ "$t" = "0" ]; then sleep 5; t2=$(systemctl --user show -p TasksCurrent --value "$u" 2>/dev/null); [ "$t2" = "0" ] && systemctl --user stop "$u" && echo "$(date -u +%H:%M:%S) reaped empty $u"; fi
  done
  sleep 30
done
