#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_CMD=(docker compose -p deer-flow-dev -f "$REPO_ROOT/docker/docker-compose-dev.yaml")

# shellcheck source=/dev/null
source "$SCRIPT_DIR/dev-ports.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

failures=0
warnings=0
MODE="auto"

case "${1:-}" in
    "")
        ;;
    --mode)
        MODE="${2:-auto}"
        ;;
    auto|local|docker)
        MODE="$1"
        ;;
    *)
        echo -e "${RED}Unknown mode '${1}'. Use auto, local, docker, or --mode <value>.${NC}"
        exit 1
        ;;
esac

docker_core_running() {
    local running_services

    if ! command -v docker >/dev/null 2>&1; then
        return 1
    fi

    running_services="$(
        DEER_FLOW_ROOT="${DEER_FLOW_ROOT:-$REPO_ROOT}" "${DOCKER_COMPOSE_CMD[@]}" ps --status running --services 2>/dev/null || true
    )"

    grep -qx "frontend" <<<"$running_services" || return 1
    grep -qx "gateway" <<<"$running_services" || return 1
    grep -qx "nginx" <<<"$running_services" || return 1
    grep -qx "langgraph" <<<"$running_services" || return 1
    grep -qx "langgraph-postgres" <<<"$running_services" || return 1
}

port_summary() {
    local port="$1"
    local listeners
    listeners=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $1 " (pid " $2 ", " $9 ")"}' | sort -u)
    if [ -n "$listeners" ]; then
        printf '%s' "$listeners" | paste -sd '; ' -
    else
        printf 'free'
    fi
}

check_listener_pattern() {
    local label="$1"
    local port="$2"
    local pattern="$3"
    local strict="${4:-warn}"
    local summary

    summary=$(port_summary "$port")
    if [ "$summary" = "free" ]; then
        echo -e "  ${BLUE}•${NC} $label ($port): free"
        return
    fi

    if printf '%s' "$summary" | grep -Eiq "$pattern"; then
        echo -e "  ${GREEN}•${NC} $label ($port): $summary"
        return
    fi

    if [ "$strict" = "fail" ]; then
        echo -e "  ${RED}•${NC} $label ($port): occupied by unexpected listener -> $summary"
        failures=$((failures + 1))
    else
        echo -e "  ${YELLOW}•${NC} $label ($port): occupied by unexpected listener -> $summary"
        warnings=$((warnings + 1))
    fi
}

check_docker_service() {
    local service="$1"
    local running_services

    running_services="$(
        DEER_FLOW_ROOT="${DEER_FLOW_ROOT:-$REPO_ROOT}" "${DOCKER_COMPOSE_CMD[@]}" ps --status running --services 2>/dev/null || true
    )"

    if grep -qx "$service" <<<"$running_services"; then
        echo -e "  ${GREEN}•${NC} Docker service '$service' running"
    else
        echo -e "  ${RED}•${NC} Docker service '$service' not running"
        failures=$((failures + 1))
    fi
}

check_frontend_env() {
    local env_file="$REPO_ROOT/frontend/.env"
    local backend_line=""
    local langgraph_line=""

    if [ ! -f "$env_file" ]; then
        echo -e "  ${YELLOW}•${NC} frontend/.env: missing"
        warnings=$((warnings + 1))
        return
    fi

    backend_line=$(grep -E '^NEXT_PUBLIC_BACKEND_BASE_URL=' "$env_file" || true)
    langgraph_line=$(grep -E '^NEXT_PUBLIC_LANGGRAPH_BASE_URL=' "$env_file" || true)

    if [ -z "$backend_line" ] && [ -z "$langgraph_line" ]; then
        echo -e "  ${GREEN}•${NC} frontend/.env: proxy mode (backend URLs unset)"
        return
    fi

    if [ -n "$backend_line" ] && ! printf '%s' "$backend_line" | grep -Eq '127\.0\.0\.1:8001|localhost:8001'; then
        echo -e "  ${RED}•${NC} frontend/.env backend URL drifts from local policy -> $backend_line"
        failures=$((failures + 1))
    else
        echo -e "  ${GREEN}•${NC} frontend/.env backend URL aligned"
    fi

    if [ -n "$langgraph_line" ] && ! printf '%s' "$langgraph_line" | grep -Eq '127\.0\.0\.1:2024|localhost:2024|127\.0\.0\.1:2027/api/langgraph|localhost:2027/api/langgraph'; then
        echo -e "  ${RED}•${NC} frontend/.env LangGraph URL drifts from local policy -> $langgraph_line"
        failures=$((failures + 1))
    else
        echo -e "  ${GREEN}•${NC} frontend/.env LangGraph URL aligned"
    fi
}

check_url() {
    local label="$1"
    local url="$2"
    local strict="${3:-warn}"

    if curl -fsS -o /dev/null --max-time 2 "$url"; then
        echo -e "  ${GREEN}•${NC} $label reachable -> $url"
        return
    fi

    if [ "$strict" = "fail" ]; then
        echo -e "  ${RED}•${NC} $label unreachable -> $url"
        failures=$((failures + 1))
    else
        echo -e "  ${YELLOW}•${NC} $label unreachable -> $url"
        warnings=$((warnings + 1))
    fi
}

