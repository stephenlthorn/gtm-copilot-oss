/**
 * Shared message conversion for OpenAI-compatible providers (OpenAI, MiniMax).
 * Both use the same chat completions API format.
 */
import OpenAI from "openai";
import type { Tool } from "@anthropic-ai/sdk/resources/messages.js";
import type { ContentBlock, ProviderMessage, ProviderResponse } from "./interface.js";

export function toOpenAIMessages(
  systemPrompt: string,
  messages: ProviderMessage[],
): OpenAI.Chat.ChatCompletionMessageParam[] {
  const result: OpenAI.Chat.ChatCompletionMessageParam[] = [
    { role: "system", content: systemPrompt },
  ];

  for (const msg of messages) {
    if (msg.role === "user") {
      if (typeof msg.content === "string") {
        result.push({ role: "user", content: msg.content });
      } else {
        for (const r of msg.content) {
          result.push({ role: "tool", tool_call_id: r.tool_use_id, content: r.content });
        }
      }
    } else {
      const text = msg.content
        .filter((b): b is { type: "text"; text: string } => b.type === "text")
        .map((b) => b.text)
        .join("");

      const toolCalls: OpenAI.Chat.ChatCompletionMessageToolCall[] = msg.content
        .filter((b): b is { type: "tool_use"; id: string; name: string; input: Record<string, string> } => b.type === "tool_use")
        .map((b) => ({
          id: b.id,
          type: "function" as const,
          function: { name: b.name, arguments: JSON.stringify(b.input) },
        }));

      result.push({
        role: "assistant",
        content: text || null,
        ...(toolCalls.length ? { tool_calls: toolCalls } : {}),
      });
    }
  }

  return result;
}

export function toOpenAITools(tools: Tool[]): OpenAI.Chat.ChatCompletionTool[] {
  return tools.map((t) => ({
    type: "function" as const,
    function: {
      name: t.name,
      description: t.description ?? "",
      parameters: t.input_schema as Record<string, unknown>,
    },
  }));
}

export function fromOpenAIResponse(
  choice: OpenAI.Chat.ChatCompletion.Choice,
): ProviderResponse {
  const content: ContentBlock[] = [];

  if (choice.message.content) {
    content.push({ type: "text", text: choice.message.content });
  }

  for (const call of choice.message.tool_calls ?? []) {
    if (call.type !== "function") continue;
    content.push({
      type: "tool_use",
      id: call.id,
      name: call.function.name,
      input: JSON.parse(call.function.arguments) as Record<string, string>,
    });
  }

  return {
    stopReason: choice.finish_reason === "tool_calls" ? "tool_use" : "end_turn",
    content,
  };
}
