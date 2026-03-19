#!/usr/bin/env bash
#
# start.sh - Start all MaestroFlow development services
#
# Must be run from the repo root directory.

set -e
trap '' HUP

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/dev-ports.sh"
export DEER_FLOW_ROOT="${DEER_FLOW_ROOT:-$REPO_ROOT}"
DOCKER_COMPOSE_CMD=(docker compose -p deer-flow-dev -f "$REPO_ROOT/docker/docker-compose-dev.yaml")
LANGGRAPH_POSTGRES_URL_DEFAULT="postgresql://postgres:postgres@127.0.0.1:55434/maestroflow_langgraph_v2"
NGINX_PID_FILE="$REPO_ROOT/logs/nginx.pid"

# ── Helpers ───────────────────────────────────────────────────────────────────

# Kill every process currently listening on a given port (force-frees the port)
free_port() {
    local port="$1"
    local pids
    pids=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        # Wait up to 3s for the port to actually release
        local i=0
        while lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1 && [ $i -lt 30 ]; do
            sleep 0.1
            i=$((i + 1))
        done
    fi
}

# Stop nginx cleanly via pid file, then force-kill stragglers
stop_nginx() {
    if [ -f "$NGINX_PID_FILE" ]; then
        local pid
        pid=$(cat "$NGINX_PID_FILE" 2>/dev/null || true)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            nginx -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" -s quit 2>/dev/null || true
            sleep 1
        fi
        rm -f "$NGINX_PID_FILE"
    fi
    # Kill any remaining nginx master/workers regardless
    pkill -9 -f "nginx.*nginx.local.conf" 2>/dev/null || true
    pkill -9 nginx 2>/dev/null || true
    free_port "$MAESTROFLOW_PUBLIC_PORT"
}

# Kill all locally managed services and free their ports
stop_all_services() {
    # Gateway
    pkill -f "uvicorn src.gateway.app:app" 2>/dev/null || true
    free_port "$MAESTROFLOW_GATEWAY_PORT"

    # Frontend (matches pnpm/next processes on the canonical local port)
    pkill -f "next dev.*--port $MAESTROFLOW_FRONTEND_PORT" 2>/dev/null || true
    pkill -f "next dev.*$MAESTROFLOW_FRONTEND_PORT" 2>/dev/null || true
    pkill -f "pnpm.*next dev" 2>/dev/null || true
    free_port "$MAESTROFLOW_FRONTEND_PORT"

    # Nginx
    stop_nginx

    # Sandbox containers
    ./scripts/cleanup-containers.sh deer-flow-sandbox 2>/dev/null || true
}

stop_langgraph_runtime() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        "${DOCKER_COMPOSE_CMD[@]}" stop langgraph langgraph-redis langgraph-postgres >/dev/null 2>&1 || true
    fi
}

prewarm_routes() {
    local base_url="http://${MAESTROFLOW_PUBLIC_HOST}:${MAESTROFLOW_PUBLIC_PORT}"
    local routes=(
        "/workspace/chats"
        "/workspace/composer"
    )

    echo "Prewarming key routes..."
    for route in "${routes[@]}"; do
        curl -fsS --max-time 45 "${base_url}${route}" >/dev/null 2>&1 || true
    done
}

# Wait for Docker daemon to be ready (up to $1 seconds)
wait_for_docker() {
    local max="${1:-30}"
    local i=0
    printf "  Waiting for Docker daemon..."
    while ! docker info >/dev/null 2>&1; do
        if [ $i -ge "$max" ]; then
            echo ""
            echo "✗ Docker daemon not ready after ${max}s. Is Docker Desktop running?"
            exit 1
        fi
        printf "."
        sleep 1
        i=$((i + 1))
    done
    printf "\r  %-60s\r" ""
}

ensure_langgraph_runtime() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "✗ Docker is required for the optimized LangGraph runtime."
        exit 1
    fi

    wait_for_docker 30

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

# ── Stop existing services ────────────────────────────────────────────────────

echo "Stopping existing services if any..."
stop_all_services
stop_langgraph_runtime
# Extra pause to let OS release ports fully
sleep 1

# ── Config check ─────────────────────────────────────────────────────────────

if ! { \
        [ -n "$DEER_FLOW_CONFIG_PATH" ] && [ -f "$DEER_FLOW_CONFIG_PATH" ] || \
        [ -f backend/config.yaml ] || \
        [ -f config.yaml ]; \
    }; then
    echo "✗ No MaestroFlow config file found."
    echo "  Checked these locations:"
    echo "    - $DEER_FLOW_CONFIG_PATH (when DEER_FLOW_CONFIG_PATH is set)"
    echo "    - backend/config.yaml"
    echo "    - ./config.yaml"
    echo ""
    echo "  Run 'make config' from the repo root to generate ./config.yaml"
    exit 1
fi

# ── Pre-flight port check ─────────────────────────────────────────────────────

