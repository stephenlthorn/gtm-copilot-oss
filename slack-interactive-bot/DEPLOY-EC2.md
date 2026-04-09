# EC2 Deployment Guide

## 🚀 Quick Deploy (Automated)

**Before running:** Update `SSH_KEY` path in `deploy-to-ec2.sh` to point to your EC2 key pair file.

```bash
cd slack-interactive-bot
./deploy-to-ec2.sh
```

This script will:
1. Get your EC2 instance IP using AWS CLI
2. Build the application locally
3. Prompt you to edit `.env` with your Slack credentials
4. Upload everything to EC2
5. Install Node.js, npm, and PM2 on EC2
6. Start the bot with PM2 (auto-restart on crash/reboot)

---

## 📋 Manual Deploy (Step-by-Step)

If the automated script doesn't work, use manual steps:

```bash
./deploy-simple.sh
```

This will print out all the commands to run manually.

---

## 🔐 Required Information

Before deploying, gather these:

### 1. EC2 SSH Key
Your `.pem` file for SSH access to the instance.

**Location:** Usually in `~/.ssh/your-key.pem`

**Fix permissions if needed:**
```bash
chmod 400 ~/.ssh/your-key.pem
```

### 2. Slack Credentials

Get these from https://api.slack.com/apps:

- **SLACK_BOT_TOKEN** - Starts with `xoxb-`
  - From: OAuth & Permissions → Bot User OAuth Token
- **SLACK_SIGNING_SECRET** - From: Basic Information → Signing Secret
- **SLACK_APP_TOKEN** - Starts with `xapp-`
  - From: Basic Information → App-Level Tokens
  - (Only needed if using Socket Mode)

### 3. Claude Bot ID

Find @Claude's user ID in Slack:
1. Click @Claude's profile in Slack
2. Click "More" → "Copy member ID"
3. ID looks like: `U01234567ABC`

---

## 🔧 Instance Requirements

### Minimum Specs
- **Instance Type:** t2.micro (free tier) is plenty
- **OS:** Ubuntu 22.04 or Amazon Linux 2
- **Storage:** 8GB is fine
- **Network:** Public IP or NAT gateway (for Socket Mode)

### Security Group Rules

**Inbound:**
- SSH (port 22) from your IP
- HTTP (port 3000) - Only needed if NOT using Socket Mode

**Outbound:**
- All traffic (for npm installs and Slack API)

---

## 🎯 Deployment Options

### Option A: Socket Mode (Recommended)
- Bot connects to Slack via WebSocket
- No need to open port 3000
- Works behind firewall
- Set `SLACK_APP_TOKEN` in .env

### Option B: HTTP Mode
- Slack sends webhooks to your server
- Need public IP and port 3000 open
- Update Slack app URLs to: `http://your-ec2-ip:3000/slack/events`
- Don't set `SLACK_APP_TOKEN`

**For EC2, use Socket Mode** - it's simpler!

---

## 📦 What Gets Deployed

```
EC2: ~/gtm-copilot/
├── dist/              # Compiled JavaScript
├── node_modules/      # Dependencies
├── package.json
└── .env              # Your credentials
```

---

## 🔍 Post-Deploy Checklist

After deployment, verify:

1. **Bot is running:**
   ```bash
   ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP
   pm2 status
   # Should show "gtm-copilot" with status "online"
   ```

2. **No errors in logs:**
   ```bash
   pm2 logs gtm-copilot
   # Should show: "⚡️ GTM Copilot Slack bot (OAuth mode) is running"
   ```

3. **Test in Slack:**
   ```
   /gtm-menu
   ```
   Should show the button menu!

---

## 🛠️ Troubleshooting

### Bot won't start

**Check logs:**
```bash
pm2 logs gtm-copilot --lines 50
```

**Common issues:**
- Missing `.env` file → Create it with credentials
- Wrong Node.js version → Must be 18+
- Port 3000 already in use → Change PORT in .env

### `/gtm-menu` command not working

**Check Slack app settings:**
1. Go to https://api.slack.com/apps
2. Select your app
3. Slash Commands → Verify `/gtm-menu` is configured
4. Request URL should be correct (or use Socket Mode)

### "Connection refused" errors

**If using Socket Mode:**
- Check `SLACK_APP_TOKEN` is set in .env
- Verify EC2 has outbound internet access

**If using HTTP Mode:**
- Check Security Group allows inbound on port 3000
- Verify EC2 has public IP
- Update Slack app Request URLs

### PM2 not starting on reboot

Run on EC2:
```bash
pm2 startup
# Follow the command it outputs
pm2 save
```

---

## 🔄 Updating the Bot

When you push new code:

```bash
# On your local machine
cd slack-interactive-bot
git pull origin claude/slack-session-F9U0D

# Run deploy script again
./deploy-to-ec2.sh
```

Or manually on EC2:
```bash
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP
cd ~/gtm-copilot-oss
git pull
cd slack-interactive-bot
npm install
npm run build
pm2 restart gtm-copilot
```

---

## 💰 Cost Estimate

| Resource | Type | Cost |
|----------|------|------|
| EC2 t2.micro | 750 hrs/month free tier | $0-3/mo |
| EBS 8GB | Free tier | $0 |
| Data transfer | Minimal | ~$0 |
| **Total** | | **$0-3/month** |

After free tier expires: ~$3-5/month

---

## 🔒 Security Notes

⚠️ **IMPORTANT:**
1. Your AWS credentials in the deploy script are **temporary** (session token)
2. They will expire in a few hours
3. **Rotate them** after sharing in Slack!
4. Never commit `.env` with real credentials to git
5. Consider using AWS Secrets Manager for production

### Secure the .env file on EC2:
```bash
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP
chmod 600 ~/gtm-copilot/.env
```

---

## 📊 Monitoring

### View real-time logs:
```bash
pm2 logs gtm-copilot
```

### View bot status:
```bash
pm2 status
```

### View resource usage:
```bash
pm2 monit
```

### Set up log rotation:
```bash
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 7
```

---

## 🆘 Need Help?

**Common Commands:**

```bash
# SSH into EC2
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_EC2_IP

# Restart bot
pm2 restart gtm-copilot

# Stop bot
pm2 stop gtm-copilot

# View logs
pm2 logs gtm-copilot

# Edit .env
cd ~/gtm-copilot
nano .env

# Rebuild
npm run build
pm2 restart gtm-copilot
```

**Still stuck?**
Check the [OAUTH-SETUP.md](OAUTH-SETUP.md) for configuration help.
