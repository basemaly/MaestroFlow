#!/usr/bin/env bash

# Canonical local-development port assignments for MaestroFlow.
# Source this file from scripts instead of hardcoding port numbers repeatedly.

export MAESTROFLOW_PUBLIC_HOST="${MAESTROFLOW_PUBLIC_HOST:-127.0.0.1}"
export MAESTROFLOW_PUBLIC_PORT="${MAESTROFLOW_PUBLIC_PORT:-2027}"
export MAESTROFLOW_FRONTEND_HOST="${MAESTROFLOW_FRONTEND_HOST:-127.0.0.1}"
export MAESTROFLOW_FRONTEND_PORT="${MAESTROFLOW_FRONTEND_PORT:-3010}"
export MAESTROFLOW_GATEWAY_HOST="${MAESTROFLOW_GATEWAY_HOST:-127.0.0.1}"
export MAESTROFLOW_GATEWAY_PORT="${MAESTROFLOW_GATEWAY_PORT:-8001}"
export MAESTROFLOW_LANGGRAPH_HOST="${MAESTROFLOW_LANGGRAPH_HOST:-127.0.0.1}"
export MAESTROFLOW_LANGGRAPH_PORT="${MAESTROFLOW_LANGGRAPH_PORT:-2024}"

# Langfuse is a companion service, not part of the core MaestroFlow app, but
# reserving it here avoids accidental clashes with the frontend's common 3000 default.
export MAESTROFLOW_LANGFUSE_HOST="${MAESTROFLOW_LANGFUSE_HOST:-127.0.0.1}"
export MAESTROFLOW_LANGFUSE_PORT="${MAESTROFLOW_LANGFUSE_PORT:-3000}"
