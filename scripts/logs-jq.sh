#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose-dev.yaml"
SERVICE="${1:-gateway}"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is not installed. Install it first, or use ./scripts/logs.sh." >&2
  exit 1
fi

docker compose -f "$COMPOSE_FILE" logs --no-color -f --tail=200 "$SERVICE" \
  | jq -Rr '
      fromjson? // empty
      | [
          .timestamp // "",
          .service // "",
          .level // "",
          .request_id // "-",
          .trace_id // "-",
          .logger // "",
          .message // ""
        ]
      | @tsv
    '
