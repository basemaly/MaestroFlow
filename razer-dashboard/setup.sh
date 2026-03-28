#!/bin/bash
set -e

echo "Setting up Unified Dashboard..."

DASHBOARD_DIR="$HOME/unified-dashboard"

if [ ! -d "$DASHBOARD_DIR" ]; then
    mkdir -p "$DASHBOARD_DIR"
fi

echo "Installing Python dependencies..."
cd "$DASHBOARD_DIR/app"
pip install -r requirements.txt

echo "Creating config directories..."
mkdir -p "$DASHBOARD_DIR/config"

echo "Setting up nginx..."
sudo cp "$DASHBOARD_DIR/config/nginx.conf" /etc/nginx/nginx.conf
sudo nginx -t && sudo nginx -s reload || echo "Nginx config needs adjustment"

echo "Starting dashboard..."
cd "$DASHBOARD_DIR"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080 &

echo "Dashboard setup complete!"
echo "Access at: http://razer.local:8080"
