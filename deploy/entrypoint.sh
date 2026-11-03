#!/bin/bash
set -euo pipefail
umask 077
ulimit -c 0 || true
export STACK_DATA_DIR="${STACK_DATA_DIR:-/mnt/workspace/dafeiyu}"
mkdir -p "$STACK_DATA_DIR" /run/nginx /var/log/supervisor
python /opt/dafeiyu/bootstrap.py
exec supervisord -n -c /opt/dafeiyu/supervisord.conf
