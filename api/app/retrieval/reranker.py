from __future__ import annotations

import json
import logging

from app.retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a relevance scorer for a go-to-market sales intelligence system.
Score each passage 0-10 for how useful it is for answering the query.

Scoring guide:
10 — directly and specifically answers the query with concrete details
8-9 — highly relevant, contains key evidence or information
6-7 — relevant, contributes useful context
3-5 — partially relevant, tangential connection
1-2 — mostly irrelevant, surface-level match only
0   — completely off-topic

Return ONLY valid JSON in this exact format: {"scores": [n, n, n, ...]}
One integer per passage, in the same order. Nothing else."""


class LLMReranker:
    def __init__(self) -> None:
        from app.core.settings import get_settings
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        if self._client is None and self.settings.openai_api_key:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )
        return self._client

    def rerank(
        self,
        query: str,
        hits: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Re-score hits with GPT-4o-mini and return top_k by relevance.

        Falls back to original ordering if LLM is unavailable.
        """
        client = self._get_client()
        if not client or not hits:
            return hits[:top_k]

        batch_size = 40
        scored: list[tuple[float, RetrievedChunk]] = []

        for i in range(0, len(hits), batch_size):
            batch = hits[i: i + batch_size]
            scores = self._score_batch(client, query, batch)
            for hit, score in zip(batch, scores):
                scored.append((score, hit))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [hit for _, hit in scored[:top_k]]

    def _score_batch(self, client, query: str, hits: list[RetrievedChunk]) -> list[float]:
        # Include source type context so the reranker knows what it's reading
        passages = "\n\n".join(
            f"[{i + 1}] ({hit.source_type}) {hit.text[:800]}"
            for i, hit in enumerate(hits)
        )
        user_msg = f"Query: {query}\n\nPassages to score:\n{passages}"

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=300,
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            scores = data.get("scores") or []
            # Pad to batch size in case the model returns fewer
            while len(scores) < len(hits):
                scores.append(5.0)
            return [float(s) for s in scores[: len(hits)]]
        except Exception as exc:
            logger.warning("LLMReranker._score_batch failed: %s", exc)
            return [hit.score for hit in hits]
