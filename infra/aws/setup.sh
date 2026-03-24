#!/bin/bash
set -euo pipefail

# ============================================================
# GTM Copilot — EC2 Setup Script
# Run this on a fresh Amazon Linux 2023 / Ubuntu 22.04 instance
# ============================================================

echo "=== Installing Docker ==="
if command -v apt-get &>/dev/null; then
    # Ubuntu / Debian
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose-plugin git
    sudo systemctl enable docker
    sudo systemctl start docker
elif command -v dnf &>/dev/null; then
    # Amazon Linux 2023
    sudo dnf install -y docker git
    sudo systemctl enable docker
    sudo systemctl start docker
    # Install docker compose plugin
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f 4)
    sudo curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

sudo usermod -aG docker "$USER"
echo "=== Docker installed ==="

echo ""
echo "=== Cloning repo ==="
cd /home/ec2-user 2>/dev/null || cd /home/ubuntu 2>/dev/null || cd ~
git clone https://github.com/stephenlthorn/gtm-copilot-oss.git app
cd app/infra/aws

echo ""
echo "=== Next steps ==="
echo "1. Copy .env.example to .env and fill in your values:"
echo "   cp .env.example .env && nano .env"
echo ""
echo "2. Set DOMAIN to your Elastic IP + .sslip.io:"
echo "   e.g. DOMAIN=34.56.78.90.sslip.io"
echo ""
echo "3. Start everything:"
echo "   docker compose -f docker-compose.prod.yml up -d --build"
echo ""
echo "4. Check logs:"
echo "   docker compose -f docker-compose.prod.yml logs -f"
echo ""
echo "5. Verify at: https://YOUR_ELASTIC_IP.sslip.io"
