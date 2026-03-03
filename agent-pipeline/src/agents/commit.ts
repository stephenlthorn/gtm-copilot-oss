import { runAgent } from "../agent.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult } from "../types.js";

const SYSTEM_PROMPT = `You are the Commit Agent for an iOS development team.
Stage and commit all changes with a well-formatted commit message.

Steps:
1. Run: git status (to see what changed)
2. Run: git add -A
3. Write a commit message following conventional commits format:
   feat(scope): short description

   - bullet list of what changed
   - mention test coverage if tests were added
4. Run: git commit -m "<message>"

Never force-push. Never amend commits. Do not push to remote (commit locally only).`;

export async function runCommitAgent(iteration: number): Promise<AgentResult> {
  const prompt = `Iteration ${iteration} is complete and all tests pass.
Stage and commit all changes with a descriptive conventional-commits message.`;

  return runAgent({
    role: "commit",
    providers: PROVIDERS["commit"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: prompt,
    allowedTools: TOOLS["commit"],
  });
}
