#!/bin/sh
set -e

is_true() {
  case "$1" in
    true|True|TRUE|1|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

if is_true "$POPULATE_KB" || is_true "$NAVAI_POPULATE_KB"; then
  python scripts/populate_qdrant.py --auto
else
  echo "Skipping KB population on startup (set POPULATE_KB=1 to enable)"
fi

# Web-demo mode (RUN_TOKEN_SERVER=1): run the token/lead HTTP API AND the LiveKit
# worker together in one container. The token server binds $PORT (Render's public
# port) to serve /api/session + /health; the worker connects out to LiveKit Cloud
# and answers dispatched rooms. If either process exits, tear the container down
# so the platform restarts it. POSIX-sh compatible (base image /bin/sh is dash).
if is_true "$RUN_TOKEN_SERVER"; then
  echo "Web-demo mode: starting token server + LiveKit worker"

  python -m webapp.token_server &
  TOKEN_PID=$!
  python src/main.py start &
  WORKER_PID=$!

  trap 'kill "$TOKEN_PID" "$WORKER_PID" 2>/dev/null; exit 143' TERM INT

  exited=""
  while [ -z "$exited" ]; do
    kill -0 "$TOKEN_PID" 2>/dev/null || exited="token-server"
    kill -0 "$WORKER_PID" 2>/dev/null || exited="worker"
    [ -z "$exited" ] && sleep 2
  done

  echo "Process '$exited' exited; shutting down container"
  kill "$TOKEN_PID" "$WORKER_PID" 2>/dev/null || true
  exit 1
fi

exec "$@"
