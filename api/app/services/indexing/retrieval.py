from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.services.indexing.embedder import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievalResult:
    chunk_text: str
    source_type: str
    source_ref: str
    title: str
    score: float
    metadata: dict


class HybridRetrievalService:
    def __init__(self, db: Session, embedding_service: EmbeddingService | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self.embedding_service = embedding_service or EmbeddingService()

    async def search(
        self,
        query: str,
        org_id: int,
        top_k: int = 10,
        source_types: list[str] | None = None,
    ) -> list[RetrievalResult]:
        from sqlalchemy import select as sa_select
        from app.models.entities import KBConfig

        config = self.db.execute(sa_select(KBConfig).limit(1)).scalar_one_or_none()
        cutover = config.retrieval_cutover if config is not None else False

        query_embeddings = await self.embedding_service.embed_chunks([query])
        query_vec = query_embeddings[0] if query_embeddings else []

        vector_results = self._vector_search(query_vec, org_id, source_types)
        fulltext_results = self._fulltext_search(query, org_id, source_types)

        if not cutover:
            vector_results = vector_results + self._legacy_vector_search(query_vec, top_k * 2)
            fulltext_results = fulltext_results + self._legacy_fulltext_search(query, top_k * 2)

        fused = self._reciprocal_rank_fusion(vector_results, fulltext_results)

        seen: set[str] = set()
        deduplicated: list[RetrievalResult] = []
        for result in fused:
            dedup_key = f"{result.source_ref}:{result.chunk_text[:100]}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            deduplicated.append(result)

        return deduplicated[:top_k]

    def _vector_search(
        self,
        query_vec: list[float],
        org_id: int,
        source_types: list[str] | None,
    ) -> list[RetrievalResult]:
        if not query_vec:
            return []

        dialect = (self.db.bind.dialect.name if self.db.bind is not None else "").lower()

        if dialect in ("mysql", "mariadb"):
            return self._vector_search_tidb(query_vec, org_id, source_types)
        return self._vector_search_generic(query_vec, org_id, source_types)

    def _vector_search_tidb(
        self,
        query_vec: list[float],
        org_id: int,
        source_types: list[str] | None,
    ) -> list[RetrievalResult]:
        vec_json = json.dumps(query_vec)

        source_filter = ""
        params: dict = {"org_id": org_id, "query_vec": vec_json}
        if source_types:
            placeholders = ", ".join(f":st_{i}" for i in range(len(source_types)))
            source_filter = f"AND source_type IN ({placeholders})"
            for i, st in enumerate(source_types):
                params[f"st_{i}"] = st

        sql = f"""
            SELECT *, VEC_COSINE_DISTANCE(embedding, :query_vec) AS distance
            FROM knowledge_index
            WHERE org_id = :org_id {source_filter}
            ORDER BY distance ASC
            LIMIT 20
        """

        try:
            rows = self.db.execute(text(sql), params).mappings().all()
        except Exception as exc:
            logger.warning("TiDB vector search failed: %s", exc)
            return []

        results: list[RetrievalResult] = []
        for row in rows:
            distance = float(row.get("distance", 1.0))
            score = max(0.0, 1.0 - distance)
            results.append(
                RetrievalResult(
                    chunk_text=row.get("chunk_text", ""),
                    source_type=row.get("source_type", ""),
                    source_ref=row.get("source_ref", ""),
                    title=row.get("title", ""),
                    score=score,
                    metadata=row.get("metadata", {}) or {},
                )
            )
        return results

    def _vector_search_generic(
        self,
        query_vec: list[float],
        org_id: int,
        source_types: list[str] | None,
    ) -> list[RetrievalResult]:
        from app.models.entities import KnowledgeIndex
        from sqlalchemy import select

        import math

        stmt = select(KnowledgeIndex).where(KnowledgeIndex.org_id == org_id)
        if source_types:
            stmt = stmt.where(KnowledgeIndex.source_type.in_(source_types))
        stmt = stmt.limit(200)

        rows = self.db.execute(stmt).scalars().all()

        scored: list[tuple[float, KnowledgeIndex]] = []
        for row in rows:
            embedding = row.embedding
            if embedding is None:
                continue
            if isinstance(embedding, str):
                try:
                    embedding = json.loads(embedding)
                except (json.JSONDecodeError, TypeError):
                    continue

            score = self._cosine_similarity(query_vec, embedding)
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[RetrievalResult] = []
        for score, row in scored[:20]:
            results.append(
                RetrievalResult(
                    chunk_text=row.chunk_text or "",
                    source_type=row.source_type.value if hasattr(row.source_type, "value") else str(row.source_type),
                    source_ref=row.source_ref or "",
                    title=row.title or "",
                    score=score,
                    metadata=row.metadata_ or {},
                )
            )
        return results

    def _fulltext_search(
        self,
        query: str,
        org_id: int,
        source_types: list[str] | None,
    ) -> list[RetrievalResult]:
        dialect = (self.db.bind.dialect.name if self.db.bind is not None else "").lower()

        if dialect in ("mysql", "mariadb"):
            return self._fulltext_search_tidb(query, org_id, source_types)
        return self._fulltext_search_generic(query, org_id, source_types)

    def _fulltext_search_tidb(
        self,
        query: str,
        org_id: int,
        source_types: list[str] | None,
    ) -> list[RetrievalResult]:
        source_filter = ""
        params: dict = {"org_id": org_id, "query": query}
        if source_types:
            placeholders = ", ".join(f":st_{i}" for i in range(len(source_types)))
            source_filter = f"AND source_type IN ({placeholders})"
            for i, st in enumerate(source_types):
                params[f"st_{i}"] = st

        sql = f"""
            SELECT *, MATCH(chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE) AS relevance
            FROM knowledge_index
            WHERE org_id = :org_id
              AND MATCH(chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE)
              {source_filter}
            ORDER BY relevance DESC
            LIMIT 20
        """

        try:
            rows = self.db.execute(text(sql), params).mappings().all()
        except Exception as exc:
            logger.warning("TiDB fulltext search failed (index may not exist): %s", exc)
            return self._fulltext_search_generic(query, org_id, source_types)

        results: list[RetrievalResult] = []
        max_relevance = max((float(r.get("relevance", 0)) for r in rows), default=1.0) or 1.0
        for row in rows:
            relevance = float(row.get("relevance", 0))
            score = relevance / max_relevance if max_relevance > 0 else 0.0
            results.append(
                RetrievalResult(
                    chunk_text=row.get("chunk_text", ""),
                    source_type=row.get("source_type", ""),
                    source_ref=row.get("source_ref", ""),
                    title=row.get("title", ""),
                    score=score,
                    metadata=row.get("metadata", {}) or {},
                )
            )
        return results

    def _fulltext_search_generic(
        self,
        query: str,
        org_id: int,
        source_types: list[str] | None,
    ) -> list[RetrievalResult]:
        from app.models.entities import KnowledgeIndex
        from sqlalchemy import or_, select

        like_term = f"%{query}%"
        stmt = (
            select(KnowledgeIndex)
            .where(KnowledgeIndex.org_id == org_id)
            .where(
                or_(
                    KnowledgeIndex.chunk_text.ilike(like_term),
                    KnowledgeIndex.title.ilike(like_term),
                )
            )
        )
        if source_types:
            stmt = stmt.where(KnowledgeIndex.source_type.in_(source_types))
        stmt = stmt.limit(20)

        rows = self.db.execute(stmt).scalars().all()

        results: list[RetrievalResult] = []
        for row in rows:
            score = 0.5
            results.append(
                RetrievalResult(
                    chunk_text=row.chunk_text or "",
                    source_type=row.source_type.value if hasattr(row.source_type, "value") else str(row.source_type),
                    source_ref=row.source_ref or "",
                    title=row.title or "",
                    score=score,
                    metadata=row.metadata_ or {},
                )
            )
        return results

    def _legacy_vector_search(self, query_vec: list[float], limit: int = 20) -> list[RetrievalResult]:
        """Fan-out vector search to kb_chunks during migration transition."""
        if not query_vec:
            return []
        try:
            import json as _json
            from sqlalchemy import select as sa_select
            from app.models.entities import KBChunk, KBDocument

            rows = self.db.execute(
                sa_select(KBChunk, KBDocument.title, KBDocument.source_type, KBDocument.source_id)
                .join(KBDocument, KBChunk.document_id == KBDocument.id)
                .where(KBChunk.embedding.isnot(None))
                .limit(200)
            ).all()

            scored: list[tuple[float, object, str, object, str]] = []
            for chunk, title, source_type, source_id in rows:
                emb = chunk.embedding
                if emb is None:
                    continue
                if isinstance(emb, str):
                    try:
                        emb = _json.loads(emb)
                    except Exception:
                        continue
                score = self._cosine_similarity(query_vec, emb)
                scored.append((score, chunk, title or "", source_type, source_id or ""))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            for score, chunk, title, source_type, source_id in scored[:limit]:
                st = source_type.value if hasattr(source_type, "value") else str(source_type)
                results.append(RetrievalResult(
                    chunk_text=chunk.text or "",
                    source_type=st,
                    source_ref=source_id,
                    title=title,
                    score=score,
                    metadata=chunk.metadata_json or {},
                ))
            return results
        except Exception as exc:
            logger.warning("Legacy vector search failed: %s", exc)
            return []

    def _legacy_fulltext_search(self, query: str, limit: int = 20) -> list[RetrievalResult]:
        """Fan-out fulltext search to kb_chunks during migration transition."""
        try:
            from sqlalchemy import select as sa_select
            from app.models.entities import KBChunk, KBDocument

            like_term = f"%{query}%"
            rows = self.db.execute(
                sa_select(KBChunk, KBDocument.title, KBDocument.source_type, KBDocument.source_id)
                .join(KBDocument, KBChunk.document_id == KBDocument.id)
                .where(KBChunk.text.ilike(like_term))
                .limit(limit)
            ).all()

            results = []
            for chunk, title, source_type, source_id in rows:
                st = source_type.value if hasattr(source_type, "value") else str(source_type)
                results.append(RetrievalResult(
                    chunk_text=chunk.text or "",
                    source_type=st,
                    source_ref=source_id or "",
                    title=title or "",
                    score=0.5,
                    metadata=chunk.metadata_json or {},
                ))
            return results
        except Exception as exc:
            logger.warning("Legacy fulltext search failed: %s", exc)
            return []

    @staticmethod
    def _reciprocal_rank_fusion(
        vector_results: list[RetrievalResult],
        fulltext_results: list[RetrievalResult],
        k: int = 60,
    ) -> list[RetrievalResult]:
        scores: dict[str, float] = {}
        result_map: dict[str, RetrievalResult] = {}

        for rank, result in enumerate(vector_results):
            key = f"{result.source_ref}|{result.chunk_text[:80]}"
            rrf_score = 1.0 / (k + rank + 1)
            scores[key] = scores.get(key, 0.0) + rrf_score
            if key not in result_map:
                result_map[key] = result

        for rank, result in enumerate(fulltext_results):
            key = f"{result.source_ref}|{result.chunk_text[:80]}"
            rrf_score = 1.0 / (k + rank + 1)
            scores[key] = scores.get(key, 0.0) + rrf_score
            if key not in result_map:
                result_map[key] = result

        sorted_keys = sorted(scores.keys(), key=lambda k_: scores[k_], reverse=True)

        fused: list[RetrievalResult] = []
        for key in sorted_keys:
            original = result_map[key]
            fused.append(
                RetrievalResult(
                    chunk_text=original.chunk_text,
                    source_type=original.source_type,
                    source_ref=original.source_ref,
                    title=original.title,
                    score=round(scores[key], 6),
                    metadata=original.metadata,
                )
            )
        return fused

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        import math
        if not a or not b:
            return 0.0
        length = min(len(a), len(b))
        dot = sum(x * y for x, y in zip(a[:length], b[:length]))
        norm_a = math.sqrt(sum(x * x for x in a[:length])) or 1.0
        norm_b = math.sqrt(sum(y * y for y in b[:length])) or 1.0
        return dot / (norm_a * norm_b)
