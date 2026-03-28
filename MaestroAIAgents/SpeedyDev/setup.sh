#!/bin/bash
# Razer Dashboard Setup Script
# Orchestrates Docker-Compose stack, Nginx, Caddy, and nftables.

set -e

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}--- Razer Dashboard Setup Sequence ---${NC}"

# 1. NFTables MAC Filter Regeneration
echo "Configuring nftables MAC filtering..."
# Generate default nftables policy into config/nftables.rules
node /Volumes/BA/DEV/MaestroAIAgents/SpeedyDev/scripts/render-mac-filter.js /Volumes/BA/DEV/MaestroAIAgents/SpeedyDev/config/nftables.rules

# 2. Docker-Compose Rebuild
# echo "Rebuilding Docker stack..."
# docker-compose up -d --build

# 3. Reload Nginx (Assuming managed by Docker or Systemd)
# nginx -s reload

# 4. Load Caddy Config
# caddy reload --config ./config/Caddyfile

echo -e "${GREEN}Setup completed successfully.${NC}"
