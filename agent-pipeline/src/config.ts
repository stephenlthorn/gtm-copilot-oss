import type { AgentRole, AllowedTools, ProviderSpec } from "./types.js";

// ─── Provider chains per role ────────────────────────────────────────────────
// Each role lists providers in priority order. On failure, the next is tried.
// Roles that only use Claude (planning/quality) have a single entry.
// Implementation roles use MiniMax first (fast + cheap), then Codex, then Claude.

export const PROVIDERS: Record<AgentRole, readonly ProviderSpec[]> = {
  // Planning track — Claude only (complex reasoning)
  pm:              [{ provider: "claude",  model: "claude-sonnet-4-6" }],
  scrum:           [{ provider: "claude",  model: "claude-sonnet-4-6" }],
  "spec-compiler": [{ provider: "claude",  model: "claude-sonnet-4-6" }],

  // Engineer swarm — MiniMax → Codex → Claude fallback
  "engineer-ui":   [
    { provider: "minimax", model: "MiniMax-M2.5" },
    { provider: "openai",  model: "codex-5.1" },
    { provider: "claude",  model: "claude-haiku-4-5-20251001" },
  ],
  "engineer-core": [
    { provider: "minimax", model: "MiniMax-M2.5" },
    { provider: "openai",  model: "codex-5.1" },
    { provider: "claude",  model: "claude-haiku-4-5-20251001" },
  ],
  "engineer-tests": [
    { provider: "minimax", model: "MiniMax-M2.5" },
    { provider: "openai",  model: "codex-5.1" },
    { provider: "claude",  model: "claude-haiku-4-5-20251001" },
  ],

  // QA Build/Fix — MiniMax → Codex → Claude fallback
  "qa-build": [
    { provider: "minimax", model: "MiniMax-M2.5" },
    { provider: "openai",  model: "codex-5.1" },
    { provider: "claude",  model: "claude-haiku-4-5-20251001" },
  ],
  "qa-fix-loop": [
    { provider: "minimax", model: "MiniMax-M2.5" },
    { provider: "openai",  model: "codex-5.1" },
    { provider: "claude",  model: "claude-haiku-4-5-20251001" },
  ],

  // QA Regression — Claude only (risk judgement)
  "qa-regression": [{ provider: "claude", model: "claude-sonnet-4-6" }],

  // Commit — MiniMax → Codex → Claude fallback
  commit: [
    { provider: "minimax", model: "MiniMax-M2.5" },
    { provider: "openai",  model: "codex-5.1" },
    { provider: "claude",  model: "claude-haiku-4-5-20251001" },
  ],

  // End User Tester — Claude only (UX synthesis)
  "end-user-tester": [{ provider: "claude", model: "claude-sonnet-4-6" }],

  // Tech Writer — MiniMax → Claude (ADR escalation handled in prompt)
  "tech-writer": [
    { provider: "minimax", model: "MiniMax-M2.5" },
    { provider: "claude",  model: "claude-haiku-4-5-20251001" },
  ],
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
