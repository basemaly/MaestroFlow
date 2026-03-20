#!/usr/bin/env bash
#
# local-daemon.sh - Detached supervisor for the split-port local dev stack.
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$REPO_ROOT/.run/local"
LOG_DIR="$REPO_ROOT/logs"
SUPERVISOR_LOG="$LOG_DIR/local-supervisor.log"
DOCKER_COMPOSE_CMD=(docker compose -p deer-flow-dev -f "$REPO_ROOT/docker/docker-compose-dev.yaml")
LANGGRAPH_POSTGRES_URL_DEFAULT="postgresql://postgres:postgres@127.0.0.1:55434/maestroflow_langgraph_v2"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/dev-ports.sh"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/dev-topology.sh"

mkdir -p "$PID_DIR" "$LOG_DIR"
export DEER_FLOW_ROOT="${DEER_FLOW_ROOT:-$REPO_ROOT}"

pid_file_for() {
  printf '%s/%s.pid' "$PID_DIR" "$1"
}

read_pid() {
  local name="$1"
  local file
  file="$(pid_file_for "$name")"
  if [ -f "$file" ]; then
    cat "$file"
  fi
}

is_pid_running() {
  local pid="${1:-}"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

write_pid() {
  local name="$1"
  local pid="$2"
  printf '%s\n' "$pid" >"$(pid_file_for "$name")"
}

remove_pid() {
  local name="$1"
  rm -f "$(pid_file_for "$name")"
}

wait_for_port() {
  local port="$1"
  local label="$2"
  local attempts="${3:-60}"
  local i=0
  while (( i < attempts )); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  echo "Timed out waiting for $label on port $port" >>"$SUPERVISOR_LOG"
  return 1
}

wait_for_port_free() {
  local port="$1"
  local label="$2"
  local attempts="${3:-60}"
  local i=0
  while (( i < attempts )); do
    if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  echo "Timed out waiting for $label on port $port to be released" >>"$SUPERVISOR_LOG"
  return 1
}

prewarm_local_routes() {
  local base_url="http://${MAESTROFLOW_PUBLIC_HOST}:${MAESTROFLOW_PUBLIC_PORT}"
  local routes=(
    "/workspace/chats"
    "/workspace/composer"
  )

  for route in "${routes[@]}"; do
    curl -fsS --max-time 45 "${base_url}${route}" >/dev/null 2>&1 || true
  done
}

start_langgraph_runtime() {
  export LANGGRAPH_CHECKPOINTER_URL="${LANGGRAPH_CHECKPOINTER_URL:-$LANGGRAPH_POSTGRES_URL_DEFAULT}"
  export BG_JOB_ISOLATED_LOOPS="${BG_JOB_ISOLATED_LOOPS:-true}"
  "${DOCKER_COMPOSE_CMD[@]}" up -d langgraph-postgres langgraph-redis >/dev/null
  until docker exec deer-flow-langgraph-postgres pg_isready -U postgres >/dev/null 2>&1; do
    sleep 1
  done
  docker exec deer-flow-langgraph-postgres psql -U postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname = 'maestroflow_langgraph_v2'" | grep -q 1 \
    || docker exec deer-flow-langgraph-postgres createdb -U postgres maestroflow_langgraph_v2
  "${DOCKER_COMPOSE_CMD[@]}" up -d langgraph >/dev/null
}

stop_langgraph_runtime() {
  "${DOCKER_COMPOSE_CMD[@]}" stop langgraph langgraph-redis langgraph-postgres >/dev/null 2>&1 || true
}

stop_pid_process() {
  local name="$1"
  local pid
  pid="$(read_pid "$name")"
  if is_pid_running "$pid"; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if is_pid_running "$pid"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  remove_pid "$name"

  if [ "$name" = "frontend" ]; then
    pkill -f "next dev.*--port $MAESTROFLOW_FRONTEND_PORT" 2>/dev/null || true
    pkill -f "next dev.*$MAESTROFLOW_FRONTEND_PORT" 2>/dev/null || true
    pkill -f "pnpm.*next dev" 2>/dev/null || true
  elif [ "$name" = "gateway" ]; then
    pkill -f "uvicorn src.gateway.app:app" 2>/dev/null || true
  fi
}

stop_nginx() {
  if [ -f "$REPO_ROOT/logs/nginx.pid" ]; then
    nginx -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" -s quit 2>/dev/null || true
    sleep 1
  fi
  pkill -9 -f "nginx.*nginx.local.conf" 2>/dev/null || true
  pkill -9 nginx 2>/dev/null || true
  rm -f "$REPO_ROOT/logs/nginx.pid"
}

local_stack_is_running() {
  curl -sf "http://${MAESTROFLOW_PUBLIC_HOST}:${MAESTROFLOW_PUBLIC_PORT}/api/health/external-services" >/dev/null 2>&1 || return 1
  curl -sf "http://${MAESTROFLOW_PUBLIC_HOST}:${MAESTROFLOW_PUBLIC_PORT}/workspace/chats" >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"$MAESTROFLOW_GATEWAY_PORT" -sTCP:LISTEN -t >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"$MAESTROFLOW_FRONTEND_PORT" -sTCP:LISTEN -t >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"$MAESTROFLOW_PUBLIC_PORT" -sTCP:LISTEN -t >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"$MAESTROFLOW_LANGGRAPH_PORT" -sTCP:LISTEN -t >/dev/null 2>&1 || return 1
}

start_gateway() {
  (
    cd "$REPO_ROOT/backend"
    export XDG_CACHE_HOME="$REPO_ROOT/.cache"
    export UV_CACHE_DIR="$REPO_ROOT/.cache/uv"
    set -a
    source "$REPO_ROOT/.env"
    export LANGGRAPH_CHECKPOINTER_URL="${LANGGRAPH_CHECKPOINTER_URL:-$LANGGRAPH_POSTGRES_URL_DEFAULT}"
    export BG_JOB_ISOLATED_LOOPS="${BG_JOB_ISOLATED_LOOPS:-true}"
    set +a
    exec "$REPO_ROOT/backend/.venv/bin/uvicorn" src.gateway.app:app --host 0.0.0.0 --port "$MAESTROFLOW_GATEWAY_PORT" >>"$REPO_ROOT/logs/gateway.log" 2>&1
  ) &
  write_pid gateway "$!"
}

start_frontend() {
  (
    cd "$REPO_ROOT/frontend"
    exec pnpm exec next dev --turbopack --hostname "$MAESTROFLOW_FRONTEND_HOST" --port "$MAESTROFLOW_FRONTEND_PORT" >>"$REPO_ROOT/logs/frontend.log" 2>&1
  ) &
  write_pid frontend "$!"
}

start_nginx() {
  nginx -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT"
}

start_local_daemon() {
  local mode
  mode="$(detect_dev_runtime_mode)"
  if local_stack_is_running; then
    echo "MaestroFlow local detached stack is already running."
    print_dev_topology "local-detached"
    exit 0
  fi

  : >"$SUPERVISOR_LOG"
  echo "Starting MaestroFlow local detached stack..." >>"$SUPERVISOR_LOG"
  echo "Preflight topology:" >>"$SUPERVISOR_LOG"
  {
    print_dev_topology "$mode"
  } >>"$SUPERVISOR_LOG"

  # The Docker-backed detached stack owns the same public port; tear it down first.
  "$REPO_ROOT/scripts/daemon.sh" stop >/dev/null 2>&1 || true
  cleanup_conflicting_local_processes
  stop_local_daemon >/dev/null 2>&1 || true
  "${DOCKER_COMPOSE_CMD[@]}" down >/dev/null 2>&1 || true
  docker rm -f deer-flow-nginx deer-flow-frontend deer-flow-gateway deer-flow-langgraph deer-flow-langgraph-postgres deer-flow-langgraph-redis >/dev/null 2>&1 || true
  wait_for_port_free "$MAESTROFLOW_PUBLIC_PORT" "public app" 45

  mkdir -p "$REPO_ROOT/.cache/uv"

  start_langgraph_runtime
  wait_for_port "$MAESTROFLOW_LANGGRAPH_PORT" "LangGraph" 60

  start_gateway
  wait_for_port "$MAESTROFLOW_GATEWAY_PORT" "Gateway" 45

  start_frontend
  wait_for_port "$MAESTROFLOW_FRONTEND_PORT" "Frontend" 120

  start_nginx
  wait_for_port "$MAESTROFLOW_PUBLIC_PORT" "Nginx" 15

  local attempts=0
  while (( attempts < 30 )); do
    if local_stack_is_running; then
      prewarm_local_routes
      echo "MaestroFlow local detached stack started."
      echo "Log: $SUPERVISOR_LOG"
      print_dev_topology "local-detached"
      return 0
    fi
    sleep 1
    attempts=$((attempts + 1))
  done

  echo "Failed to start MaestroFlow local detached stack."
  echo "See $SUPERVISOR_LOG"
  tail -n 80 "$SUPERVISOR_LOG" || true
  exit 1
}

stop_local_daemon() {
  stop_pid_process frontend
  stop_pid_process gateway
  stop_nginx
  stop_langgraph_runtime
  echo "MaestroFlow local detached supervisor stopped."
}

status_local_daemon() {
  local mode
  mode="$(detect_dev_runtime_mode)"
  if local_stack_is_running; then
    print_dev_topology "local-detached"
    return 0
  fi
  print_dev_topology "$mode"
  [ "$mode" != "stopped" ]
}

case "${1:-}" in
  start)
    start_local_daemon
    ;;
  stop)
    stop_local_daemon
    ;;
  restart)
    stop_local_daemon
    start_local_daemon
    ;;
  status)
    status_local_daemon
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
