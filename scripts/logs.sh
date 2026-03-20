#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose-dev.yaml"
USE_LNAV=0

# shellcheck source=/dev/null
source "$ROOT_DIR/scripts/dev-topology.sh"

if [[ "${1:-}" == "--lnav" ]]; then
  USE_LNAV=1
  shift
fi

run_pipe() {
  if [[ $USE_LNAV -eq 1 ]]; then
    if ! command -v lnav >/dev/null 2>&1; then
      echo "lnav is not installed. Install it first, or run without --lnav." >&2
      exit 1
    fi
    cat | lnav -
  else
    cat
  fi
}

tail_local_logs() {
  local files=(
    "$ROOT_DIR/logs/frontend.log"
    "$ROOT_DIR/logs/gateway.log"
    "$ROOT_DIR/logs/nginx.log"
    "$ROOT_DIR/logs/langgraph.log"
  )

  local existing=()
  local file
  for file in "${files[@]}"; do
    if [[ -f "$file" ]]; then
      existing+=("$file")
    fi
  done

  if [[ ${#existing[@]} -eq 0 ]]; then
    echo "No local log files found under $ROOT_DIR/logs" >&2
    exit 1
  fi

  tail -n 200 -F "${existing[@]}"
}

tail_docker_logs() {
  local services=("$@")
  if [[ ${#services[@]} -eq 0 ]]; then
    services=(nginx frontend gateway langgraph)
  fi
  docker compose -f "$COMPOSE_FILE" -p deer-flow-dev logs --no-color -f --tail=200 "${services[@]}"
}

tail_mixed_logs() {
  {
    echo "===== Local file logs ====="
    tail_local_logs &
    local local_pid=$!

    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
      echo "===== Docker service logs ====="
      tail_docker_logs langgraph langgraph-postgres langgraph-redis &
      local docker_pid=$!
      wait "$local_pid" "$docker_pid"
    else
      wait "$local_pid"
    fi
  }
}

MODE="$(detect_dev_runtime_mode)"
echo "MaestroFlow log mode: $MODE"
print_dev_topology "$MODE"
echo ""

case "$MODE" in
  local-detached|foreground-local|frontend-direct|frontend-only)
    tail_local_logs | run_pipe
    ;;
  docker-detached)
    tail_docker_logs "$@" | run_pipe
    ;;
  mixed)
    tail_mixed_logs | run_pipe
    ;;
  stopped)
    echo "The MaestroFlow app stack is not running." >&2
    exit 1
    ;;
  *)
    tail_mixed_logs | run_pipe
    ;;
esac
