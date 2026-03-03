import { runAgent } from "../agent.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult } from "../types.js";

const SYSTEM_PROMPT = `You are the QA Fix Loop Agent for an iOS development team.
You receive build/test errors and fix them.

Strategy:
1. Read the failing file(s) with read_file
2. Understand the root cause — don't guess
3. Fix the minimal amount of code needed
4. Verify the fix compiles with bash_exec before finishing
5. Report what you changed and why

Fix only compilation and test errors. Do not add features or refactor unrelated code.
If an error is in generated code or a dependency, note it and skip.`;

export async function runQaFixLoopAgent(attempt: number, errors: string): Promise<AgentResult> {
  const prompt = `QA build/test failed (attempt ${attempt + 1}).

## Errors
${errors}

Fix the errors above. Read the relevant files first, then fix, then verify with bash_exec.`;

  return runAgent({
    role: "qa-fix-loop",
    providers: PROVIDERS["qa-fix-loop"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: prompt,
    allowedTools: TOOLS["qa-fix-loop"],
  });
}
