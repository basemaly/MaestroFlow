#!/usr/bin/env bash
# Install MiroFlow on the Linux PC and start the wrapper server.
# Run this on 192.168.86.145 (the Ollama LAN host).
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh

set -e

MIROFLOW_DIR="$HOME/miroflow"
SERVER_PORT=8020
OLLAMA_MODEL="mirothinker-v2:latest"

# API keys — replace or set in environment before running
E2B_API_KEY="${E2B_API_KEY:-e2b_8f17556f98a41114f86c652e8b06b212fa1c04f5}"
SERPER_API_KEY="${SERPER_API_KEY:-e0b2e93f4b820e307f293a369d05c54c85298d92}"
JINA_API_KEY="${JINA_API_KEY:-jina_a7e2c72530f94127a5f7a4a7d7273abea2LlXMqaG_c9kRnlQlm4JfKhZLFj}"

echo "=== MiroFlow Setup ==="
echo "Install dir: $MIROFLOW_DIR"
echo "Server port: $SERVER_PORT"

# 1. Clone MiroThinker repo
if [ -d "$MIROFLOW_DIR/.git" ]; then
  echo "Repo already exists at $MIROFLOW_DIR — pulling latest..."
  git -C "$MIROFLOW_DIR" pull
elif [ -d "$MIROFLOW_DIR" ]; then
  echo "Directory exists (non-empty) — initialising git repo in place..."
  git -C "$MIROFLOW_DIR" init
  git -C "$MIROFLOW_DIR" remote add origin https://github.com/MiroMindAI/MiroThinker
  git -C "$MIROFLOW_DIR" fetch origin
  git -C "$MIROFLOW_DIR" checkout -b main --track origin/main 2>/dev/null || \
    git -C "$MIROFLOW_DIR" reset --hard origin/HEAD
else
  echo "Cloning MiroThinker..."
  git clone https://github.com/MiroMindAI/MiroThinker "$MIROFLOW_DIR"
fi

cd "$MIROFLOW_DIR"

# 2. Create venv and install
echo "Setting up venv..."
python3 -m venv .venv
source .venv/bin/activate

echo "Installing MiroFlow..."
pip install -e . 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true
pip install fastapi uvicorn httpx pydantic

# 3. Create .env
cat > "$MIROFLOW_DIR/.env" << ENV
E2B_API_KEY=$E2B_API_KEY
SERPER_API_KEY=$SERPER_API_KEY
JINA_API_KEY=$JINA_API_KEY
MIROFLOW_MODEL=$OLLAMA_MODEL
MIROFLOW_PORT=$SERVER_PORT
OLLAMA_BASE=http://localhost:11434
ENV
echo "Created .env"

# 4. Copy wrapper server
cp "$(dirname "$0")/server.py" "$MIROFLOW_DIR/wrapper_server.py"

# 5. Create systemd service (optional)
SERVICE_FILE="$HOME/.config/systemd/user/miroflow-wrapper.service"
mkdir -p "$(dirname "$SERVICE_FILE")"
cat > "$SERVICE_FILE" << SERVICE
[Unit]
Description=MiroFlow Research Wrapper
After=network.target

[Service]
Type=simple
WorkingDirectory=$MIROFLOW_DIR
EnvironmentFile=$MIROFLOW_DIR/.env
ExecStart=$MIROFLOW_DIR/.venv/bin/python wrapper_server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SERVICE

echo "Created systemd service at $SERVICE_FILE"
echo "Enable with: systemctl --user enable --now miroflow-wrapper"
echo ""
echo "=== Done! ==="
echo "Start manually: cd $MIROFLOW_DIR && source .venv/bin/activate && python wrapper_server.py"
echo "Health check:  curl http://localhost:$SERVER_PORT/health"
