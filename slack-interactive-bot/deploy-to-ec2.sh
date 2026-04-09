#!/bin/bash
set -e

# ============================================================================
# GTM Copilot Slack Bot - EC2 Deployment Script
# ============================================================================

echo "🚀 Deploying GTM Copilot Slack Bot to EC2..."

# AWS Credentials - set these in your environment before running:
# export AWS_ACCESS_KEY_ID="your-key-id"
# export AWS_SECRET_ACCESS_KEY="your-secret-key"
# export AWS_SESSION_TOKEN="your-session-token"  # If using temporary credentials

if [ -z "$AWS_ACCESS_KEY_ID" ]; then
  echo "❌ Error: AWS credentials not set!"
  echo ""
  echo "Set these environment variables first:"
  echo "  export AWS_ACCESS_KEY_ID=\"your-key-id\""
  echo "  export AWS_SECRET_ACCESS_KEY=\"your-secret-key\""
  echo "  export AWS_SESSION_TOKEN=\"your-token\"  # Optional, for temp credentials"
  echo ""
  exit 1
fi

# EC2 Instance ID
INSTANCE_ID="i-04e2c79d13403a32c"
REGION="ap-northeast-1"  # Change if different

# Get instance public IP
echo "📡 Getting EC2 instance IP..."
INSTANCE_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --region $REGION \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

if [ "$INSTANCE_IP" == "None" ] || [ -z "$INSTANCE_IP" ]; then
  echo "❌ Error: Could not get instance IP. Is the instance running?"
  echo "   Trying private IP instead..."
  INSTANCE_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --region $REGION \
    --query 'Reservations[0].Instances[0].PrivateIpAddress' \
    --output text)
fi

echo "✅ Instance IP: $INSTANCE_IP"

# Get instance user (ubuntu for Ubuntu AMI, ec2-user for Amazon Linux)
INSTANCE_USER="ubuntu"  # Change to "ec2-user" if using Amazon Linux

# SSH Key Path - IMPORTANT: Update this to your SSH key location
SSH_KEY="$HOME/.ssh/gtm-copilot-key.pem"  # ⚠️ UPDATE THIS PATH

if [ ! -f "$SSH_KEY" ]; then
  echo "❌ Error: SSH key not found at $SSH_KEY"
  echo "   Please update SSH_KEY variable in this script to point to your EC2 key pair"
  echo "   Example: SSH_KEY=\"$HOME/.ssh/your-key.pem\""
  exit 1
fi

# Ensure key has correct permissions
chmod 400 "$SSH_KEY"

echo ""
echo "📦 Building application locally..."
cd "$(dirname "$0")"
npm install
npm run build

echo ""
echo "📤 Creating deployment package..."
DEPLOY_DIR="/tmp/gtm-copilot-deploy-$$"
mkdir -p "$DEPLOY_DIR"

# Copy necessary files
cp -r dist "$DEPLOY_DIR/"
cp package.json "$DEPLOY_DIR/"
cp package-lock.json "$DEPLOY_DIR/" 2>/dev/null || true

# Create .env file (you'll need to fill this in)
cat > "$DEPLOY_DIR/.env" << 'EOF'
# Slack Bot Configuration
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token

# Claude Bot ID (find with @Claude's Slack profile)
CLAUDE_BOT_ID=U01234567

# Server Configuration
PORT=3000
NODE_ENV=production
EOF

echo ""
echo "⚠️  IMPORTANT: You need to edit .env with your Slack credentials!"
echo "   Opening .env file now..."
echo ""
read -p "Press ENTER to edit .env file with your credentials..."
${EDITOR:-nano} "$DEPLOY_DIR/.env"

echo ""
echo "🚢 Uploading to EC2..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$INSTANCE_USER@$INSTANCE_IP" "mkdir -p ~/gtm-copilot"
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no -r "$DEPLOY_DIR"/* "$INSTANCE_USER@$INSTANCE_IP:~/gtm-copilot/"

echo ""
echo "⚙️  Installing and starting on EC2..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$INSTANCE_USER@$INSTANCE_IP" << 'ENDSSH'
set -e

echo "📦 Installing Node.js..."
if ! command -v node &> /dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

echo "✅ Node.js version: $(node --version)"
echo "✅ NPM version: $(npm --version)"

cd ~/gtm-copilot

echo "📦 Installing dependencies..."
npm install --production

echo "📦 Installing PM2..."
sudo npm install -g pm2

echo "🛑 Stopping existing instance (if any)..."
pm2 delete gtm-copilot 2>/dev/null || true

echo "🚀 Starting GTM Copilot bot..."
pm2 start dist/index-oauth.js --name gtm-copilot

echo "💾 Saving PM2 configuration..."
pm2 save

echo "🔄 Setting up PM2 to start on boot..."
sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u $USER --hp $HOME

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Bot status:"
pm2 status

echo ""
echo "📋 View logs:"
echo "   pm2 logs gtm-copilot"
echo ""
echo "🔄 Restart bot:"
echo "   pm2 restart gtm-copilot"
echo ""
echo "🛑 Stop bot:"
echo "   pm2 stop gtm-copilot"

ENDSSH

echo ""
echo "✅ Deployment successful!"
echo ""
echo "📍 Instance: $INSTANCE_IP"
echo "🔗 SSH: ssh -i $SSH_KEY $INSTANCE_USER@$INSTANCE_IP"
echo ""
echo "Next steps:"
echo "1. Test the bot in Slack: /gtm-menu"
echo "2. View logs: ssh -i $SSH_KEY $INSTANCE_USER@$INSTANCE_IP 'pm2 logs gtm-copilot'"
echo ""
echo "⚠️  Security Note: Remember to rotate your AWS credentials after sharing them!"

# Cleanup
rm -rf "$DEPLOY_DIR"