for port in "$MAESTROFLOW_GATEWAY_PORT" "$MAESTROFLOW_FRONTEND_PORT" "$MAESTROFLOW_PUBLIC_PORT"; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "  ⚠ Port $port still in use after cleanup — force-freeing..."
        free_port "$port"
    fi
done

# ── Cleanup trap ─────────────────────────────────────────────────────────────

cleanup() {
    trap - INT TERM
    echo ""
    echo "Shutting down services..."
    stop_all_services
    stop_langgraph_runtime
    echo "✓ All services stopped"
    exit 0
}
trap cleanup INT TERM

# ── Banner ────────────────────────────────────────────────────────────────────

echo ""
echo "=========================================="
echo "  Starting MaestroFlow Development Server"
echo "=========================================="
echo ""
echo "Services starting up..."
echo "  → Backend: LangGraph + Gateway"
echo "  → Frontend: Next.js"
echo "  → Nginx: Reverse Proxy"
echo ""

# ── Start services ────────────────────────────────────────────────────────────

mkdir -p logs
mkdir -p .cache/uv
export XDG_CACHE_HOME="$REPO_ROOT/.cache"
export UV_CACHE_DIR="$REPO_ROOT/.cache/uv"
export HOST=127.0.0.1
export HOSTNAME=127.0.0.1
export LANGGRAPH_CHECKPOINTER_URL="${LANGGRAPH_CHECKPOINTER_URL:-$LANGGRAPH_POSTGRES_URL_DEFAULT}"
export BG_JOB_ISOLATED_LOOPS="${BG_JOB_ISOLATED_LOOPS:-true}"

echo "Starting LangGraph server..."
ensure_langgraph_runtime
./scripts/wait-for-port.sh "$MAESTROFLOW_LANGGRAPH_PORT" 60 "LangGraph" || {
    echo "  See logs/langgraph.log for details"
    tail -20 logs/langgraph.log 2>/dev/null || true
    cleanup
}
echo "✓ LangGraph server started on localhost:$MAESTROFLOW_LANGGRAPH_PORT (Docker)"

echo "Starting Gateway API..."
(cd backend && exec uv run uvicorn src.gateway.app:app --host 0.0.0.0 --port "$MAESTROFLOW_GATEWAY_PORT" > ../logs/gateway.log 2>&1) &
GATEWAY_PID=$!
./scripts/wait-for-port.sh "$MAESTROFLOW_GATEWAY_PORT" 30 "Gateway API" || {
    echo "✗ Gateway API failed to start. Last log output:"
    tail -60 logs/gateway.log
    echo ""
    grep -E "Failed to load configuration|Environment variable .* not found|config\.yaml.*not found" logs/gateway.log | tail -5 || true
    cleanup
}
echo "✓ Gateway API started on localhost:$MAESTROFLOW_GATEWAY_PORT"

echo "Starting Frontend..."
(cd frontend && exec pnpm exec next dev --turbopack --hostname "$MAESTROFLOW_FRONTEND_HOST" --port "$MAESTROFLOW_FRONTEND_PORT" > ../logs/frontend.log 2>&1) &
FRONTEND_PID=$!
./scripts/wait-for-port.sh "$MAESTROFLOW_FRONTEND_PORT" 120 "Frontend" || {
    echo "  See logs/frontend.log for details"
    tail -20 logs/frontend.log
    cleanup
}
echo "✓ Frontend started on ${MAESTROFLOW_FRONTEND_HOST}:$MAESTROFLOW_FRONTEND_PORT"

echo "Starting Nginx reverse proxy..."
nginx -g "daemon off; pid $NGINX_PID_FILE;" \
    -c "$REPO_ROOT/docker/nginx/nginx.local.conf" \
    -p "$REPO_ROOT" \
    > logs/nginx.log 2>&1 &
NGINX_PID=$!
./scripts/wait-for-port.sh "$MAESTROFLOW_PUBLIC_PORT" 10 "Nginx" || {
    echo "  See logs/nginx.log for details"
    tail -10 logs/nginx.log
    cleanup
}
echo "✓ Nginx started on localhost:$MAESTROFLOW_PUBLIC_PORT"

# ── Ready ─────────────────────────────────────────────────────────────────────

echo ""
echo "=========================================="
echo "  MaestroFlow is ready!"
echo "=========================================="
echo ""
echo "  🌐 Application: http://localhost:$MAESTROFLOW_PUBLIC_PORT"
echo "  📡 API Gateway: http://localhost:$MAESTROFLOW_PUBLIC_PORT/api/*"
echo "  🤖 LangGraph:   http://localhost:$MAESTROFLOW_PUBLIC_PORT/api/langgraph/*"
echo ""
echo "  📋 Logs:"
echo "     - LangGraph: logs/langgraph.log"
echo "     - Gateway:   logs/gateway.log"
echo "     - Frontend:  logs/frontend.log"
echo "     - Nginx:     logs/nginx.log"
echo ""
prewarm_routes
echo "Press Ctrl+C to stop all services"
echo ""

wait "$GATEWAY_PID" "$FRONTEND_PID" "$NGINX_PID"
