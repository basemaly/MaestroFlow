#!/bin/bash
# MAC-based access control for Unified Dashboard
# Run as sudo

DASHBOARD_PORT=8080
TRUSTED_MACS=(
    "XX:XX:XX:XX:XX:XX"  # Add your MAC addresses here
)

echo "Setting up MAC-based access control for dashboard..."

# Flush existing rules for dashboard port
sudo iptables -F DASHBOARD 2>/dev/null || true
sudo iptables -X DASHBOARD 2>/dev/null || true

# Create new chain
sudo iptables -N DASHBOARD

# Allow established connections
sudo iptables -A DASHBOARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow trusted MACs
for MAC in "${TRUSTED_MACS[@]}"; do
    if [ "$MAC" != "XX:XX:XX:XX:XX:XX" ]; then
        sudo iptables -A DASHBOARD -m mac --mac-source "$MAC" -j ACCEPT
        echo "Allowed MAC: $MAC"
    fi
done

# Log and drop others
sudo iptables -A DASHBOARD -j LOG --log-prefix "DASHBOARD-DROP: "
sudo iptables -A DASHBOARD -j DROP

# Apply to dashboard port
sudo iptables -I INPUT -p tcp --dport $DASHBOARD_PORT -j DASHBOARD

echo "MAC filtering applied. Dashboard port $DASHBOARD_PORT restricted to trusted MACs."

# To persist across reboots, save rules:
# sudo iptables-save > /etc/iptables/rules.v4
