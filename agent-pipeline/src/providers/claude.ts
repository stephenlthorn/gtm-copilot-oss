import Anthropic from "@anthropic-ai/sdk";
import type { MessageParam } from "@anthropic-ai/sdk/resources/messages.js";
import type { Provider, ProviderRequest, ProviderResponse, ContentBlock } from "./interface.js";

export class ClaudeProvider implements Provider {
  readonly name = "claude";
  private readonly client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: process.env["ANTHROPIC_API_KEY"] });
  }

  async complete(req: ProviderRequest): Promise<ProviderResponse> {
    const response = await this.client.messages.create({
      model: req.model,
      max_tokens: req.maxTokens ?? 8192,
      system: req.systemPrompt,
      tools: req.tools,
      messages: req.messages as MessageParam[],
    });

    const content: ContentBlock[] = [];
    for (const block of response.content) {
      if (block.type === "text") {
        content.push({ type: "text", text: block.text });
      } else if (block.type === "tool_use") {
        content.push({
          type: "tool_use",
          id: block.id,
          name: block.name,
          input: block.input as Record<string, string>,
        });
      }
      // Skip thinking, server_tool_use, web_search_tool_result, redacted_thinking, etc.
    }

    return {
      stopReason: response.stop_reason === "end_turn" ? "end_turn" : "tool_use",
      content,
    };
  }
}
