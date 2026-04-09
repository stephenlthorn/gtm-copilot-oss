#!/bin/bash
set -e

# ============================================================================
# SIMPLE EC2 Deployment - Manual Steps
# ============================================================================
# Use this if the automated script doesn't work
# This gives you the commands to run manually
# ============================================================================

cat << 'EOF'
🚀 GTM Copilot EC2 Deployment - Manual Steps
============================================

STEP 1: Get your EC2 instance IP
---------------------------------
Run this locally:

export AWS_ACCESS_KEY_ID="your-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_SESSION_TOKEN="your-session-token"  # If using temp credentials

aws ec2 describe-instances \
  --instance-ids i-04e2c79d13403a32c \
  --region ap-northeast-1 \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text

# This will output your instance IP. Save it!


STEP 2: SSH into your EC2 instance
-----------------------------------
# Replace with your SSH key path and instance IP from step 1
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_INSTANCE_IP


STEP 3: Install Node.js on EC2
-------------------------------
# Run these commands on EC2:

curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs git
node --version  # Should show v18.x


STEP 4: Clone repo and setup
-----------------------------
# On EC2:

git clone https://github.com/stephenlthorn/gtm-copilot-oss.git
cd gtm-copilot-oss/slack-interactive-bot


STEP 5: Create .env file
-------------------------
# On EC2, create .env file:

nano .env

# Paste this and fill in your actual tokens:
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token
CLAUDE_BOT_ID=U01234567
PORT=3000
NODE_ENV=production

# Save with Ctrl+X, Y, Enter


STEP 6: Install and build
--------------------------
# On EC2:

npm install
npm run build


STEP 7: Install PM2 and start bot
----------------------------------
# On EC2:

sudo npm install -g pm2
pm2 start dist/index-oauth.js --name gtm-copilot
pm2 save
pm2 startup  # Follow the command it outputs


STEP 8: Verify it's running
----------------------------
# On EC2:

pm2 status
pm2 logs gtm-copilot


DONE! Test in Slack
-------------------
In Slack, run: /gtm-menu


Useful PM2 Commands
-------------------
pm2 status              # Check status
pm2 logs gtm-copilot   # View logs
pm2 restart gtm-copilot # Restart
pm2 stop gtm-copilot    # Stop
pm2 delete gtm-copilot  # Delete

EOF
