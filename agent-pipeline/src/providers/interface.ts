import type { Tool } from "@anthropic-ai/sdk/resources/messages.js";

export type ContentBlock =
  | { type: "text"; text: string }
  | { type: "tool_use"; id: string; name: string; input: Record<string, string> };

export type ProviderMessage =
  | { role: "user"; content: string | ProviderToolResult[] }
  | { role: "assistant"; content: ContentBlock[] };

export type ProviderToolResult = {
  type: "tool_result";
  tool_use_id: string;
  content: string;
};

export type ProviderRequest = {
  readonly model: string;
  readonly systemPrompt: string;
  readonly messages: ProviderMessage[];
  readonly tools: Tool[];
  readonly maxTokens?: number;
};

export type ProviderResponse = {
  readonly stopReason: "end_turn" | "tool_use";
  readonly content: ContentBlock[];
};

export interface Provider {
  readonly name: string;
  complete(req: ProviderRequest): Promise<ProviderResponse>;
}
