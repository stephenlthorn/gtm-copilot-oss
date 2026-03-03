import { runAgent } from "../agent.js";
import { readState, readDoc } from "../state.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult } from "../types.js";

const SYSTEM_PROMPT = `You are the PM Agent for an iOS development team.
Your job is to read the current project state and living docs, then define clear iteration goals.

Output a concise iteration plan:
- Current phase summary
- 3-5 specific goals for this iteration
- Any blockers or open questions
- Success criteria

Be concrete. Reference specific features, bugs, or doc sections by name.
Do not write code. Do not edit files directly — just read and reason.`;

export async function runPmAgent(): Promise<AgentResult> {
  const state = readState();
  const prd = readDoc("docs/PRD.md");
  const backlog = readDoc("docs/BACKLOG.md");
  const feedback = readDoc("docs/USER_FEEDBACK.md");
  const sprintLog = readDoc("docs/SPRINT_LOG.md");

  const prompt = `Current pipeline state:
- Phase: ${state.phase}
- Total iterations completed: ${state.totalIterations}
- Last QA status: ${state.lastQAStatus}
- Last updated: ${state.lastUpdated}

## PRD (excerpt)
${prd.slice(0, 3000)}

## Backlog (excerpt)
${backlog.slice(0, 2000)}

## User Feedback (latest)
${feedback.slice(-1500)}

## Sprint Log (last entries)
${sprintLog.slice(-1000)}

Based on the above, define the goals for this iteration. Use your read_file and glob_files tools if you need to inspect specific source files before deciding.`;

  return runAgent({
    role: "pm",
    providers: PROVIDERS["pm"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: prompt,
    allowedTools: TOOLS["pm"],
  });
}
