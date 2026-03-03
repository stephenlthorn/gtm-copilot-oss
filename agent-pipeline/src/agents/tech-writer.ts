import { runAgent } from "../agent.js";
import { readDoc } from "../state.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult } from "../types.js";

const SYSTEM_PROMPT = `You are the Tech Writer Agent for an iOS development team.
You update living documentation after each iteration.

Documents to update as needed:
- docs/CHANGELOG.md — add entry for what changed this iteration
- docs/ARCHITECTURE.md — update if architecture changed
- docs/BACKLOG.md — mark completed items, add newly discovered items
- docs/decisions/ADR-NNN.md — write a new ADR if a significant decision was made

Guidelines:
- Keep CHANGELOG entries concise (3-5 bullet points per version)
- ADRs should be written only for significant, non-obvious decisions
- Do not rewrite history — append only, do not remove old entries
- Read the current state of each doc before updating`;

export async function runTechWriterAgent(commitOutput: string): Promise<AgentResult> {
  const changelog = readDoc("docs/CHANGELOG.md");
  const backlog = readDoc("docs/BACKLOG.md");
  const sprintLog = readDoc("docs/SPRINT_LOG.md");

  const prompt = `## Commit Summary
${commitOutput}

## Sprint Log
${sprintLog.slice(-1000)}

## Current CHANGELOG (tail)
${changelog.slice(-1000)}

## Current BACKLOG (excerpt)
${backlog.slice(-1000)}

Update CHANGELOG.md and BACKLOG.md. Write an ADR only if a significant architectural decision was made.`;

  return runAgent({
    role: "tech-writer",
    providers: PROVIDERS["tech-writer"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: prompt,
    allowedTools: TOOLS["tech-writer"],
  });
}
