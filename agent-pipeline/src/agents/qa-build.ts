import { runAgent } from "../agent.js";
import { PROVIDERS, TOOLS } from "../config.js";
import type { AgentResult, QaBuildResult } from "../types.js";

const SYSTEM_PROMPT = `You are the QA Build Agent for an iOS development team.
Run the full project build and test suite using bash_exec. Report pass or fail.

Steps:
1. Use bash_exec to run: xcodebuild build -scheme AppName -destination 'platform=iOS Simulator,name=iPhone 15'
2. If build passes, use bash_exec to run: xcodebuild test -scheme AppName -destination 'platform=iOS Simulator,name=iPhone 15'
3. Report ALL errors and failures verbatim.

Your final message MUST end with one of:
  BUILD_STATUS: PASS
or
  BUILD_STATUS: FAIL
  ERRORS: <paste full error output here>`;

export async function runQaBuildAgent(): Promise<QaBuildResult> {
  const result: AgentResult = await runAgent({
    role: "qa-build",
    providers: PROVIDERS["qa-build"],
    systemPrompt: SYSTEM_PROMPT,
    userPrompt: "Run the build and tests. Report BUILD_STATUS: PASS or FAIL with full error details.",
    allowedTools: TOOLS["qa-build"],
  });

  const output = result.output;
  if (output.includes("BUILD_STATUS: PASS")) return { pass: true };

  const errorsMatch = /ERRORS:\s*([\s\S]+)/.exec(output);
  const errors = errorsMatch?.[1]?.trim() ?? output;
  return { pass: false, errors };
}
