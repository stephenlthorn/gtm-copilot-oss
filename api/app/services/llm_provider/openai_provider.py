from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from .base import LLMResponse


class OpenAIProvider:
    """LLM provider backed by the OpenAI API."""

    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4.1",
        embedding_model: str = "text-embedding-3-small",
        base_url: str | None = None,
    ) -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.default_model = default_model
        self.embedding_model = embedding_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            tokens_used=response.usage.total_tokens if response.usage else 0,
            model=response.model,
        )

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        input_text = text if isinstance(text, list) else [text]
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=input_text,
        )
        return [item.embedding for item in response.data]
