import { runAgent } from "../agent.js";
import { readDoc } from "../state.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult, EngineerVariant } from "../types.js";

const FOCUS: Record<EngineerVariant, string> = {
  ui: "SwiftUI views, navigation, and UI components",
  core: "business logic, models, services, and data layer",
  tests: "XCTest unit tests and XCUITest UI tests",
};

function systemPrompt(variant: EngineerVariant): string {
  return `You are the ${variant.toUpperCase()} Engineer Agent for an iOS team.
Your focus: ${FOCUS[variant]}

Follow the spec in docs/CURRENT_SPEC.md exactly. Only implement tasks assigned to your domain.
Write idiomatic Swift. Follow existing patterns in the codebase.
Use read_file to understand context before editing. Use write_file to write code.
Run swift build or xcodebuild to verify your changes compile.

Do not implement other engineers' tasks. If you see a dependency missing, note it in your output.`;
}

export async function runEngineerAgent(
  variant: EngineerVariant,
  specOutput: string,
): Promise<AgentResult> {
  const spec = readDoc("docs/CURRENT_SPEC.md");
  const architecture = readDoc("docs/ARCHITECTURE.md");

  const roleMap: Record<EngineerVariant, "engineer-ui" | "engineer-core" | "engineer-tests"> = {
    ui: "engineer-ui",
    core: "engineer-core",
    tests: "engineer-tests",
  };
  const role = roleMap[variant];

  const prompt = `## Your Variant: ${variant.toUpperCase()} Engineer

## Spec
${spec || specOutput}

## Architecture Reference
${architecture.slice(0, 1500)}

Implement only the ${variant} tasks from the spec. Read existing files first to understand patterns.
Verify your code compiles after writing. Report what you implemented and any issues encountered.`;

  return runAgent({
    role,
    providers: PROVIDERS[role],
    systemPrompt: systemPrompt(variant),
    userPrompt: prompt,
    allowedTools: TOOLS[role],
  });
}
