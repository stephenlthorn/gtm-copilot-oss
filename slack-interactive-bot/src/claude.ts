import Anthropic from "@anthropic-ai/sdk";
import { GTMFunction } from "./prompts";
import { SYSTEM_PROMPTS } from "./system-prompts";

/**
 * Process user input with Claude API
 * Uses the appropriate system prompt and template
 */
export async function processPrompt(
  anthropic: Anthropic,
  functionDef: GTMFunction,
  userInputs: Record<string, string>
): Promise<string> {
  // Get system prompt
  const systemPrompt = SYSTEM_PROMPTS[functionDef.systemPrompt] || "";

  // Build user message by filling in template with variables
  const userMessage = fillTemplate(functionDef, userInputs);

  // Call Claude API
  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-5-20250514",
    max_tokens: 8000,
    system: systemPrompt,
    messages: [
      {
        role: "user",
        content: userMessage,
      },
    ],
  });

  // Extract text from response
  const textContent = response.content.find((block) => block.type === "text");
  if (!textContent || textContent.type !== "text") {
    throw new Error("No text response from Claude");
  }

  return textContent.text;
}

/**
 * Fill template with user-provided variables
 */
function fillTemplate(
  functionDef: GTMFunction,
  userInputs: Record<string, string>
): string {
  // Get template from TEMPLATES constant (you'll need to import this from your API)
  // For now, we'll construct a basic prompt
  let prompt = `Please complete the following ${functionDef.name} request:\n\n`;

  for (const [key, value] of Object.entries(userInputs)) {
    if (value) {
      prompt += `**${formatLabel(key)}:** ${value}\n\n`;
    }
  }

  prompt += `\nPlease provide a complete and structured analysis following the ${functionDef.name} framework.`;

  return prompt;
}

/**
 * Convert variable name to readable label
 */
function formatLabel(key: string): string {
  return key
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
