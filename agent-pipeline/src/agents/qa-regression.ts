import { runAgent } from "../agent.js";
import { readDoc } from "../state.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult } from "../types.js";

const SYSTEM_PROMPT = `You are the QA Regression Agent for an iOS development team.
You do risk-based regression testing after a build passes.

Your job:
1. Read the sprint plan and spec to understand what changed
2. Identify the 3-5 highest-risk regression areas (what could have broken)
3. Run targeted tests for those areas using bash_exec
4. Read test output and summarize: REGRESSION_STATUS: PASS or FAIL

You cannot edit source files — read and run tests only.
Focus on areas adjacent to what changed, not just the happy path.`;

export async function runQaRegressionAgent(): Promise<AgentResult> {
  const sprintLog = readDoc("docs/SPRINT_LOG.md");
  const spec = readDoc("docs/CURRENT_SPEC.md");

  const prompt = `## Sprint Plan (what changed)
${sprintLog.slice(-1500)}

## Spec
${spec.slice(0, 2000)}

Identify regression risk areas and run targeted tests. Report REGRESSION_STATUS: PASS or FAIL.`;

  return runAgent({
    role: "qa-regression",
    providers: PROVIDERS["qa-regression"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: prompt,
    allowedTools: TOOLS["qa-regression"],
  });
}
