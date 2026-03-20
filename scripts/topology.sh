#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/dev-topology.sh"

MODE="$(detect_dev_runtime_mode)"
print_dev_topology "$MODE"
warn_if_mixed_topology "$MODE"
