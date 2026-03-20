from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tokens_used: int = 0
    model: str = ""


class LLMProvider(Protocol):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> LLMResponse: ...

    async def embed(self, text: str | list[str]) -> list[list[float]]: ...