echo "=========================================="
echo "  MaestroFlow Dev Port Doctor"
echo "=========================================="
echo ""

if [ "$MODE" = "auto" ]; then
    if docker_core_running; then
        MODE="docker"
    else
        MODE="local"
    fi
fi

if [ "$MODE" != "local" ] && [ "$MODE" != "docker" ]; then
    echo -e "${RED}Unknown mode '$MODE'. Use auto, local, docker, or --mode <value>.${NC}"
    exit 1
fi

echo "Mode: $MODE"
echo ""
echo "Canonical local ports:"
echo "  app       http://${MAESTROFLOW_PUBLIC_HOST}:${MAESTROFLOW_PUBLIC_PORT}"
echo "  frontend  http://${MAESTROFLOW_FRONTEND_HOST}:${MAESTROFLOW_FRONTEND_PORT}"
echo "  gateway   http://${MAESTROFLOW_GATEWAY_HOST}:${MAESTROFLOW_GATEWAY_PORT}"
echo "  langgraph http://${MAESTROFLOW_LANGGRAPH_HOST}:${MAESTROFLOW_LANGGRAPH_PORT}"
echo "  langfuse  http://${MAESTROFLOW_LANGFUSE_HOST}:${MAESTROFLOW_LANGFUSE_PORT}"
echo ""

if [ "$MODE" = "local" ]; then
    echo "Listener status:"
    check_listener_pattern "Public app" "$MAESTROFLOW_PUBLIC_PORT" 'nginx'
    check_listener_pattern "Frontend" "$MAESTROFLOW_FRONTEND_PORT" 'node'
    check_listener_pattern "Gateway" "$MAESTROFLOW_GATEWAY_PORT" 'python|uvicorn'
    check_listener_pattern "LangGraph" "$MAESTROFLOW_LANGGRAPH_PORT" 'docker|com\.docke|com\.docker|vpnkit|qemu|langgraph'
    check_listener_pattern "Langfuse" "$MAESTROFLOW_LANGFUSE_PORT" 'docker|com\.docke|com\.docker|node|langfuse'
    echo ""
    echo "Config drift:"
    check_frontend_env
    echo ""
    echo "Reachability:"
    check_url "Public app" "http://${MAESTROFLOW_PUBLIC_HOST}:${MAESTROFLOW_PUBLIC_PORT}/"
    check_url "Gateway health" "http://${MAESTROFLOW_GATEWAY_HOST}:${MAESTROFLOW_GATEWAY_PORT}/docs"
    check_url "LangGraph root" "http://${MAESTROFLOW_LANGGRAPH_HOST}:${MAESTROFLOW_LANGGRAPH_PORT}/ok"
    check_url "Langfuse" "http://${MAESTROFLOW_LANGFUSE_HOST}:${MAESTROFLOW_LANGFUSE_PORT}"
else
    echo "Docker services:"
    check_docker_service "frontend"
    check_docker_service "gateway"
    check_docker_service "nginx"
    check_docker_service "langgraph"
    check_docker_service "langgraph-postgres"
    echo ""
    echo "Listener status:"
    check_listener_pattern "Public app" "$MAESTROFLOW_PUBLIC_PORT" 'docker|com\.docke|com\.docker|nginx'
    check_listener_pattern "LangGraph" "$MAESTROFLOW_LANGGRAPH_PORT" 'docker|com\.docke|com\.docker|vpnkit|qemu|langgraph'
    check_listener_pattern "Langfuse" "$MAESTROFLOW_LANGFUSE_PORT" 'docker|com\.docke|com\.docker|node|langfuse'
    echo ""
    echo "Frontend config:"
    check_frontend_env
    echo ""
    echo "Reachability:"
    check_url "Public app" "http://${MAESTROFLOW_PUBLIC_HOST}:${MAESTROFLOW_PUBLIC_PORT}/"
    check_url "Gateway via public app" "http://${MAESTROFLOW_PUBLIC_HOST}:${MAESTROFLOW_PUBLIC_PORT}/api/health/external-services"
    check_url "LangGraph root" "http://${MAESTROFLOW_LANGGRAPH_HOST}:${MAESTROFLOW_LANGGRAPH_PORT}/ok"
    check_url "Langfuse" "http://${MAESTROFLOW_LANGFUSE_HOST}:${MAESTROFLOW_LANGFUSE_PORT}"
fi

echo ""

if [ "$failures" -gt 0 ]; then
    echo -e "${RED}Doctor found ${failures} blocking issue(s) and ${warnings} warning(s).${NC}"
    exit 1
fi

if [ "$warnings" -gt 0 ]; then
    echo -e "${YELLOW}Doctor found ${warnings} warning(s), but no blocking issues.${NC}"
    exit 0
fi

echo -e "${GREEN}Ports, URLs, and local frontend config are aligned.${NC}"
