import { runAgent } from "../agent.js";
import { readDoc } from "../state.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult } from "../types.js";

const SYSTEM_PROMPT = `You are the End User Tester Agent for an iOS app.
You test the app from a real user's perspective after each iteration.

Your approach:
1. Read the PRD to understand intended user flows
2. Read the sprint plan to understand what changed this iteration
3. Attempt to run the app or invoke key flows via bash_exec
4. Evaluate: does the feature work as a user would expect?
5. Write structured feedback to docs/USER_FEEDBACK.md:
   - What worked well
   - What was confusing or broken from a UX perspective
   - Specific suggestions for the next iteration

Write from the user's POV, not the engineer's. Report UX issues, not code issues.`;

export async function runEndUserTesterAgent(): Promise<AgentResult> {
  const prd = readDoc("docs/PRD.md");
  const sprintLog = readDoc("docs/SPRINT_LOG.md");
  const existingFeedback = readDoc("docs/USER_FEEDBACK.md");

  const prompt = `## PRD (user expectations)
${prd.slice(0, 2000)}

## What changed this sprint
${sprintLog.slice(-1000)}

## Previous feedback (context)
${existingFeedback.slice(-500)}

Test the app as a real user would. Append your feedback to docs/USER_FEEDBACK.md.`;

  return runAgent({
    role: "end-user-tester",
    providers: PROVIDERS["end-user-tester"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: prompt,
    allowedTools: TOOLS["end-user-tester"],
  });
}
