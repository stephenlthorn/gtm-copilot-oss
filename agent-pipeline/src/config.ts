import type { AgentRole, AllowedTools, ProviderSpec } from "./types.js";

// ─── Provider chains per role ────────────────────────────────────────────────
// All roles use OpenAI (Codex) via OAuth token.

export const PROVIDERS: Record<AgentRole, readonly ProviderSpec[]> = {
  pm:               [{ provider: "openai", model: "codex-5.1" }],
  scrum:            [{ provider: "openai", model: "codex-5.1" }],
  "spec-compiler":  [{ provider: "openai", model: "codex-5.1" }],
  "engineer-ui":    [{ provider: "openai", model: "codex-5.1" }],
  "engineer-core":  [{ provider: "openai", model: "codex-5.1" }],
  "engineer-tests": [{ provider: "openai", model: "codex-5.1" }],
  "qa-build":       [{ provider: "openai", model: "codex-5.1" }],
  "qa-fix-loop":    [{ provider: "openai", model: "codex-5.1" }],
  "qa-regression":  [{ provider: "openai", model: "codex-5.1" }],
  commit:           [{ provider: "openai", model: "codex-5.1" }],
  "end-user-tester":[{ provider: "openai", model: "codex-5.1" }],
  "tech-writer":    [{ provider: "openai", model: "codex-5.1" }],
};

// ─── Tool access per role ─────────────────────────────────────────────────────
export const TOOLS: Record<AgentRole, AllowedTools> = {
  pm:              ["read_file", "glob_files", "grep_files"],
  scrum:           ["read_file", "glob_files", "grep_files", "write_file"],
  "spec-compiler": ["read_file", "glob_files", "grep_files", "write_file"],
  "engineer-ui":   ["read_file", "write_file", "bash_exec", "glob_files", "grep_files"],
  "engineer-core": ["read_file", "write_file", "bash_exec", "glob_files", "grep_files"],
  "engineer-tests":["read_file", "write_file", "bash_exec", "glob_files", "grep_files"],
  "qa-build":      ["read_file", "write_file", "bash_exec", "glob_files"],
  "qa-fix-loop":   ["read_file", "write_file", "bash_exec", "glob_files", "grep_files"],
  "qa-regression": ["read_file", "bash_exec", "glob_files"],
  commit:          ["bash_exec"],
  "end-user-tester":["read_file", "write_file", "bash_exec"],
  "tech-writer":   ["read_file", "write_file", "glob_files"],
};

export const MAX_AGENT_TURNS = 40;
export const QA_MAX_RETRIES = Number(process.env["QA_MAX_RETRIES"] ?? "5");
export const IOS_APP_ROOT = process.env["IOS_APP_ROOT"] ?? "../";
