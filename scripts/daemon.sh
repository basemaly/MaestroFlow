#!/usr/bin/env bash
#
# daemon.sh - Detached MaestroFlow supervisor lifecycle
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$REPO_ROOT/.run"
SUPERVISOR_LOG="$REPO_ROOT/logs/supervisor.log"
export DEER_FLOW_ROOT="${DEER_FLOW_ROOT:-$REPO_ROOT}"
DOCKER_COMPOSE_CMD=(docker compose -p deer-flow-dev -f "$REPO_ROOT/docker/docker-compose-dev.yaml")

mkdir -p "$PID_DIR" "$REPO_ROOT/logs"

stack_is_running() {
  curl -sf http://127.0.0.1:2027/api/health/external-services >/dev/null 2>&1 || return 1
  curl -Is http://127.0.0.1:2027/workspace/chats/new >/dev/null 2>&1 || return 1
  local running_services
  running_services="$("${DOCKER_COMPOSE_CMD[@]}" ps --status running --services 2>/dev/null || true)"
  grep -qx "langgraph" <<<"$running_services" || return 1
  grep -qx "langgraph-postgres" <<<"$running_services" || return 1
  grep -qx "gateway" <<<"$running_services" || return 1
  grep -qx "frontend" <<<"$running_services" || return 1
  grep -qx "nginx" <<<"$running_services" || return 1
}

start_daemon() {
  if stack_is_running; then
    echo "MaestroFlow detached stack is already running."
    exit 0
  fi

  # The split-port local detached stack owns the same public port; tear it down first.
  "$REPO_ROOT/scripts/local-daemon.sh" stop >/dev/null 2>&1 || true

  cd "$REPO_ROOT"
  export DEER_FLOW_ROOT="${DEER_FLOW_ROOT:-$REPO_ROOT}"
  : >"$SUPERVISOR_LOG"
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -oL -eL "$REPO_ROOT/scripts/docker.sh" start >>"$SUPERVISOR_LOG" 2>&1
  else
    "$REPO_ROOT/scripts/docker.sh" start >>"$SUPERVISOR_LOG" 2>&1
  fi

  local attempts=0
  local max_attempts=120
  while (( attempts < max_attempts )); do
    if stack_is_running; then
      echo "MaestroFlow detached stack started."
      echo "Log: $SUPERVISOR_LOG"
      return 0
    fi
    sleep 1
    attempts=$((attempts + 1))
  done

  echo "Failed to start MaestroFlow detached stack."
  echo "See $SUPERVISOR_LOG"
  tail -n 80 "$SUPERVISOR_LOG" || true
  exit 1
}

stop_daemon() {
  cd "$REPO_ROOT"
  export DEER_FLOW_ROOT="${DEER_FLOW_ROOT:-$REPO_ROOT}"
  "$REPO_ROOT/scripts/docker.sh" stop >/dev/null
  echo "MaestroFlow detached supervisor stopped."
}

status_daemon() {
  if stack_is_running; then
    echo "running"
  else
    echo "stopped"
    return 1
  fi
}

case "${1:-}" in
  start)
    start_daemon
    ;;
  stop)
    stop_daemon
    ;;
  restart)
    stop_daemon
    start_daemon
    ;;
  status)
    status_daemon
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
