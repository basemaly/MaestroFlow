#!/usr/bin/env bash
set -euo pipefail

MAESTROFLOW_ROOT="/Volumes/BA/DEV/MaestroFlow"
MAESTROSURF_ROOT="/Volumes/BA/DEV/MaestroSurf"
LITELLM_ROOT="/Volumes/BA/DEV/LiteLLM"
LANGFUSE_ROOT="/Volumes/BA/DEV/langfuse"

MAESTROSURF_COMPOSE_DIR="${MAESTROSURF_ROOT}/docker"
LANGFUSE_COMPOSE_FILE="${LANGFUSE_ROOT}/docker-compose.yml"
MAESTROFLOW_ENV_FILE="${MAESTROFLOW_ROOT}/.env"

LANGFUSE_URL="http://127.0.0.1:3000"
LITELLM_URL="http://127.0.0.1:4000"
LITELLM_MODELS_URL="${LITELLM_URL}/v1/models"
SURFSENSE_BACKEND_URL="http://127.0.0.1:8002/health"
SURFSENSE_FRONTEND_URL="http://127.0.0.1:3004"
MAESTROFLOW_URL="http://127.0.0.1:2027"
MAESTROFLOW_HEALTH_URL="${MAESTROFLOW_URL}/api/health/external-services"

action="${1:-status}"
force_build="false"

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || {
    echo "Missing required command: ${cmd}" >&2
    exit 1
  }
}

http_ok() {
  local url="$1"
  curl -fsS --max-time 5 "${url}" >/dev/null 2>&1
}

read_env_value() {
  local file="$1"
  local key="$2"
  [[ -f "${file}" ]] || return 1
  awk -F= -v key="${key}" '$1 == key {print substr($0, index($0, "=") + 1); exit}' "${file}"
}

litellm_ok() {
  local api_key header
  api_key="${LITELLM_PROXY_API_KEY:-}"
  if [[ -z "${api_key}" ]]; then
    api_key="$(read_env_value "${MAESTROFLOW_ENV_FILE}" "LITELLM_PROXY_API_KEY" || true)"
  fi
  if [[ -n "${api_key}" ]]; then
    header="Authorization: Bearer ${api_key}"
    curl -fsS --max-time 5 -H "${header}" "${LITELLM_MODELS_URL}" >/dev/null 2>&1
  else
    curl -fsS --max-time 5 "${LITELLM_MODELS_URL}" >/dev/null 2>&1
  fi
}

service_running() {
  local service="$1"
  case "${service}" in
    langfuse)
      http_ok "${LANGFUSE_URL}/api/public/health"
      ;;
    litellm)
      litellm_ok
      ;;
    surfsense)
      http_ok "${SURFSENSE_BACKEND_URL}" && http_ok "${SURFSENSE_FRONTEND_URL}"
      ;;
    maestroflow)
      http_ok "${MAESTROFLOW_HEALTH_URL}"
      ;;
    *)
      return 1
      ;;
  esac
}

wait_for_http() {
  local label="$1"
  local url="$2"
  local attempts="${3:-60}"
  local sleep_secs="${4:-2}"
  local i

  for i in $(seq 1 "${attempts}"); do
    if http_ok "${url}"; then
      return 0
    fi
    sleep "${sleep_secs}"
  done

  echo "${label} did not become ready at ${url}" >&2
  return 1
}

langfuse_start() {
  if service_running langfuse; then
    echo "Langfuse already running."
    return 0
  fi
  echo "Starting Langfuse..."
  docker compose -f "${LANGFUSE_COMPOSE_FILE}" up -d
  wait_for_http "Langfuse" "${LANGFUSE_URL}/api/public/health" 90 2
}

langfuse_stop() {
  echo "Stopping Langfuse..."
  docker compose -f "${LANGFUSE_COMPOSE_FILE}" down >/dev/null
}

langfuse_status() {
  if http_ok "${LANGFUSE_URL}/api/public/health"; then
    echo "langfuse=running"
  else
    echo "langfuse=stopped"
  fi
}

