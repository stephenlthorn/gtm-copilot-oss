#!/bin/bash
# Auto-deploy to EC2 after git push.
# Requires ~/.ssh/gtm-copilot-ec2.pem — if missing, GitHub Actions handles deploy instead.

cmd=$(jq -r '.tool_input.command // ""')

# Only fire on git push commands
if ! echo "$cmd" | grep -q 'git push'; then
  exit 0
fi

KEY="$HOME/.ssh/gtm-copilot-ec2.pem"
HOST="ec2-user@100.49.55.13"
DEPLOY="cd ~/app && git pull && docker compose -f infra/aws/docker-compose.prod.yml up -d --build ui api 2>&1 | tail -20"

if [ -f "$KEY" ]; then
  ssh -i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=15 "$HOST" "$DEPLOY"
else
  echo "{\"systemMessage\": \"Pushed to GitHub. GitHub Actions will deploy automatically (or add SSH key to ~/.ssh/gtm-copilot-ec2.pem for local deploy).\"}"
fi
