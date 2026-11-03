#!/bin/bash
set -euo pipefail
for attempt in $(seq 1 60); do
  if [ -S /tmp/.X11-unix/X99 ]; then break; fi
  sleep 1
done
unset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS
exec dbus-run-session -- xfce4-session