litellm_start() {
  if service_running litellm; then
    echo "LiteLLM already running."
    return 0
  fi
  echo "Starting LiteLLM..."
  (cd "${LITELLM_ROOT}" && ./scripts/litellm_stack.sh start)
  local i
  for i in $(seq 1 60); do
    if litellm_ok; then
      return 0
    fi
    sleep 2
  done
  echo "LiteLLM did not become ready at ${LITELLM_MODELS_URL}" >&2
  return 1
}

litellm_stop() {
  echo "Stopping LiteLLM..."
  (cd "${LITELLM_ROOT}" && ./scripts/litellm_stack.sh stop)
}

litellm_status() {
  local status
  status="$(cd "${LITELLM_ROOT}" && ./scripts/litellm_stack.sh status)"
  echo "litellm=${status}"
}

surfsense_start() {
  local compose_args=(up -d)

  if service_running surfsense && [[ "${force_build}" != "true" ]]; then
    echo "SurfSense already running."
    return 0
  fi

  if [[ "${force_build}" == "true" ]]; then
    compose_args+=(--build)
  fi

  echo "Starting SurfSense..."
  (
    cd "${MAESTROSURF_COMPOSE_DIR}"
    docker compose "${compose_args[@]}"
  )
  wait_for_http "SurfSense backend" "${SURFSENSE_BACKEND_URL}" 120 2
  wait_for_http "SurfSense frontend" "${SURFSENSE_FRONTEND_URL}" 120 2
}

surfsense_stop() {
  echo "Stopping SurfSense..."
  (
    cd "${MAESTROSURF_COMPOSE_DIR}"
    docker compose down >/dev/null
  )
}

surfsense_status() {
  local backend="stopped"
  local frontend="stopped"
  http_ok "${SURFSENSE_BACKEND_URL}" && backend="running"
  http_ok "${SURFSENSE_FRONTEND_URL}" && frontend="running"
  echo "surfsense_backend=${backend} surfsense_frontend=${frontend}"
}

maestroflow_start() {
  if service_running maestroflow; then
    echo "MaestroFlow already running."
    return 0
  fi
  echo "Starting MaestroFlow..."
  (cd "${MAESTROFLOW_ROOT}" && make dev-daemon)
  wait_for_http "MaestroFlow" "${MAESTROFLOW_HEALTH_URL}" 120 2
}

maestroflow_stop() {
  echo "Stopping MaestroFlow..."
  (cd "${MAESTROFLOW_ROOT}" && make daemon-stop >/dev/null)
}

maestroflow_status() {
  if http_ok "${MAESTROFLOW_HEALTH_URL}"; then
    echo "maestroflow=running"
    curl -fsS "${MAESTROFLOW_HEALTH_URL}"
    echo
  else
    echo "maestroflow=stopped"
  fi
}

stack_start() {
  require_cmd docker
  require_cmd curl
  langfuse_start
  litellm_start
  surfsense_start
  maestroflow_start
  echo ""
  echo "Full stack is ready:"
  echo "  MaestroFlow: ${MAESTROFLOW_URL}"
  echo "  SurfSense:   ${SURFSENSE_FRONTEND_URL}"
  echo "  Langfuse:    ${LANGFUSE_URL}"
  echo "  LiteLLM:     ${LITELLM_URL}"
}

stack_stop() {
  maestroflow_stop
  surfsense_stop
  litellm_stop
  langfuse_stop
}

stack_restart() {
  stack_stop
  stack_start
}

print_usage() {
  cat <<'EOF' >&2
Usage: maestro_stack.sh {up|down|restart|status|rebuild}

Commands:
  up       Fast path. Starts missing services and skips healthy ones.
  down     Stops the full stack.
  restart  Restarts the full stack.
  status   Shows stack status.
  rebuild  Rebuilds SurfSense images, then starts the full stack.

Compatibility aliases:
  start -> up
  stop  -> down
EOF
}

stack_status() {
  langfuse_status
  litellm_status
  surfsense_status
  maestroflow_status
}

case "${action}" in
  up|start)
    stack_start
    ;;
  down|stop)
    stack_stop
    ;;
  restart)
    stack_restart
    ;;
  rebuild)
    force_build="true"
    stack_start
    ;;
  status)
    stack_status
    ;;
  *)
    print_usage
    exit 1
    ;;
esac
