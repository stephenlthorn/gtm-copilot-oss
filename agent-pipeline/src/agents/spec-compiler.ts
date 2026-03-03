import { runAgent } from "../agent.js";
import { writeDoc } from "../state.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult } from "../types.js";

const SYSTEM_PROMPT = `You are the Spec Compiler Agent for an iOS development team.
You turn sprint tasks into precise engineering specs that engineers can implement without ambiguity.

For each task, write a spec covering:
- Exact file(s) to create or modify
- Function/class/struct signatures
- Input/output contracts
- Edge cases and error handling
- Test cases the engineer must pass
- Swift/SwiftUI/UIKit conventions to follow

Write the combined specs to docs/CURRENT_SPEC.md.
Read existing source files to understand current patterns and avoid duplication.`;

export async function runSpecCompilerAgent(scrumOutput: string): Promise<AgentResult> {
  const prompt = `## Sprint Plan
${scrumOutput}

Write detailed engineering specs for each task. Read existing source files as needed to match patterns.
Save the final spec to docs/CURRENT_SPEC.md.`;

  return runAgent({
    role: "spec-compiler",
    providers: PROVIDERS["spec-compiler"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: prompt,
    allowedTools: TOOLS["spec-compiler"],
  });
}
