from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime

from sqlalchemy import literal, or_, select
from sqlalchemy.orm import Session

from app.models import KBChunk, KBDocument
from app.retrieval.reranker import LLMReranker
from app.retrieval.types import RetrievedChunk
from app.services.embedding import EmbeddingService
from app.services.query_rewrite import QueryRewriter


class HybridRetriever:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedder = EmbeddingService()
        self.rewriter = QueryRewriter()
        self.reranker = LLMReranker()

    @staticmethod
    def _cosine(a: list[float] | None, b: list[float] | None) -> float:
        if a is None or b is None:
            return 0.0
        aa_raw = list(a)
        bb_raw = list(b)
        if not aa_raw or not bb_raw:
            return 0.0
        length = min(len(aa_raw), len(bb_raw))
        if length == 0:
            return 0.0
        aa = aa_raw[:length]
        bb = bb_raw[:length]
        dot = sum(x * y for x, y in zip(aa, bb))
        na = math.sqrt(sum(x * x for x in aa)) or 1.0
        nb = math.sqrt(sum(y * y for y in bb)) or 1.0
        return dot / (na * nb)

    @staticmethod
    def _contains_term(haystack: str, term: str) -> bool:
        pattern = rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])"
        return re.search(pattern, haystack) is not None

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9._-]{1,}", query.lower())
        stop = {
            "what",
            "where",
            "when",
            "which",
            "who",
            "why",
            "how",
            "are",
            "the",
            "for",
            "and",
            "with",
            "from",
            "into",
            "this",
            "that",
            "your",
            "ours",
            "their",
            "about",
            "should",
            "could",
            "would",
            "please",
            "show",
            "tell",
            "give",
        }
        seen: set[str] = set()
        terms: list[str] = []
        for token in tokens:
            if len(token) < 3 or token in stop:
                continue
            if token not in seen:
                terms.append(token)
                seen.add(token)
        return terms

    @staticmethod
    def _dedupe_terms(terms: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for term in terms:
            normalized = term.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            out.append(normalized)
        return out

    @staticmethod
    def _term_coverage(text: str, terms: list[str]) -> float:
        if not terms:
            return 0.0
        lowered = text.lower()
        matched = sum(1 for term in terms if HybridRetriever._contains_term(lowered, term))
        return matched / max(1, len(terms))

    def _expand_query_bundle(self, query: str, mode: str) -> list[str]:
        expanded = self.rewriter.expand(query, mode)
        candidates = [query]
        variants = expanded.get("variants") if isinstance(expanded, dict) else None
        if isinstance(variants, list):
            candidates.extend(v for v in variants if isinstance(v, str))
        hyde = expanded.get("hyde") if isinstance(expanded, dict) else None
        if isinstance(hyde, str):
            candidates.append(hyde)

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            text = candidate.strip()
            if len(text) < 2:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)
        return deduped[:5]

    @staticmethod
    def _keyword_score(text: str, terms: list[str]) -> float:
        if not terms:
            return 0.0
        lowered = text.lower()
        count = Counter(term for term in terms if term and HybridRetriever._contains_term(lowered, term))
        if not count:
            return 0.0
        weighted_hits = 0.0
        for term, term_count in count.items():
            weight = 1.0 + min(len(term), 12) / 20.0
            if len(term) > 5:
                weight *= 1.3  # boost specific/domain terms
            weighted_hits += weight * term_count
        denom = max(1.0, len(terms) * 1.3)
        return min(1.0, weighted_hits / denom)

    @staticmethod
    def _apply_filters(doc: KBDocument, filters: dict, chunk: "KBChunk | None" = None) -> bool:
        from app.models.entities import SourceType
        source_filter = {s.lower() for s in (filters.get("source_type") or [])}
        if source_filter and doc.source_type.value.lower() not in source_filter:
            return False

        viewer_email = str(filters.get("viewer_email") or "").strip().lower()
        if viewer_email and doc.source_type.value == "google_drive":
            tags = doc.tags if isinstance(doc.tags, dict) else {}
            indexed_for = str(tags.get("user_email", "")).strip().lower()
            # Shared Drive/service-account indexed content can legitimately omit user_email.
            if indexed_for and indexed_for != viewer_email:
                return False
        if viewer_email and doc.source_type.value == "memory":
            tags = doc.tags if isinstance(doc.tags, dict) else {}
            indexed_for = str(tags.get("user_email", "")).strip().lower()
            if indexed_for and indexed_for != viewer_email:
                return False

        account_filter = {a.lower() for a in (filters.get("account") or [])}
        if account_filter:
            tags = doc.tags if isinstance(doc.tags, dict) else {}
            account = str(tags.get("account", "")).lower()
            if account not in account_filter:
                return False

        # Chunk-level filters — CHORUS source only
        if chunk is not None and doc.source_type.value == SourceType.CHORUS.value:
            chunk_meta = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}

            rep_email_filter = str(filters.get("rep_email") or "").strip().lower()
            if rep_email_filter:
                chunk_rep = str(chunk_meta.get("rep_email", "")).strip().lower()
                if not chunk_rep or chunk_rep != rep_email_filter:
                    return False

            stage_filter = {s.lower() for s in (filters.get("stage") or [])}
            if stage_filter:
                chunk_stage = str(chunk_meta.get("stage", "")).strip().lower()
                if not chunk_stage or chunk_stage not in stage_filter:
                    return False

            outcome_filter = {o.lower() for o in (filters.get("call_outcome") or [])}
            if outcome_filter:
                chunk_outcome = str(chunk_meta.get("call_outcome", "")).strip().lower()
                if not chunk_outcome or chunk_outcome not in outcome_filter:
                    return False

        return True

    @staticmethod
    def _source_bias(doc: KBDocument) -> float:
        title = (doc.title or "").lower()
        bias = 0.0
        if title.startswith("github/") and ("/docs/" in title or title.endswith(".md")):
            bias += 0.08
        if title.endswith((".md", ".markdown", ".rst", ".adoc")):
            bias += 0.03

        if "/test/" in title or "/tests/" in title or title.endswith("_test.go"):
            bias -= 0.20
        elif title.endswith((".go", ".java", ".kt", ".py", ".js", ".jsx", ".ts", ".tsx", ".c", ".cc", ".cpp", ".h", ".hpp", ".rs", ".proto")):
            bias -= 0.05

        # Changelogs/release notes often match generic terms but are weak primary evidence.
        if "/releases/" in title or "release-" in title:
            bias -= 0.10
        if title.endswith("/toc.md") or title.endswith("toc.md") or title.endswith("_index.md"):
            bias -= 0.24
        if title.endswith("/overview.md") or title.endswith("overview.md") or title.endswith("glossary.md"):
            bias -= 0.12
        return bias

    @staticmethod
    def _domain_term_boost(query_terms: list[str], title: str, text: str) -> float:
        if not query_terms:
            return 0.0
        focused_terms = {
            "tiflash",
            "tikv",
            "htap",
            "replication",
            "lag",
            "aurora",
            "mysql",
            "mpp",
            "ddl",
            "migration",
            "poc",
            "consistency",
            "acid",
            "isolation",
            "distributed",
            "sharding",
            "cluster",
            "raft",
            "placement",
            "operator",
            "dashboard",
            "grafana",
            "prometheus",
        }
        terms = [term for term in query_terms if term in focused_terms]
        if not terms:
            return 0.0
        haystack = f"{title}\n{text[:1400]}".lower()
        matched = sum(1 for term in terms if HybridRetriever._contains_term(haystack, term))
        return min(0.24, matched * 0.07)

    @staticmethod
    def _parse_call_date(message: str) -> str | None:
        """Extract a YYYY-MM-DD date string from patterns like '3/19/2026' or '2026-03-19'."""
        # ISO format: 2026-03-19
        iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", message)
        if iso_match:
            return iso_match.group(1)
        # US format: 3/19/2026
        us_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", message)
        if us_match:
            m, d, y = us_match.group(1), us_match.group(2), us_match.group(3)
            try:
                return datetime(int(y), int(m), int(d)).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return None

    def _get_call_focused_rows(self, account_filter_set: set, query_date: str | None) -> tuple[list[tuple], str | None]:
        """Fetch chorus chunks for matching accounts and return (rows, primary_doc_id).

        Returns all chunks from the primary (date-closest) doc plus the first 3 chunks
        from every other doc. primary_doc_id is the str(doc.id) of the primary doc.
        """
        try:
            acct_stmt = (
                select(KBChunk, KBDocument)
                .join(KBDocument, KBChunk.document_id == KBDocument.id)
                .where(KBDocument.source_type.in_(["chorus"]))
                .order_by(KBDocument.id, KBChunk.chunk_index)
            )
            acct_rows = self.db.execute(acct_stmt).all()

            # Group by document, keeping only rows for matching accounts
            docs: dict[str, list[tuple]] = {}
            doc_objects: dict[str, KBDocument] = {}
            for chunk, doc in acct_rows:
                tags = doc.tags if isinstance(doc.tags, dict) else {}
                if str(tags.get("account", "")).lower() not in account_filter_set:
                    continue
                doc_id = str(doc.id)
                if doc_id not in docs:
                    docs[doc_id] = []
                    doc_objects[doc_id] = doc
                docs[doc_id].append((chunk, doc))

            if not docs:
                return [], None

            # Find primary doc: closest date to query_date, else most recent
            primary_doc_id: str | None = None
            if query_date:
                try:
                    target_dt = datetime.strptime(query_date, "%Y-%m-%d")
                    best_delta: float | None = None
                    for doc_id, doc in doc_objects.items():
                        tags = doc.tags if isinstance(doc.tags, dict) else {}
                        date_str = tags.get("date", "")
                        if not date_str:
                            continue
                        try:
                            doc_dt = datetime.strptime(str(date_str), "%Y-%m-%d")
                            delta = abs((doc_dt - target_dt).total_seconds())
                            if best_delta is None or delta < best_delta:
                                best_delta = delta
                                primary_doc_id = doc_id
                        except ValueError:
                            continue
                except ValueError:
                    pass

            if primary_doc_id is None:
                # Use most recent doc (highest id as proxy, or latest date tag)
                best_dt: datetime | None = None
                for doc_id, doc in doc_objects.items():
                    tags = doc.tags if isinstance(doc.tags, dict) else {}
                    date_str = tags.get("date", "")
                    if date_str:
                        try:
                            doc_dt = datetime.strptime(str(date_str), "%Y-%m-%d")
                            if best_dt is None or doc_dt > best_dt:
                                best_dt = doc_dt
                                primary_doc_id = doc_id
                        except ValueError:
                            continue
                if primary_doc_id is None:
                    # Fall back to largest doc id
                    primary_doc_id = max(doc_objects.keys())

            result_rows: list[tuple] = []
            for doc_id, chunk_rows in docs.items():
                if doc_id == primary_doc_id:
                    result_rows.extend(chunk_rows)
                else:
                    result_rows.extend(chunk_rows[:3])

            return result_rows, primary_doc_id
        except Exception:
            return [], None

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
        filters: dict | None = None,
        mode: str = "oracle",
    ) -> list[RetrievedChunk]:
        filters = filters or {}
        query_bundle = self._expand_query_bundle(query, mode)
        terms = self._dedupe_terms(
            [term for query_text in query_bundle for term in self._query_terms(query_text)]
        )
        semantic_available = bool(getattr(self.embedder, "client", None))
        q_vec = self.embedder.embed(query)
        query_vectors = [q_vec] if (semantic_available and q_vec) else []
        if semantic_available:
            for query_text in query_bundle:
                if query_text.strip().lower() == query.strip().lower():
                    continue
                try:
                    variant_vec = self.embedder.embed(query_text)
                    if variant_vec:
                        query_vectors.append(variant_vec)
                except Exception:
                    continue
        if query_vectors:
            dedup_vectors: list[list[float]] = []
            seen_vecs: set[str] = set()
            for vec in query_vectors:
                key = json.dumps(vec[:48])
                if key in seen_vecs:
                    continue
                seen_vecs.add(key)
                dedup_vectors.append(vec)
            query_vectors = dedup_vectors[:4]
        dialect = (self.db.bind.dialect.name if self.db.bind is not None else "").lower()

        source_filter = {s.lower() for s in (filters.get("source_type") or [])}
        candidate_limit = max(320, top_k * 50)

        base_stmt = select(KBChunk, KBDocument).join(KBDocument, KBChunk.document_id == KBDocument.id)
        if source_filter:
            base_stmt = base_stmt.where(KBDocument.source_type.in_(sorted(source_filter)))

        rows: list[tuple[KBChunk, KBDocument]] = []

        if dialect == "mysql":
            from app.db.tidb_vector import vec_cosine_distance

            if semantic_available and query_vectors:
                vector_limit = max(60, int(candidate_limit / max(1, len(query_vectors))))
                for query_vec in query_vectors:
                    try:
                        q_vec_str = json.dumps(query_vec)
                        vector_rows = self.db.execute(
                            base_stmt.where(KBChunk.embedding.is_not(None))
                            .order_by(vec_cosine_distance(KBChunk.embedding, literal(q_vec_str)))
                            .limit(vector_limit)
                        ).all()
                        rows.extend(vector_rows)
                    except Exception:
                        self.db.rollback()
                        rows.extend(self.db.execute(base_stmt.limit(candidate_limit)).all())
                        break

            if terms:
                keyword_clauses = [KBChunk.text.ilike(f"%{term}%") for term in terms[:12]]
                keyword_rows = self.db.execute(
                    base_stmt.where(or_(*keyword_clauses)).limit(candidate_limit)
                ).all()
                rows.extend(keyword_rows)
        else:
            # SQLite fallback for local unit tests
            rows.extend(self.db.execute(base_stmt.limit(candidate_limit)).all())
            if terms:
                keyword_clauses = [KBChunk.text.ilike(f"%{term}%") for term in terms[:12]]
                keyword_rows = self.db.execute(
                    base_stmt.where(or_(*keyword_clauses)).limit(candidate_limit)
                ).all()
                rows.extend(keyword_rows)

        # If an account filter is set, use smart call-focused retrieval
        call_focused_primary_doc_id: str | None = None
        account_filter_set = {a.lower() for a in (filters.get("account") or [])}
        if account_filter_set:
            call_date = self._parse_call_date(query)
            call_rows, call_focused_primary_doc_id = self._get_call_focused_rows(account_filter_set, call_date)
            rows.extend(call_rows)

        deduped: dict[str, tuple[KBChunk, KBDocument]] = {}
        for chunk, doc in rows:
            deduped[str(chunk.id)] = (chunk, doc)

        scored: list[tuple[float, KBChunk, KBDocument]] = []
        for chunk, doc in deduped.values():
            if not self._apply_filters(doc, filters, chunk):
                continue
            # Force call-focused primary chunks to score near 1.0 in order
            # Note: _apply_filters (with chunk) was already applied above.
            chunk_doc_id = str(doc.id)
            if call_focused_primary_doc_id and chunk_doc_id == call_focused_primary_doc_id:
                chunk_idx = getattr(chunk, 'chunk_index', 0) or 0
                score = 1.0 - (chunk_idx * 0.0001)
                scored.append((score, chunk, doc))
                continue
            if query_vectors:
                vec_score = max((self._cosine(chunk.embedding, vec) + 1) / 2 for vec in query_vectors)
            else:
                vec_score = (self._cosine(chunk.embedding, q_vec) + 1) / 2 if q_vec else 0.5
            kw_score = self._keyword_score(chunk.text, terms)
            title_score = self._keyword_score(doc.title or "", terms)
            coverage = self._term_coverage(f"{doc.title or ''}\n{chunk.text}", terms)
            domain_boost = self._domain_term_boost(terms, doc.title or "", chunk.text)
            if semantic_available:
                score = (
                    (0.46 * vec_score)
                    + (0.24 * kw_score)
                    + (0.12 * title_score)
                    + (0.10 * coverage)
                    + self._source_bias(doc)
                    + domain_boost
                )
                # Penalize weak matches instead of hard-filtering them.
                if kw_score < 0.10 and coverage < 0.08:
                    score *= 0.3
            else:
                score = (
                    (0.70 * kw_score)
                    + (0.18 * title_score)
                    + (0.12 * coverage)
                    + self._source_bias(doc)
                    + domain_boost
                )
                # Penalize weak matches instead of hard-filtering them.
                if kw_score < 0.10 and coverage < 0.08:
                    score *= 0.3
            score = max(0.0, min(1.0, score))
            if score <= 0:
                continue
            scored.append((score, chunk, doc))

        # Apply ChunkQualitySignal nudge for chunks with ≥10 signals
        if scored:
            _chunk_ids = [chunk.id for _, chunk, _ in scored]
            from app.models.feedback import ChunkQualitySignal
            from sqlalchemy import func as _func, case
            quality_rows = self.db.execute(
                select(
                    ChunkQualitySignal.chunk_id,
                    _func.sum(case((ChunkQualitySignal.signal == "cited_positive", 1), else_=0)).label("pos"),
                    _func.sum(case((ChunkQualitySignal.signal == "cited_negative", 1), else_=0)).label("neg"),
                )
                .where(ChunkQualitySignal.chunk_id.in_(_chunk_ids))
                .group_by(ChunkQualitySignal.chunk_id)
            ).all()
            quality_map: dict[str, tuple[int, int]] = {
                str(row.chunk_id): (int(row.pos), int(row.neg)) for row in quality_rows
                if int(row.pos) + int(row.neg) >= 10
            }
            if quality_map:
                new_scored = []
                for score, chunk, doc in scored:
                    cid = str(chunk.id)
                    if cid in quality_map:
                        pos, neg = quality_map[cid]
                        positive_rate = pos / (pos + neg)
                        score = max(0.0, min(1.0, score + 0.05 * (positive_rate - 0.5)))
                    new_scored.append((score, chunk, doc))
                scored = new_scored

        scored.sort(key=lambda item: item[0], reverse=True)
        _min_score = float(os.getenv("RAG_MIN_SCORE", "0.12"))
        # Call-focused primary chunks always score ≥ 0.9999 and are never filtered.
        scored = [(s, c, d) for s, c, d in scored if s >= _min_score]
        # If call-focused primary doc is set, return all scored chunks (no top_k cap)
        # so that all primary call chunks reach the LLM.
        if call_focused_primary_doc_id:
            top = scored
        else:
            top = scored[:top_k]

        # Build RetrievedChunk objects from top 100 candidates for reranking
        rerank_pool_size = min(100, len(scored))
        pre_rerank: list[RetrievedChunk] = []
        for score, chunk, doc in scored[:rerank_pool_size]:
            metadata = dict(chunk.metadata_json or {})
            pre_rerank.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    score=round(float(score), 4),
                    token_count=chunk.token_count,
                    text=chunk.text,
                    metadata=metadata,
                    source_type=doc.source_type.value,
                    source_id=doc.source_id,
                    title=doc.title,
                    url=doc.url,
                    file_id=str((doc.tags or {}).get("drive_file_id") or doc.source_id),
                )
            )

        # ── Step 6: LLM reranker → final top_k ────────────────────────────────
        return self.reranker.rerank(query, pre_rerank, top_k)

    @staticmethod
    def retrieval_payload(hits: list[RetrievedChunk], top_k: int) -> dict:
        return {
            "top_k": top_k,
            "results": [
                {
                    "chunk_id": str(hit.chunk_id),
                    "document_id": str(hit.document_id),
                    "score": hit.score,
                }
                for hit in hits
            ],
        }

    @staticmethod
    def serialize_hits(hits: list[RetrievedChunk]) -> list[dict]:
        return [asdict(hit) for hit in hits]
