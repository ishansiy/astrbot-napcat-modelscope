#!/bin/bash
set -euo pipefail
for attempt in $(seq 1 30); do
  if [ -S /tmp/.X11-unix/X99 ]; then break; fi
  sleep 1
done
exec /opt/QQ/qq --no-sandbox --disable-gpu ${QQ_ACCOUNT:+-q "$QQ_ACCOUNT"}
