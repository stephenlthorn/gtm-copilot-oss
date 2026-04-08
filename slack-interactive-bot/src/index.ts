import { App, BlockAction, ViewSubmission } from "@slack/bolt";
import Anthropic from "@anthropic-ai/sdk";
import dotenv from "dotenv";
import { getPromptMenu, GTM_FUNCTIONS } from "./prompts";
import { buildModal } from "./modals";
import { processPrompt } from "./claude";

dotenv.config();

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
});

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
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
 * Collects user input and calls Claude API
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

  // Get channel ID from private_metadata
  const channelId = view.private_metadata;
  const userId = body.user.id;

  // Post "processing" message
  const processingMsg = await client.chat.postMessage({
    channel: channelId,
    text: `⏳ Processing your **${functionDef.name}** request...`,
    blocks: [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `⏳ Processing your **${functionDef.name}** request...\n\n_This may take 30-60 seconds._`,
        },
      },
    ],
  });

  try {
    // Call Claude API
    const result = await processPrompt(
      anthropic,
      functionDef,
      userInputs
    );

    // Update message with result
    await client.chat.update({
      channel: channelId,
      ts: processingMsg.ts!,
      text: `✅ ${functionDef.name} Complete`,
      blocks: [
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `✅ **${functionDef.name} Complete**`,
          },
        },
        {
          type: "divider",
        },
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: result,
          },
        },
        {
          type: "context",
          elements: [
            {
              type: "mrkdwn",
              text: `Requested by <@${userId}>`,
            },
          ],
        },
      ],
    });
  } catch (error) {
    console.error("Error processing prompt:", error);

    await client.chat.update({
      channel: channelId,
      ts: processingMsg.ts!,
      text: "❌ Error processing request",
      blocks: [
        {
          type: "section",
          text: {
            type: "mrkdwn",
            text: `❌ **Error processing ${functionDef.name}**\n\n\`\`\`\n${error}\n\`\`\``,
          },
        },
      ],
    });
  }
});

(async () => {
  const port = process.env.PORT || 3000;
  await app.start(port);
  console.log(`⚡️ GTM Copilot Slack bot is running on port ${port}`);
})();
