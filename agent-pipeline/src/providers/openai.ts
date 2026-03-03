import OpenAI from "openai";
import type { Provider, ProviderRequest, ProviderResponse } from "./interface.js";
import { toOpenAIMessages, toOpenAITools, fromOpenAIResponse } from "./openai-compat.js";

export class OpenAIProvider implements Provider {
  readonly name = "openai";
  protected readonly client: OpenAI;

  constructor() {
    const token = process.env["OPENAI_OAUTH_TOKEN"];
    if (!token) throw new Error("OPENAI_OAUTH_TOKEN is not set");
    this.client = new OpenAI({ apiKey: token });
  }

  async complete(req: ProviderRequest): Promise<ProviderResponse> {
    const response = await this.client.chat.completions.create({
      model: req.model,
      max_tokens: req.maxTokens ?? 8192,
      messages: toOpenAIMessages(req.systemPrompt, req.messages),
      ...(req.tools.length ? { tools: toOpenAITools(req.tools), tool_choice: "auto" as const } : {}),
    });

    const choice = response.choices[0];
    if (!choice) throw new Error("OpenAI returned no choices");
    return fromOpenAIResponse(choice);
  }
}
