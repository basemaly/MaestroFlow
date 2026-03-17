#!/usr/bin/env bash
#
# start.sh - Start all MaestroFlow development services
#
# Must be run from the repo root directory.

set -e
trap '' HUP

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export DEER_FLOW_ROOT="${DEER_FLOW_ROOT:-$REPO_ROOT}"
DOCKER_COMPOSE_CMD=(docker compose -p deer-flow-dev -f "$REPO_ROOT/docker/docker-compose-dev.yaml")
LANGGRAPH_POSTGRES_URL_DEFAULT="postgresql://postgres:postgres@127.0.0.1:55434/maestroflow_langgraph_v2"

ensure_langgraph_runtime() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "✗ Docker is required for the optimized LangGraph runtime."
        exit 1
    fi

    export LANGGRAPH_CHECKPOINTER_URL="${LANGGRAPH_CHECKPOINTER_URL:-$LANGGRAPH_POSTGRES_URL_DEFAULT}"
    export BG_JOB_ISOLATED_LOOPS="${BG_JOB_ISOLATED_LOOPS:-true}"
    "${DOCKER_COMPOSE_CMD[@]}" up -d langgraph-postgres langgraph-redis >/dev/null
    until docker exec deer-flow-langgraph-postgres pg_isready -U postgres >/dev/null 2>&1; do
        sleep 1
    done
    docker exec deer-flow-langgraph-postgres psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'maestroflow_langgraph_v2'" | grep -q 1 \
        || docker exec deer-flow-langgraph-postgres createdb -U postgres maestroflow_langgraph_v2
    "${DOCKER_COMPOSE_CMD[@]}" up -d langgraph >/dev/null
}

stop_langgraph_runtime() {
    if command -v docker >/dev/null 2>&1; then
        "${DOCKER_COMPOSE_CMD[@]}" stop langgraph langgraph-redis langgraph-postgres >/dev/null 2>&1 || true
    fi
}

# ── Stop existing services ────────────────────────────────────────────────────

echo "Stopping existing services if any..."
pkill -f "langgraph dev" 2>/dev/null || true
pkill -f "uvicorn src.gateway.app:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
nginx -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" -s quit 2>/dev/null || true
sleep 1
pkill -9 nginx 2>/dev/null || true
./scripts/cleanup-containers.sh deer-flow-sandbox 2>/dev/null || true
stop_langgraph_runtime
sleep 1

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
    echo "  Run 'make config' from the repo root to generate ./config.yaml, then set required model API keys in .env or your config file."
    exit 1
fi

# ── Cleanup trap ─────────────────────────────────────────────────────────────

cleanup() {
    trap - INT TERM
    echo ""
    echo "Shutting down services..."
    pkill -f "langgraph dev" 2>/dev/null || true
    pkill -f "uvicorn src.gateway.app:app" 2>/dev/null || true
    pkill -f "next dev" 2>/dev/null || true
    nginx -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" -s quit 2>/dev/null || true
    sleep 1
    pkill -9 nginx 2>/dev/null || true
    echo "Cleaning up sandbox containers..."
    ./scripts/cleanup-containers.sh deer-flow-sandbox 2>/dev/null || true
    stop_langgraph_runtime
    echo "✓ All services stopped"
    exit 0
}
trap cleanup INT TERM

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
./scripts/wait-for-port.sh 2024 60 "LangGraph" || {
    echo "  See logs/langgraph.log for details"
    tail -20 logs/langgraph.log
    cleanup
}
echo "✓ LangGraph server started on localhost:2024 (Docker)"

echo "Starting Gateway API..."
(cd backend && exec uv run uvicorn src.gateway.app:app --host 0.0.0.0 --port 8001 > ../logs/gateway.log 2>&1) &
GATEWAY_PID=$!
./scripts/wait-for-port.sh 8001 30 "Gateway API" || {
    echo "✗ Gateway API failed to start. Last log output:"
    tail -60 logs/gateway.log
    echo ""
    echo "Likely configuration errors:"
    grep -E "Failed to load configuration|Environment variable .* not found|config\.yaml.*not found" logs/gateway.log | tail -5 || true
    cleanup
}
echo "✓ Gateway API started on localhost:8001"

echo "Starting Frontend..."
(cd frontend && exec pnpm exec next dev --turbopack --hostname 127.0.0.1 --port 3010 > ../logs/frontend.log 2>&1) &
FRONTEND_PID=$!
./scripts/wait-for-port.sh 3010 120 "Frontend" || {
    echo "  See logs/frontend.log for details"
    tail -20 logs/frontend.log
    cleanup
}
echo "✓ Frontend started on localhost:3010"

echo "Starting Nginx reverse proxy..."
nginx -g 'daemon off;' -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" > logs/nginx.log 2>&1 &
NGINX_PID=$!
./scripts/wait-for-port.sh 2027 10 "Nginx" || {
    echo "  See logs/nginx.log for details"
    tail -10 logs/nginx.log
    cleanup
}
echo "✓ Nginx started on localhost:2027"

# ── Ready ─────────────────────────────────────────────────────────────────────

echo ""
echo "=========================================="
echo "  MaestroFlow is ready!"
echo "=========================================="
echo ""
echo "  🌐 Application: http://localhost:2027"
echo "  📡 API Gateway: http://localhost:2027/api/*"
echo "  🤖 LangGraph:   http://localhost:2027/api/langgraph/*"
echo ""
echo "  📋 Logs:"
echo "     - LangGraph: logs/langgraph.log"
echo "     - Gateway:   logs/gateway.log"
echo "     - Frontend:  logs/frontend.log"
echo "     - Nginx:     logs/nginx.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

wait "$GATEWAY_PID" "$FRONTEND_PID" "$NGINX_PID"
