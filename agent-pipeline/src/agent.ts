import { getToolDefs, executeTool } from "./tools.js";
import { getProvider } from "./providers/index.js";
import { MAX_AGENT_TURNS } from "./config.js";
import type { AgentRole, AgentResult, AllowedTools, ProviderSpec } from "./types.js";
import type { ProviderMessage, ProviderToolResult } from "./providers/interface.js";

type RunAgentOptions = {
  readonly role: AgentRole;
  readonly providers: readonly ProviderSpec[];
  readonly systemPrompt: string;
  readonly userPrompt: string;
  readonly allowedTools: AllowedTools;
};

export async function runAgent(opts: RunAgentOptions): Promise<AgentResult> {
  const { role, providers, systemPrompt, userPrompt, allowedTools } = opts;
  const tools = getToolDefs(allowedTools);

  for (const spec of providers) {
    try {
      const provider = await getProvider(spec.provider);
      console.log(`  [${role}] using ${spec.provider}/${spec.model}`);

      const messages: ProviderMessage[] = [{ role: "user", content: userPrompt }];
      let toolCallCount = 0;
      let finalOutput = "";

      for (let turn = 0; turn < MAX_AGENT_TURNS; turn++) {
        const response = await provider.complete({
          model: spec.model,
          systemPrompt,
          messages,
          tools,
        });

        for (const block of response.content) {
          if (block.type === "text") finalOutput = block.text;
        }

        if (response.stopReason === "end_turn") break;
        if (response.stopReason !== "tool_use") break;

        // Execute tool calls
        const toolResults: ProviderToolResult[] = [];
        for (const block of response.content) {
          if (block.type !== "tool_use") continue;
          toolCallCount++;
          const output = executeTool(block.name, block.input);
          toolResults.push({ type: "tool_result", tool_use_id: block.id, content: output });
        }

        messages.push({ role: "assistant", content: response.content });
        messages.push({ role: "user", content: toolResults });
      }

      return { role, output: finalOutput, toolCallCount };
    } catch (err) {
      const next = providers[providers.indexOf(spec) + 1];
      if (next) {
        console.warn(`  [${role}] ${spec.provider} failed (${err instanceof Error ? err.message : String(err)}), trying ${next.provider}...`);
      } else {
        throw new Error(`[${role}] All providers exhausted. Last error: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
  }

  throw new Error(`[${role}] No providers configured`);
}
