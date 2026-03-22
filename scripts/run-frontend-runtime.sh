#!/bin/sh

set -eu

MODE="${MAESTROFLOW_FRONTEND_RUNTIME_MODE:-app}"
HOST="${MAESTROFLOW_FRONTEND_BIND_HOST:-${HOSTNAME:-0.0.0.0}}"
PORT="${MAESTROFLOW_FRONTEND_BIND_PORT:-${PORT:-3000}}"
PUBLIC_ORIGIN="${MAESTROFLOW_PUBLIC_ORIGIN:-http://localhost:2027}"

case "$MODE" in
  app)
    DIST_DIR="${MAESTROFLOW_FRONTEND_APP_DIST_DIR:-.next-app}"
    ;;
  ui-dev)
    DIST_DIR="${MAESTROFLOW_FRONTEND_DEV_DIST_DIR:-.next-dev}"
    ;;
  *)
    DIST_DIR=".next"
    ;;
esac

BUILD_STAMP="${DIST_DIR}/BUILD_ID"

export BETTER_AUTH_BASE_URL="${BETTER_AUTH_BASE_URL:-$PUBLIC_ORIGIN}"
export MAESTROFLOW_NEXT_DIST_DIR="$DIST_DIR"

needs_frontend_build() {
  if [ ! -f "$BUILD_STAMP" ]; then
    return 0
  fi

  if find src app components core server public \
    -type f \
    -newer "$BUILD_STAMP" \
    -print \
    -quit 2>/dev/null | grep -q .; then
    return 0
  fi

  for file in package.json pnpm-lock.yaml next.config.js tsconfig.json src/env.js; do
    if [ -f "$file" ] && [ "$file" -nt "$BUILD_STAMP" ]; then
      return 0
    fi
  done

  return 1
}

case "$MODE" in
  app)
    export NODE_ENV=production
    echo "Starting frontend in app mode on ${HOST}:${PORT}"
    if needs_frontend_build; then
      echo "Building frontend bundle for app mode"
      rm -rf "$DIST_DIR"
      pnpm run build
    else
      echo "Reusing existing frontend app-mode build"
    fi
    exec pnpm exec next start --hostname "$HOST" --port "$PORT"
    ;;
  ui-dev)
    export NODE_ENV=development
    echo "Starting frontend in ui-dev mode on ${HOST}:${PORT}"
    exec pnpm exec next dev --hostname "$HOST" --port "$PORT"
    ;;
  *)
    echo "Unknown MAESTROFLOW_FRONTEND_RUNTIME_MODE: $MODE" >&2
    echo "Expected one of: app, ui-dev" >&2
    exit 1
    ;;
esac
