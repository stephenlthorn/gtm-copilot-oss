# Multi-Provider Support Design

**Date:** 2026-03-03

## Problem

The initial pipeline hardcodes `@anthropic-ai/sdk` and Claude models. The original `ios-dev-co` pipeline used multiple providers (MiniMax M2.5, Codex via OAuth, Sonnet) with fallback chains per role. This design restores that capability.

## Approach: Provider Factory + Fallback Chain

Each agent role declares an **ordered list** of `{ provider, model }` specs. The agent runner tries each in sequence, falling back if any throws.

## Provider Interface

```typescript
interface Provider {
  name: string;
  complete(req: ProviderRequest): Promise<ProviderResponse>;
}
```

All providers normalize their response to a shared `ProviderResponse` type (same content block shape), so the agentic loop in `agent.ts` is provider-agnostic.

## Providers

| Provider | Package | Auth |
|----------|---------|------|
| Claude | `@anthropic-ai/sdk` | `ANTHROPIC_API_KEY` |
| OpenAI / Codex | `openai` | `OPENAI_OAUTH_TOKEN` (OAuth-issued token as bearer) |
| MiniMax | `openai` (OpenAI-compat) | `MINIMAX_API_KEY` + `MINIMAX_GROUP_ID` |

## Role → Provider Mapping (default)

| Role | Primary | Fallback 1 | Fallback 2 |
|------|---------|------------|------------|
| PM, Scrum, Spec, QA Regression, End User Tester | Claude Sonnet | — | — |
| Engineer UI/Core/Tests, QA Build/Fix, Commit, Tech Writer | MiniMax M2.5 | Codex (openai) | Claude Haiku |

## Fallback Trigger

Any thrown error causes fallback. (All errors — not just rate limits — since cold errors from MiniMax or OAuth expiry are equally blocking.)

## Files Changed

- `src/types.ts` — add `ProviderSpec`, `ProviderName`
- `src/providers/interface.ts` — `Provider`, `ProviderRequest`, `ProviderResponse`
- `src/providers/claude.ts` — `ClaudeProvider`
- `src/providers/openai.ts` — `OpenAIProvider` (Codex)
- `src/providers/minimax.ts` — `MiniMaxProvider`
- `src/providers/index.ts` — `getProvider()` factory
- `src/config.ts` — replace `MODEL` with `PROVIDERS` per role
- `src/agent.ts` — implement fallback chain loop
- `.env.example` — add `OPENAI_OAUTH_TOKEN`, `MINIMAX_API_KEY`, `MINIMAX_GROUP_ID`
