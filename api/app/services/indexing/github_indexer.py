from __future__ import annotations

import base64
import logging
import re

import httpx
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.entities import SyncSourceType, SyncStatusEnum
from app.services.indexing.embedder import EmbeddingService
from app.services.indexing.index_manager import IndexManager, SyncResult

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"

_TARGET_REPOS = [
    {"owner": "pingcap", "repo": "tidb"},
    {"owner": "tikv", "repo": "tikv"},
    {"owner": "tikv", "repo": "pd"},
]

_INDEX_PATTERNS = [
    "README.md",
    "docs/",
    "pkg/",
    "components/",
]

_MAX_FILE_SIZE = 500_000


class GitHubIndexer:
    def __init__(self, db: Session, embedding_service: EmbeddingService | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self.embedding_service = embedding_service or EmbeddingService()
        self.index_manager = IndexManager(db, self.embedding_service)

    async def sync(self, org_id: int = 1) -> SyncResult:
        source_type = SyncSourceType.tidb_github

        self.index_manager.update_sync_status(
            source_type=source_type,
            org_id=org_id,
            status=SyncStatusEnum.syncing,
        )

        errors: list[str] = []
        docs_indexed = 0
        chunks_indexed = 0

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for repo_info in _TARGET_REPOS:
                    owner = repo_info["owner"]
                    repo = repo_info["repo"]
                    try:
                        result = await self._index_repo(client, owner, repo, org_id)
                        docs_indexed += result.docs_indexed
                        chunks_indexed += result.chunks_indexed
                        if result.errors:
                            errors.extend(result.errors)
                    except Exception as exc:
                        msg = f"Failed to index {owner}/{repo}: {exc}"
                        logger.error(msg)
                        errors.append(msg)

            self.index_manager.update_sync_status(
                source_type=source_type,
                org_id=org_id,
                status=SyncStatusEnum.idle,
                docs_indexed=docs_indexed,
                chunks_indexed=chunks_indexed,
            )

        except Exception as exc:
            error_msg = f"GitHub sync failed: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)
            self.index_manager.update_sync_status(
                source_type=source_type,
                org_id=org_id,
                status=SyncStatusEnum.error,
                error_message=error_msg,
            )

        return SyncResult(
            docs_indexed=docs_indexed,
            chunks_indexed=chunks_indexed,
            errors=errors if errors else None,
        )

    async def _index_repo(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        org_id: int,
    ) -> SyncResult:
        errors: list[str] = []
        docs_indexed = 0
        chunks_indexed = 0

        headers = self._github_headers()

        tree_url = f"{_GITHUB_API}/repos/{owner}/{repo}/git/trees/main?recursive=1"
        resp = await client.get(tree_url, headers=headers)
        if resp.status_code == 404:
            tree_url = f"{_GITHUB_API}/repos/{owner}/{repo}/git/trees/master?recursive=1"
            resp = await client.get(tree_url, headers=headers)
        resp.raise_for_status()

        tree_data = resp.json()
        tree_items = tree_data.get("tree", [])

        for item in tree_items:
            if item.get("type") != "blob":
                continue

            path = item.get("path", "")
            if not self._should_index(path):
                continue

            size = item.get("size", 0)
            if size > _MAX_FILE_SIZE:
                continue

            try:
                content = await self._fetch_file_content(client, owner, repo, path, headers)
                if not content or not content.strip():
                    continue

                strategy = self._pick_strategy(path)
                source_ref = f"github/{owner}/{repo}/{path}"
                title = f"{owner}/{repo}: {path}"
                metadata = {
                    "owner": owner,
                    "repo": repo,
                    "path": path,
                    "url": f"https://github.com/{owner}/{repo}/blob/main/{path}",
                }

                count = await self.index_manager.index_document(
                    source_type=SyncSourceType.tidb_github,
                    source_ref=source_ref,
                    title=title,
                    content=content,
                    metadata=metadata,
                    org_id=org_id,
                    chunk_strategy=strategy,
                )
                docs_indexed += 1
                chunks_indexed += count
            except Exception as exc:
                msg = f"Failed to index {owner}/{repo}/{path}: {exc}"
                logger.warning(msg)
                errors.append(msg)

        return SyncResult(
            docs_indexed=docs_indexed,
            chunks_indexed=chunks_indexed,
            errors=errors if errors else None,
        )

    async def _fetch_file_content(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        path: str,
        headers: dict,
    ) -> str:
        url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        encoding = data.get("encoding", "")
        raw = data.get("content", "")
        if encoding == "base64" and raw:
            return base64.b64decode(raw).decode("utf-8", errors="ignore")
        return raw

    def _github_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        return headers

    @staticmethod
    def _should_index(path: str) -> bool:
        lower = path.lower()
        if lower == "readme.md" or lower.endswith("/readme.md"):
            return True
        if lower.startswith("docs/") or "/docs/" in lower:
            return True
        if lower.endswith((".md", ".rst", ".adoc")):
            return True
        code_extensions = {".go", ".py", ".rs", ".java", ".c", ".cc", ".cpp", ".h"}
        for ext in code_extensions:
            if lower.endswith(ext):
                if "pkg/" in lower or "components/" in lower or "src/" in lower:
                    return True
        return False

    @staticmethod
    def _pick_strategy(path: str) -> str:
        lower = path.lower()
        if lower.endswith((".md", ".rst", ".adoc")):
            return "section"
        return "paragraph"
