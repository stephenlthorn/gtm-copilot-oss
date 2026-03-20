from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.llm_provider.openai_provider import OpenAIProvider
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_MAX_BATCH_SIZE = 100


@dataclass
class EmbeddingUsage:
    total_tokens: int = 0
    total_requests: int = 0
    total_chunks: int = 0


class EmbeddingService:
    def __init__(self, provider: OpenAIProvider | None = None) -> None:
        self.settings = get_settings()
        if provider is not None:
            self._provider = provider
        elif self.settings.openai_api_key:
            self._provider = OpenAIProvider(
                api_key=self.settings.openai_api_key,
                embedding_model=self.settings.openai_embedding_model,
                base_url=self.settings.openai_base_url,
            )
        else:
            self._provider = None
        self.usage = EmbeddingUsage()

    async def embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        if not chunks:
            return []

        if self._provider is None:
            logger.warning("No embedding provider configured; returning empty vectors")
            dim = self.settings.embedding_dimensions
            return [[0.0] * dim for _ in chunks]

        all_embeddings: list[list[float]] = []

        for start in range(0, len(chunks), _MAX_BATCH_SIZE):
            batch = chunks[start : start + _MAX_BATCH_SIZE]
            embeddings = await self._provider.embed(batch)
            all_embeddings.extend(embeddings)
            self.usage.total_requests += 1
            self.usage.total_chunks += len(batch)
            estimated_tokens = sum(max(1, len(t.split())) for t in batch)
            self.usage.total_tokens += estimated_tokens

        return all_embeddings
