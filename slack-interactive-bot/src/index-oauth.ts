import { App, BlockAction } from "@slack/bolt";
import dotenv from "dotenv";
import { getPromptMenu, GTM_FUNCTIONS } from "./prompts";
import { buildModal } from "./modals";
import { buildClaudeMessage } from "./claude-oauth";

dotenv.config();

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
});

/**
 * Slash command: /gtm-menu
 * Posts an interactive message with buttons for all GTM functions
 */
app.command("/gtm-menu", async ({ command, ack, client }) => {
  await ack();

  const blocks = getPromptMenu();

  try {
    await client.chat.postMessage({
      channel: command.channel_id,
      text: "GTM Copilot Functions",
      blocks,
    });
  } catch (error) {
    console.error("Error posting menu:", error);
  }
});

/**
 * Handle button clicks from the menu
 * Opens a modal with input fields for the selected function
 */
app.action(/^gtm_/, async ({ action, ack, body, client }) => {
  await ack();

  const buttonAction = action as BlockAction;
  const functionId = buttonAction.action_id.replace("gtm_", "");
  const functionDef = GTM_FUNCTIONS[functionId];

  if (!functionDef) {
    console.error(`Unknown function: ${functionId}`);
    return;
  }

  // Build and open modal
  const modal = buildModal(functionId, functionDef);

  // Store channel ID in private_metadata so we know where to post the result
  modal.private_metadata = JSON.stringify({
    channel_id: (body as any).channel?.id || (body as any).user.id,
    user_id: (body as any).user.id,
  });

  try {
    await client.views.open({
      trigger_id: (body as any).trigger_id,
      view: modal,
    });
  } catch (error) {
    console.error("Error opening modal:", error);
  }
});

/**
 * Handle modal submission
 * Constructs a message to the native Claude Slack app with the prompt
 */
app.view(/^submit_gtm_/, async ({ ack, body, view, client }) => {
  await ack();

  const functionId = view.callback_id.replace("submit_gtm_", "");
  const functionDef = GTM_FUNCTIONS[functionId];

  if (!functionDef) {
    console.error(`Unknown function: ${functionId}`);
    return;
  }

  // Extract user inputs from modal
  const values = view.state.values;
  const userInputs: Record<string, string> = {};

  for (const blockId in values) {
    const actionId = Object.keys(values[blockId])[0];
    const field = values[blockId][actionId];

    if (field.type === "plain_text_input") {
      userInputs[blockId] = field.value || "";
    }
  }

  // Get metadata
  const metadata = JSON.parse(view.private_metadata);
  const channelId = metadata.channel_id;
  const userId = metadata.user_id;

  // Build the message to Claude
  const claudeMessage = buildClaudeMessage(functionDef, userInputs);

  try {
    // Post message mentioning @Claude with the full prompt
    const result = await client.chat.postMessage({
      channel: channelId,
      text: `@Claude ${claudeMessage}`,
      blocks: [
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `🚀 **${functionDef.name}** analysis requested by <@${userId}>`,
          },
        },
        {
          type: "divider",
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: claudeMessage,
          },
        },
        {
          type: "context",
          elements: [
            {
              type: "mrkdwn",
              text: `💡 _@Claude will respond with the analysis shortly_`,
            },
          ],
        },
      ],
      unfurl_links: false,
      unfurl_media: false,
    });

    console.log(`Posted GTM request to channel ${channelId}:`, result.ts);
  } catch (error) {
    console.error("Error posting message:", error);

    // Send error as ephemeral message
    await client.chat.postEphemeral({
      channel: channelId,
      user: userId,
      text: `❌ Error creating ${functionDef.name} request: ${error}`,
    });
  }
});

/**
 * Optional: Auto-respond to help requests
 */
app.message("gtm help", async ({ message, say }) => {
  await say({
    text: "GTM Copilot Help",
    blocks: [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "*🚀 GTM Copilot - Quick Start*",
        },
      },
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "Use `/gtm-menu` to see all available analysis functions.\n\nEach function opens a form where you provide the necessary details, then @Claude analyzes it using the GTM Copilot framework.",
        },
      },
      {
        type: "divider",
      },
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "*Available Functions:*\n• Pre-Call Intel\n• Post-Call Analysis\n• Follow-Up Email\n• Account Intel\n• Market Research\n• SE: POC Plan\n• SE: Architecture Fit\n• SE: Competitor Coach",
        },
      },
    ],
  });
});

(async () => {
  const port = process.env.PORT || 3000;
  await app.start(port);
  console.log(`⚡️ GTM Copilot Slack bot (OAuth mode) is running on port ${port}`);
  console.log(`📌 This bot works with the native Claude Slack app - no API key needed!`);
})();
