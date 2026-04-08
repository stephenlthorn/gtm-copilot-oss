# GTM Copilot with Native Claude Slack App (OAuth Mode)

This version works with the **native Claude Slack app** that's already installed in your workspace. No Anthropic API key needed!

## How It Works

1. User runs `/gtm-menu` → sees button menu
2. User clicks button (e.g., "Pre-Call Intel") → modal opens
3. User fills form → clicks "Run Analysis"
4. Bot posts a formatted message mentioning `@Claude`
5. **Native Claude Slack app** responds with the analysis
6. Users authenticate with Claude using their own accounts (OAuth)

## Architecture Difference

| Feature | OAuth Mode (This) | API Mode |
|---------|-------------------|----------|
| Authentication | Users' Claude accounts (OAuth) | Single API key |
| Cost | Free (users' Claude quota) | Paid API usage |
| Setup | Just Slack bot token | Slack token + Anthropic API key |
| Claude Integration | Native @Claude app | Direct API calls |
| Response Speed | ~30-60s (Claude app) | ~20-40s (direct API) |

## Prerequisites

1. **Native Claude Slack App** must be installed in your workspace
   - If not installed, add it from the Slack App Directory
   - Invite @Claude to your channel: `/invite @Claude`

2. **Your Slack Bot** (the GTM Copilot menu bot)
   - This is the lightweight bot you'll create below

## Setup

### 1. Create Your Slack App

1. Go to https://api.slack.com/apps
2. Click **Create New App** → **From scratch**
3. Name: `GTM Copilot Menu`
4. Select your workspace

### 2. Configure Slack App

#### OAuth & Permissions

Add these **Bot Token Scopes**:
- `chat:write` - Post messages
- `commands` - Add slash commands
- `users:read` - Read user info (optional)

Click **Install to Workspace** and copy the **Bot User OAuth Token** (starts with `xoxb-`)

#### Slash Commands

Create a new command:
- **Command:** `/gtm-menu`
- **Request URL:** `https://your-domain.com/slack/events` (use ngrok for local dev)
- **Short Description:** Show GTM Copilot function menu

#### Interactivity & Shortcuts

- **Turn on Interactivity**
- **Request URL:** `https://your-domain.com/slack/events`

#### Socket Mode (Recommended)

- **Enable Socket Mode**
- Create an **App-Level Token** with `connections:write` scope
- Copy the token (starts with `xapp-`)

### 3. Find Claude's User ID

You need to find the user ID of the @Claude bot in your workspace:

**Option 1: Via Slack UI**
1. Click on @Claude's profile in Slack
2. Click "More" → "Copy member ID"
3. The ID looks like `U01234567ABC`

**Option 2: Via API**
```bash
# List all users and find Claude
curl -H "Authorization: Bearer xoxb-YOUR-BOT-TOKEN" \
  https://slack.com/api/users.list | grep -i claude
```

### 4. Environment Setup

```bash
cd slack-interactive-bot
cp .env.example .env
```

Edit `.env`:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token
CLAUDE_BOT_ID=U01234567  # @Claude's user ID from step 3
GTM_CHANNEL_ID=C0ARQCGCBJN  # Your GTM channel (optional)
```

### 5. Install & Run

```bash
npm install
npm run dev  # Runs OAuth mode by default
```

For API mode (if you want to compare):
```bash
npm run dev:api
```

### 6. Test in Slack

```
/gtm-menu
```

Click a button → Fill the form → Submit → @Claude responds!

## Usage Flow

### Example: Pre-Call Intel

```
/gtm-menu
```

**Bot posts:**
```
🚀 GTM Copilot Functions

Select a function to run with Claude:

[🔍 Pre-Call Intel] [Run ▸]
Research prospect and company before sales call

[📊 Post-Call Analysis] [Run ▸]
...
```

**User clicks "Run" on Pre-Call Intel**

**Modal opens:**
```
┌─────────────────────────────────┐
│      Pre-Call Intel             │
├─────────────────────────────────┤
│ Account Name*                   │
│ [Acme Corp              ]       │
│                                 │
│ Company Website*                │
│ [https://acme.com       ]       │
│                                 │
│ Prospect Name*                  │
│ [John Smith             ]       │
│                                 │
│ Prospect LinkedIn*              │
│ [https://linkedin.com/in/...]   │
│                                 │
│            [Cancel] [Run Analysis]
└─────────────────────────────────┘
```

**User clicks "Run Analysis"**

**Bot posts in channel:**
```
🚀 Pre-Call Intel analysis requested by @stephen

> Context: You are a GTM Copilot specialist.
> You are a GTM research specialist helping sales teams...
> [System prompt here]

---

Task: Pre-Call Intel

Account Name: Acme Corp
Website: https://acme.com
Prospect Name: John Smith
Prospect LinkedIn: https://linkedin.com/in/johnsmith

---

Please research this prospect and company thoroughly and provide:
1. Prospect Information - Role, background...
2. Company Context - Industry, size...
[Instructions here]

💡 @Claude will respond with the analysis shortly
```

**@Claude responds:**
```
Based on my research of Acme Corp and John Smith:

## 1. Prospect Information
John Smith is the VP of Engineering at Acme Corp...
[Full analysis]
```

## Channel Setup Options

### Option 1: Any Channel (Ad-hoc)
- Run `/gtm-menu` in any channel
- Invite @Claude to that channel if needed
- Analysis appears inline

### Option 2: Dedicated GTM Channel (Recommended)
1. Create `#gtm-copilot` channel
2. Invite @Claude: `/invite @Claude`
3. Set `GTM_CHANNEL_ID=C0ARQCGCBJN` in .env
4. All analyses automatically post there
5. Searchable archive of all GTM work

### Option 3: DM with Claude
- Run `/gtm-menu` in your DM with the bot
- Bot posts to your DM
- Private, one-on-one analysis

## Customization

### Auto-Post to Specific Channel

Edit `src/index-oauth.ts`:

```typescript
// Always post to GTM channel instead of current channel
const channelId = process.env.GTM_CHANNEL_ID || metadata.channel_id;
```

### Create Canvas Instead of Message

Replace the `chat.postMessage` call with:

```typescript
// Create a Canvas with the request
const canvas = await client.canvases.create({
  owner_id: channelId,
  document_content: {
    type: "markdown",
    markdown: claudeMessage,
  },
});

// Post a link to the Canvas
await client.chat.postMessage({
  channel: channelId,
  text: `📄 New ${functionDef.name} analysis in Canvas`,
  blocks: [
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `🚀 **${functionDef.name}** requested by <@${userId}>\n\n<slack://canvas/${canvas.canvas_id}|Open Canvas>`,
      },
    },
  ],
});
```

### Add Custom Functions

See main README.md for how to add new GTM functions.

## Troubleshooting

### @Claude doesn't respond

1. **Check if @Claude is in the channel:**
   ```
   /invite @Claude
   ```

2. **Verify @Claude app is installed:**
   - Go to Slack App Directory
   - Search for "Claude"
   - Click "Add to Slack" if needed

3. **Check if message properly mentions Claude:**
   - Message should start with `@Claude` or mention Claude
   - Check bot logs to see the exact message posted

### Modal doesn't open

- Enable **Interactivity** in Slack app settings
- Verify Request URL or Socket Mode is configured

### Message posts but formatting is wrong

- Check that `CLAUDE_BOT_ID` is set correctly
- Use `<@${CLAUDE_BOT_ID}>` syntax to mention Claude
- Current implementation uses plain text `@Claude` which should work if Claude is in the channel

## Benefits of OAuth Mode

✅ **No API costs** - Uses users' Claude accounts  
✅ **No API key management** - OAuth handles auth  
✅ **Native Slack experience** - Threads, reactions, etc.  
✅ **User attribution** - Each request tied to user  
✅ **Simpler setup** - Just a lightweight menu bot  

## Limitations

❌ **Slower** - Native app response time varies  
❌ **Less control** - Can't customize Claude's output format  
❌ **Requires Claude in channel** - Must invite @Claude  
❌ **Public responses** - Claude responds in thread (not ephemeral)  

## Next Steps

1. Test with a few functions
2. Gather feedback from sales team
3. Add more functions as needed
4. Consider Canvas integration for long reports
5. Set up a dedicated `#gtm-copilot` channel

For API mode (direct Anthropic integration), use `npm run dev:api` and see main README.md.
