# GTM Copilot Interactive Slack Bot

An interactive Slack bot that provides button-based access to all GTM Copilot functions.

## 🎯 Two Modes Available

### OAuth Mode (Recommended - No API Key Needed!)
- Works with **native Claude Slack app** that's already in your workspace
- Users authenticate with their own Claude accounts
- **No Anthropic API costs**
- See **[OAUTH-SETUP.md](OAUTH-SETUP.md)** for setup

### API Mode (Direct Integration)
- Calls Anthropic API directly with your API key
- Faster responses, more control
- Costs based on API usage
- See setup below

## Features

### Available Functions

Users can click buttons to run:
- 🔍 **Pre-Call Intel** - Research prospect/company before calls
- 📊 **Post-Call Analysis** - MEDDPICC analysis after calls
- ✉️ **Follow-Up Email** - Draft personalized follow-up emails
- 🎯 **Account Intel** - Full analysis on current account
- 🎯 **Market Research / TAL** - Generate target account lists
- 🛠️ **SE: POC Plan** - Create technical POC roadmaps
- 🏗️ **SE: Architecture Fit** - Analyze TiDB architecture fit
- ⚔️ **SE: Competitor Coach** - Competitive positioning briefs

### How It Works

1. User runs `/gtm-menu` in any channel
2. Bot posts a message with buttons for each function
3. User clicks a button (e.g., "Pre-Call Intel")
4. Bot opens a modal form asking for required inputs
5. User fills out the form and clicks "Run Analysis"
6. Bot calls Claude API with the appropriate prompt
7. Bot posts the result back to the channel

## Setup

### Prerequisites

- Slack workspace with admin access
- Anthropic API key
- Node.js 18+ installed

### 1. Create Slack App

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. Name: `GTM Copilot`
4. Select your workspace

### 2. Configure Slack App

#### OAuth & Permissions

Add these **Bot Token Scopes**:
- `chat:write` - Post messages
- `commands` - Add slash commands
- `im:history` - Read DM history (optional)
- `channels:history` - Read channel history (optional)

Click **Install to Workspace** and copy the **Bot User OAuth Token** (starts with `xoxb-`)

#### Slash Commands

Create a new command:
- **Command:** `/gtm-menu`
- **Request URL:** `https://your-domain.com/slack/events` (use ngrok for local dev)
- **Short Description:** Show GTM Copilot function menu
- **Usage Hint:** (leave empty)

#### Interactivity & Shortcuts

- **Turn on Interactivity**
- **Request URL:** `https://your-domain.com/slack/events`

#### Socket Mode (Recommended for Development)

- **Enable Socket Mode**
- Create an **App-Level Token** with `connections:write` scope
- Copy the token (starts with `xapp-`)

#### Event Subscriptions (Optional)

If you want the bot to listen to messages:
- **Enable Events**
- **Request URL:** `https://your-domain.com/slack/events`
- Subscribe to bot events: `message.channels`, `message.im`

### 3. Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Fill in your credentials:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token  # Only needed for Socket Mode
ANTHROPIC_API_KEY=sk-ant-your-api-key
PORT=3000
```

### 4. Install Dependencies

```bash
npm install
```

### 5. Run the Bot

#### Development (with auto-reload)

```bash
npm run dev
```

#### Production

```bash
npm run build
npm start
```

### 6. Expose to Slack (Local Development)

If using Socket Mode, skip this step - the bot connects directly to Slack.

If using HTTP mode, you need to expose your local server:

```bash
npm run tunnel
```

This runs ngrok and gives you a public URL like `https://abc123.ngrok.io`

Update your Slack app's **Request URLs** to use this ngrok URL.

## Usage

### In Slack

1. In any channel where the bot is present, run:
   ```
   /gtm-menu
   ```

2. Click any button to open the input form

3. Fill out the required fields and click **Run Analysis**

4. Wait 30-60 seconds for Claude to process

5. Result appears in the channel

### Example Flow: Pre-Call Intel

```
/gtm-menu
```

→ Click "Pre-Call Intel" button  
→ Modal opens asking for:
  - Account Name: `Acme Corp`
  - Website: `https://acme.com`
  - Prospect Name: `John Smith`
  - Prospect LinkedIn: `https://linkedin.com/in/johnsmith`

