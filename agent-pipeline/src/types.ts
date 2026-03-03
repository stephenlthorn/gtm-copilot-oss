export type ProviderName = "claude" | "openai" | "minimax";

export type ProviderSpec = {
  readonly provider: ProviderName;
  readonly model: string;
};

export type AgentRole =
  | "pm"
  | "scrum"
  | "spec-compiler"
  | "engineer-ui"
  | "engineer-core"
  | "engineer-tests"
  | "qa-build"
  | "qa-fix-loop"
  | "qa-regression"
  | "commit"
  | "end-user-tester"
  | "tech-writer";

export type EngineerVariant = "ui" | "core" | "tests";

export type ToolName =
  | "read_file"
  | "write_file"
  | "bash_exec"
  | "glob_files"
  | "grep_files";

export type AllowedTools = ReadonlyArray<ToolName>;

export type QaBuildResult =
  | { pass: true }
  | { pass: false; errors: string };

export type PipelineState = {
  readonly phase: string;
  readonly totalIterations: number;
  readonly lastQAStatus: "pass" | "fail" | "unknown";
  readonly lastUpdated: string;
};

export type AgentResult = {
  readonly role: AgentRole;
  readonly output: string;
  readonly toolCallCount: number;
};
