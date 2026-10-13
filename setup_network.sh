#!/bin/bash
# ============================================================
# Network Setup for VPS Bot
# Creates isolated Docker network with inter-container isolation
# ============================================================

echo "🔒 Setting up isolated Docker network..."

# Create isolated network with inter-container communication DISABLED
docker network create \
    --driver bridge \
    --opt "com.docker.network.bridge.enable_icc=false" \
    --opt "com.docker.network.bridge.enable_ip_masquerade=true" \
    --subnet 172.20.0.0/16 \
    --ip-range 172.20.240.0/20 \
    vps_isolated_net 2>/dev/null || echo "Network already exists"

echo "✅ Network 'vps_isolated_net' ready"
echo ""
echo "ICC (Inter-Container Communication) = DISABLED"
echo "Containers CANNOT talk to each other"
echo ""
echo "Update config.py: CONTAINER_NETWORK_MODE = 'vps_isolated_net'"
echo ""

# Host firewall rules (iptables on the HOST machine)
echo "🔒 Setting up host firewall rules..."

# Prevent containers from accessing Docker daemon
iptables -I DOCKER-USER -d 172.17.0.1 -p tcp --dport 2375 -j DROP 2>/dev/null
iptables -I DOCKER-USER -d 172.17.0.1 -p tcp --dport 2376 -j DROP 2>/dev/null

# Prevent containers from accessing host metadata service (cloud)
iptables -I DOCKER-USER -d 169.254.169.254 -j DROP 2>/dev/null

# Prevent containers from accessing other container networks
iptables -I DOCKER-USER -s 172.20.0.0/16 -d 172.20.0.0/16 -j DROP 2>/dev/null

# Allow established connections
iptables -I DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null

echo "✅ Host firewall configured"
echo ""
echo "Done! Start bot with: python bot.py"