→ Click "Run Analysis"  
→ Bot posts: "⏳ Processing your Pre-Call Intel request..."  
→ 45 seconds later, bot updates with full research brief

## Architecture

```
User runs /gtm-menu
    ↓
index.ts - Posts button menu
    ↓
User clicks button
    ↓
index.ts - Opens modal (from modals.ts)
    ↓
User submits form
    ↓
index.ts - Extracts inputs
    ↓
claude.ts - Calls Anthropic API
    ↓
index.ts - Posts result to Slack
```

### File Structure

```
slack-interactive-bot/
├── src/
│   ├── index.ts          # Main bot logic
│   ├── prompts.ts        # Function definitions
│   ├── modals.ts         # Modal builders
│   ├── claude.ts         # Claude API integration
│   └── system-prompts.ts # System prompts
├── package.json
├── tsconfig.json
└── .env.example
```

## Deployment

### Option 1: Railway (Recommended)

1. Push code to GitHub
2. Go to https://railway.app
3. Click **New Project** → **Deploy from GitHub**
4. Select your repo
5. Add environment variables in Railway dashboard
6. Railway gives you a public URL - update Slack app URLs

### Option 2: Heroku

```bash
heroku create gtm-copilot-bot
heroku config:set SLACK_BOT_TOKEN=xoxb-...
heroku config:set SLACK_SIGNING_SECRET=...
heroku config:set ANTHROPIC_API_KEY=sk-ant-...
git push heroku main
```

### Option 3: AWS Lambda + API Gateway

Use the Slack Bolt for JavaScript AWS Lambda adapter:
https://slack.dev/bolt-js/deployments/aws-lambda

### Option 4: Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
CMD ["npm", "start"]
```

```bash
docker build -t gtm-copilot-bot .
docker run -p 3000:3000 --env-file .env gtm-copilot-bot
```

## Customization

### Add a New Function

1. **Update `src/prompts.ts`**:
   ```typescript
   export const GTM_FUNCTIONS: Record<string, GTMFunction> = {
     // ... existing functions
     my_function: {
       id: "my_function",
       name: "My Function",
       description: "What it does",
       icon: "🚀",
       systemPrompt: "system_my_prompt",
       template: "tpl_my_template",
       variables: ["account", "my_field"],
     },
   };
   ```

2. **Add button to menu in `getPromptMenu()`**:
   ```typescript
   {
     type: "section",
     text: {
       type: "mrkdwn",
       text: `🚀 *My Function*\nWhat it does`,
     },
     accessory: {
       type: "button",
       text: { type: "plain_text", text: "Run" },
       action_id: "gtm_my_function",
     },
   },
   ```

3. **Add field config to `src/modals.ts`**:
   ```typescript
   my_field: {
     label: "My Field Label",
     placeholder: "Enter something...",
     multiline: false,
   },
   ```

4. **Add system prompt to `src/system-prompts.ts`**:
   ```typescript
   system_my_prompt: `You are an expert at...`
   ```

### Connect to Your GTM API

Instead of using hardcoded prompts, fetch from your API:

```typescript
// In src/claude.ts
import axios from "axios";

const GTM_API_URL = process.env.GTM_API_URL || "http://localhost:8000";

async function getPromptFromAPI(promptId: string): Promise<string> {
  const response = await axios.get(`${GTM_API_URL}/api/prompts/${promptId}`);
  return response.data.current_content;
}
```

## Troubleshooting

### Bot doesn't respond to `/gtm-menu`

- Check that slash command is configured in Slack app settings
- Verify Request URL is correct (or Socket Mode is enabled)
- Check logs for errors: `npm run dev`

### Modal doesn't open when clicking button

- Ensure **Interactivity** is enabled in Slack app
- Verify Request URL matches your server
- Check browser console for errors

### Claude API errors

- Verify `ANTHROPIC_API_KEY` is correct
- Check API quota: https://console.anthropic.com
- Review error in bot logs

### "Channel not found" error

- Ensure bot is invited to the channel: `/invite @GTM Copilot`
- Or run `/gtm-menu` in a DM with the bot

## Support

For issues or questions:
- GitHub Issues: [your-repo]/issues
- Internal Slack: #gtm-copilot-support

## License

MIT
