#!/usr/bin/env bash

# Shared topology detection and reporting for MaestroFlow local development.

# shellcheck disable=SC2034
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/dev-ports.sh"

DOCKER_COMPOSE_CMD=("${DOCKER_COMPOSE_CMD[@]:-docker compose -p deer-flow-dev -f $REPO_ROOT/docker/docker-compose-dev.yaml}")

listener_pid() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true
}

listener_command() {
  local port="$1"
  local pid
  pid="$(listener_pid "$port")"
  if [ -n "$pid" ]; then
    ps -p "$pid" -o command= 2>/dev/null || true
  fi
}

port_is_listening() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1
}

port_summary_line() {
  local label="$1"
  local port="$2"
  local pid cmd
  pid="$(listener_pid "$port")"
  cmd="$(listener_command "$port")"
  if [ -n "$pid" ]; then
    printf "  %-12s : %s (%s)\n" "$label" ":$port" "${cmd:-pid $pid}"
  else
    printf "  %-12s : %s (stopped)\n" "$label" ":$port"
  fi
}

docker_services_running() {
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    return 1
  fi
  docker compose -p deer-flow-dev -f "$REPO_ROOT/docker/docker-compose-dev.yaml" ps --status running --services 2>/dev/null || true
}

detect_dev_runtime_mode() {
  local has_public=0 has_frontend=0 has_gateway=0 has_langgraph=0
  local services

  port_is_listening "$MAESTROFLOW_PUBLIC_PORT" && has_public=1
  port_is_listening "$MAESTROFLOW_FRONTEND_PORT" && has_frontend=1
  port_is_listening "$MAESTROFLOW_GATEWAY_PORT" && has_gateway=1
  port_is_listening "$MAESTROFLOW_LANGGRAPH_PORT" && has_langgraph=1

  services="$(docker_services_running)"

  if [ "$has_public" -eq 1 ] && grep -qx "frontend" <<<"$services" && grep -qx "gateway" <<<"$services" && grep -qx "nginx" <<<"$services"; then
    echo "docker-detached"
    return
  fi

  if [ "$has_public" -eq 1 ] && [ "$has_frontend" -eq 1 ] && [ "$has_gateway" -eq 1 ] && [ "$has_langgraph" -eq 1 ]; then
    echo "local-detached"
    return
  fi

  if [ "$has_public" -eq 0 ] && [ "$has_frontend" -eq 1 ] && [ "$has_gateway" -eq 0 ]; then
    echo "frontend-only"
    return
  fi

  if [ "$has_public" -eq 0 ] && [ "$has_frontend" -eq 1 ] && [ "$has_gateway" -eq 1 ]; then
    echo "frontend-direct"
    return
  fi

  if [ "$has_public" -eq 0 ] && [ "$has_frontend" -eq 0 ] && [ "$has_gateway" -eq 0 ] && [ "$has_langgraph" -eq 0 ]; then
    echo "stopped"
    return
  fi

  echo "mixed"
}

print_dev_topology() {
  local mode="$1"
  printf "Mode           : %s\n" "$mode"
  printf "Frontend mode  : %s\n" "${MAESTROFLOW_FRONTEND_RUNTIME_MODE:-app}"
  printf "Public app     : http://%s:%s\n" "$MAESTROFLOW_PUBLIC_HOST" "$MAESTROFLOW_PUBLIC_PORT"
  printf "Frontend direct: http://%s:%s\n" "$MAESTROFLOW_FRONTEND_HOST" "$MAESTROFLOW_FRONTEND_PORT"
  printf "Gateway direct : http://%s:%s\n" "$MAESTROFLOW_GATEWAY_HOST" "$MAESTROFLOW_GATEWAY_PORT"
  printf "LangGraph      : http://%s:%s\n" "$MAESTROFLOW_LANGGRAPH_HOST" "$MAESTROFLOW_LANGGRAPH_PORT"
  echo "Listeners:"
  port_summary_line "public" "$MAESTROFLOW_PUBLIC_PORT"
  port_summary_line "frontend" "$MAESTROFLOW_FRONTEND_PORT"
  port_summary_line "gateway" "$MAESTROFLOW_GATEWAY_PORT"
  port_summary_line "langgraph" "$MAESTROFLOW_LANGGRAPH_PORT"
}

warn_if_mixed_topology() {
  local mode="$1"
  if [ "$mode" = "mixed" ]; then
    echo "⚠ Mixed local topology detected." >&2
    echo "  The app is being served by overlapping launch modes. Cleanup is recommended before debugging." >&2
  fi
}

kill_process_on_port_if_matches() {
  local port="$1"
  local pattern="$2"
  local pid cmd
  pid="$(listener_pid "$port")"
  cmd="$(listener_command "$port")"
  if [ -n "$pid" ] && [[ "${cmd:-}" =~ $pattern ]]; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
}

cleanup_conflicting_local_processes() {
  local mode
  mode="$(detect_dev_runtime_mode)"
  warn_if_mixed_topology "$mode"

  # Clean up stray repo-owned local services that survive outside the blessed launchers.
  kill_process_on_port_if_matches "$MAESTROFLOW_FRONTEND_PORT" "next.*/next (dev|start)"
  kill_process_on_port_if_matches 3000 "next.*/next (dev|start)"
  kill_process_on_port_if_matches "$MAESTROFLOW_GATEWAY_PORT" "uvicorn .*src.gateway.app:app"
  kill_process_on_port_if_matches "$MAESTROFLOW_PUBLIC_PORT" "nginx.*nginx.local.conf"
}
