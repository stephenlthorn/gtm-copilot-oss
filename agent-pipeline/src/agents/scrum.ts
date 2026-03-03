import { runAgent } from "../agent.js";
import { readDoc, writeDoc } from "../state.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult } from "../types.js";

const SYSTEM_PROMPT = `You are the Scrum Master Agent for an iOS development team.
You receive the PM's iteration goals and break them into a concrete sprint plan.

Output a sprint plan with:
- Sprint goal (one sentence)
- Ordered task list (each task: title, acceptance criteria, owner role)
- Dependencies between tasks
- Definition of Done for the sprint

Update docs/SPRINT_LOG.md by appending this sprint's plan.
Keep tasks small enough for a single engineer agent to complete in one session.`;

export async function runScrumAgent(pmOutput: string): Promise<AgentResult> {
  const sprintLog = readDoc("docs/SPRINT_LOG.md");
  const architecture = readDoc("docs/ARCHITECTURE.md");

  const prompt = `## PM Iteration Goals
${pmOutput}

## Current Architecture
${architecture.slice(0, 2000)}

## Existing Sprint Log (for context)
${sprintLog.slice(-1500)}

Break the PM's goals into a sprint plan. Update docs/SPRINT_LOG.md with this sprint's plan.
Use read_file to inspect relevant source files if needed to estimate task scope.`;

  return runAgent({
    role: "scrum",
    providers: PROVIDERS["scrum"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: prompt,
    allowedTools: TOOLS["scrum"],
  });
}
