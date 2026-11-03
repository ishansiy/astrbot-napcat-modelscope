#!/bin/bash
set -euo pipefail
for attempt in $(seq 1 60); do
  if [ -S /tmp/.X11-unix/X99 ]; then break; fi
  sleep 1
done
unset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS
# Managed Studio containers may reject the nested namespaces used by Glycin's
# image decoders. Keep the desktop within the existing container boundary.
if ! bwrap --unshare-all --ro-bind / / -- /usr/bin/true 2>/dev/null; then
  export GLYCIN_DISABLE_SANDBOX=i-know-the-risks
  echo '[desktop] Nested image sandbox unavailable; using the container boundary.'
fi
exec dbus-run-session -- xfce4-session
