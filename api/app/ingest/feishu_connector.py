from __future__ import annotations

import logging
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

_TENANT_TOKEN_URL = "/auth/v3/tenant_access_token/internal"
_LIST_FILES_URL = "/drive/v1/files"
_DOC_CONTENT_URL = "/docx/v1/documents/{doc_token}/raw_content"
_LIST_WIKI_SPACES_URL = "/wiki/v2/spaces"
_LIST_WIKI_NODES_URL = "/wiki/v2/spaces/{space_id}/nodes"


class FeishuConnector:
    """Fetch Feishu/Lark docs from one or more root folders (optionally recursive)."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn/open-apis",
        access_token: str | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self._tenant_token: str | None = None
        self._access_token = (access_token or "").strip() or None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _refresh_tenant_token(self) -> None:
        if not self.app_id or not self.app_secret:
            raise RuntimeError("Feishu app_id/app_secret are required for tenant-token mode.")
        url = self.base_url + _TENANT_TOKEN_URL
        resp = httpx.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Feishu auth error: {data}")
        self._tenant_token = data["tenant_access_token"]

    def _headers(self) -> dict[str, str]:
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        if not self._tenant_token:
            self._refresh_tenant_token()
        return {"Authorization": f"Bearer {self._tenant_token}"}

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    @staticmethod
    def _item_token(item: dict[str, Any]) -> str | None:
        for key in ("token", "file_token", "doc_token", "obj_token"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def list_folder_items(self, folder_token: str | None) -> list[dict[str, Any]]:
        """Return all file metadata dicts in the given folder."""
        url = self.base_url + _LIST_FILES_URL
        params: dict[str, Any] = {"page_size": 50}
        if folder_token:
            params["folder_token"] = folder_token

        items: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            request_params = dict(params)
            if page_token:
                request_params["page_token"] = page_token
            resp = httpx.get(url, headers=self._headers(), params=request_params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Feishu list_folder error: {data}")
            payload = data.get("data", {})
            batch = payload.get("files") or payload.get("items") or []
            for item in batch:
                if isinstance(item, dict):
                    items.append(item)
            if not payload.get("has_more"):
                break
            page_token = payload.get("next_page_token")

        return items

    def list_documents(
        self,
        root_tokens: list[str],
        *,
        recursive: bool = True,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Traverse one or more Feishu folders and return docx/doc entries."""
        normalized_roots = []
        seen_roots: set[str] = set()
        for token in root_tokens:
            normalized = (token or "").strip()
            if not normalized or normalized in seen_roots:
                continue
            seen_roots.add(normalized)
            normalized_roots.append(normalized)

        if not normalized_roots:
            normalized_roots = [""]

        docs: list[dict[str, Any]] = []
        seen_docs: set[str] = set()
        seen_folders: set[str] = set()
        queue: list[str] = list(normalized_roots)

        if progress:
            progress(
                {
                    "phase": "listing",
                    "roots": len(normalized_roots),
                    "folders_queued": len(queue),
                    "folders_visited": 0,
                    "files_discovered": 0,
                }
            )

        while queue:
            current_folder = (queue.pop(0) or "").strip()
            if current_folder:
                if current_folder in seen_folders:
                    continue
                seen_folders.add(current_folder)
            items = self.list_folder_items(current_folder or None)

            for item in items:
                item_type = str(item.get("type") or "").strip().lower()
                token = self._item_token(item)
                if not token:
                    continue

                if item_type == "folder":
                    if recursive and token not in seen_folders:
                        queue.append(token)
                    continue

                if item_type not in {"docx", "doc"}:
                    continue

                if token in seen_docs:
                    continue
                seen_docs.add(token)
                docs.append(
                    {
                        **item,
                        "token": token,
                        "_root_token": current_folder,
                    }
                )

            if progress:
                progress(
                    {
                        "phase": "listing",
                        "roots": len(normalized_roots),
                        "folders_queued": len(queue),
                        "folders_visited": len(seen_folders),
                        "files_discovered": len(docs),
                    }
                )

        logger.info(
            "Feishu: found %d docs across %d roots (recursive=%s)",
            len(docs),
            len(normalized_roots),
            recursive,
        )
        return docs

    def list_folder(self, folder_token: str) -> list[dict[str, Any]]:
        """Backward-compatible single-root listing."""
        return self.list_documents([folder_token], recursive=False)

    # ------------------------------------------------------------------
    # Wiki
    # ------------------------------------------------------------------

    def list_wiki_spaces(self) -> list[dict[str, Any]]:
        """Return all wiki spaces the app has access to."""
        url = self.base_url + _LIST_WIKI_SPACES_URL
        spaces: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": 50}
            if page_token:
                params["page_token"] = page_token
            resp = httpx.get(url, headers=self._headers(), params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Feishu list_wiki_spaces error: {data}")
            payload = data.get("data", {})
            spaces.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")

        logger.info("Feishu wiki: found %d spaces", len(spaces))
        return spaces

    def list_wiki_nodes(self, space_id: str, parent_node_token: str | None = None) -> list[dict[str, Any]]:
        """Return direct children of parent_node_token in the given space (paged)."""
        url = self.base_url + _LIST_WIKI_NODES_URL.format(space_id=space_id)
        nodes: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": 50}
            if page_token:
                params["page_token"] = page_token
            if parent_node_token:
                params["parent_node_token"] = parent_node_token
            resp = httpx.get(url, headers=self._headers(), params=params, timeout=20)
            if not resp.is_success:
                logger.warning(
                    "Feishu list_wiki_nodes HTTP %s space=%s parent=%s: %s",
                    resp.status_code, space_id, parent_node_token, resp.text[:500],
                )
                break
            data = resp.json()
            if data.get("code") != 0:
                logger.warning("Feishu list_wiki_nodes error space=%s: %s", space_id, data)
                break
            payload = data.get("data", {})
            nodes.extend(payload.get("items") or [])
            if not payload.get("has_more"):
                break
            page_token = payload.get("page_token")

        return nodes

    def _collect_wiki_docs(self, space_id: str, root_node_token: str, seen_docs: set[str]) -> list[dict[str, Any]]:
        """BFS-collect all doc nodes reachable under root_node_token."""
        docs: list[dict[str, Any]] = []
        queue: list[str] = [root_node_token]
        seen_nodes: set[str] = set()

        while queue:
            parent_token = queue.pop(0)
            if parent_token in seen_nodes:
                continue
            seen_nodes.add(parent_token)

            children = self.list_wiki_nodes(space_id, parent_node_token=parent_token)
            for child in children:
                obj_type = (child.get("obj_type") or "").strip().lower()
                obj_token = (child.get("obj_token") or "").strip()
                node_token = (child.get("node_token") or "").strip()

                if obj_token and obj_token not in seen_docs and obj_type in {"docx", "doc"}:
                    seen_docs.add(obj_token)
                    docs.append({
                        "token": obj_token,
                        "name": child.get("title") or obj_token,
                        "_source": "wiki",
                        "_space_id": space_id,
                    })

                if node_token and node_token not in seen_nodes:
                    queue.append(node_token)

        return docs

    def get_wiki_node(self, node_token: str) -> dict[str, Any]:
        """Get wiki node info by token — returns space_id, obj_token, obj_type, etc."""
        url = self.base_url + "/wiki/v2/spaces/get_node"
        resp = httpx.get(url, headers=self._headers(), params={"token": node_token}, timeout=20)
        if not resp.is_success:
            logger.warning(
                "Feishu get_wiki_node HTTP %s token=%s: %s",
                resp.status_code, node_token, resp.text[:500],
            )
            resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Feishu get_wiki_node error: {data}")
        return data.get("data", {}).get("node", {})

    def list_wiki_documents(self, root_tokens: list[str] | None = None) -> list[dict[str, Any]]:
        """Return all docx/doc items from wiki spaces (flat, deduplicated).

        If root_tokens are provided, resolve each to a space_id via the nodes API
        and list that space's nodes directly — bypasses space enumeration permission.
        Falls back to auto-discovering all accessible spaces when no tokens given.
        """
        docs: list[dict[str, Any]] = []
        seen_docs: set[str] = set()

        if root_tokens:
            for token in root_tokens:
                try:
                    node = self.get_wiki_node(token)
                    space_id = (node.get("space_id") or "").strip()
                    node_token = (node.get("node_token") or token).strip()
                    if not space_id:
                        continue

                    # Include root node itself if it's a doc
                    obj_type = (node.get("obj_type") or "").strip().lower()
                    obj_token = (node.get("obj_token") or "").strip()
                    if obj_type in {"docx", "doc"} and obj_token and obj_token not in seen_docs:
                        seen_docs.add(obj_token)
                        docs.append({
                            "token": obj_token,
                            "name": node.get("title") or obj_token,
                            "_source": "wiki",
                            "_space_id": space_id,
                        })

                    # Recursively collect all docs under this node
                    docs.extend(self._collect_wiki_docs(space_id, node_token, seen_docs))
                except Exception as exc:
                    logger.warning("Feishu wiki: failed to resolve root token %s: %s", token, exc)
            logger.info("Feishu wiki: found %d docs via %d root tokens", len(docs), len(root_tokens))
            return docs

        # Auto-discovery fallback
        spaces = self.list_wiki_spaces()
        for space in spaces:
            space_id = (space.get("space_id") or "").strip()
            if not space_id:
                continue
            nodes = self.list_wiki_nodes(space_id)
            for node in nodes:
                obj_type = (node.get("obj_type") or "").strip().lower()
                obj_token = (node.get("obj_token") or "").strip()
                if obj_type not in {"docx", "doc"} or not obj_token or obj_token in seen_docs:
                    continue
                seen_docs.add(obj_token)
                docs.append({
                    "token": obj_token,
                    "name": node.get("title") or obj_token,
                    "_source": "wiki",
                    "_space_id": space_id,
                })

        logger.info("Feishu wiki: found %d docs across %d spaces", len(docs), len(spaces))
        return docs

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def get_doc_content(self, doc_token: str) -> str:
        """Fetch plain text content of a Feishu document."""
        url = self.base_url + _DOC_CONTENT_URL.format(doc_token=doc_token)
        resp = httpx.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        code = data.get("code")
        if code != 0:
            msg = str(data.get("msg") or "")
            if code == 20043 or "docs:document:readonly" in msg:
                raise RuntimeError(
                    "Feishu permission denied (code 20043). Missing docs:document:readonly. "
                    "Grant docs read permission in Feishu app, publish the app version, "
                    "approve it in tenant admin, then reconnect OAuth and sync again."
                )
            raise RuntimeError(f"Feishu get_doc_content error: {data}")
        return data.get("data", {}).get("content", "")
