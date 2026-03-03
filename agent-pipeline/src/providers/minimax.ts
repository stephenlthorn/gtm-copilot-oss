import OpenAI from "openai";
import type { Provider, ProviderRequest, ProviderResponse } from "./interface.js";
import { toOpenAIMessages, toOpenAITools, fromOpenAIResponse } from "./openai-compat.js";

export class MiniMaxProvider implements Provider {
  readonly name = "minimax";
  private readonly client: OpenAI;

  constructor() {
    const apiKey = process.env["MINIMAX_API_KEY"];
    const groupId = process.env["MINIMAX_GROUP_ID"];
    if (!apiKey) throw new Error("MINIMAX_API_KEY is not set");
    if (!groupId) throw new Error("MINIMAX_GROUP_ID is not set");

    this.client = new OpenAI({
      apiKey,
      baseURL: "https://api.minimax.chat/v1",
      defaultHeaders: { "MiniMax-GroupId": groupId },
    });
  }

  async complete(req: ProviderRequest): Promise<ProviderResponse> {
    const response = await this.client.chat.completions.create({
      model: req.model,
      max_tokens: req.maxTokens ?? 8192,
      messages: toOpenAIMessages(req.systemPrompt, req.messages),
      ...(req.tools.length ? { tools: toOpenAITools(req.tools), tool_choice: "auto" as const } : {}),
    });

    const choice = response.choices[0];
    if (!choice) throw new Error("MiniMax returned no choices");
    return fromOpenAIResponse(choice);
  }
}
