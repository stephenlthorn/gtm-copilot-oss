from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"


class GitHubMCPHandlers:
    """Handlers for GitHub code and issue search operations."""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def gh_search_code(
        self,
        query: str,
        repo: str | None = None,
    ) -> dict[str, Any]:
        try:
            search_query = query
            if repo:
                search_query = f"repo:{repo} {query}"

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_GITHUB_API}/search/code",
                    params={"q": search_query, "per_page": 20},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                return {
                    "results": [
                        {
                            "name": item.get("name", ""),
                            "path": item.get("path", ""),
                            "repository": item.get("repository", {}).get("full_name", ""),
                            "html_url": item.get("html_url", ""),
                            "score": item.get("score", 0),
                        }
                        for item in items
                    ],
                    "total_count": data.get("total_count", 0),
                }
        except Exception as exc:
            logger.exception("GitHub search_code error")
            return {"error": str(exc), "results": []}

    async def gh_get_file(self, repo: str, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_GITHUB_API}/repos/{repo}/contents/{path}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()

                content = ""
                if data.get("encoding") == "base64" and data.get("content"):
                    raw = base64.b64decode(data["content"])
                    content = raw.decode("utf-8", errors="replace")[:10000]

                return {
                    "name": data.get("name", ""),
                    "path": data.get("path", ""),
                    "size": data.get("size", 0),
                    "html_url": data.get("html_url", ""),
                    "content": content,
                }
        except Exception as exc:
            logger.exception("GitHub get_file error")
            return {"error": str(exc)}

    async def gh_search_issues(
        self,
        query: str,
        repo: str | None = None,
    ) -> dict[str, Any]:
        try:
            search_query = query
            if repo:
                search_query = f"repo:{repo} {query}"

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{_GITHUB_API}/search/issues",
                    params={"q": search_query, "per_page": 20},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                return {
                    "issues": [
                        {
                            "number": item.get("number"),
                            "title": item.get("title", ""),
                            "state": item.get("state", ""),
                            "user": (item.get("user") or {}).get("login", ""),
                            "html_url": item.get("html_url", ""),
                            "body": (item.get("body") or "")[:500],
                            "labels": [
                                lbl.get("name", "") for lbl in (item.get("labels") or [])
                            ],
                            "created_at": item.get("created_at", ""),
                        }
                        for item in items
                    ],
                    "total_count": data.get("total_count", 0),
                }
        except Exception as exc:
            logger.exception("GitHub search_issues error")
            return {"error": str(exc), "issues": []}


def create_github_mcp_server(access_token: str = "") -> MCPServer:
    """Create and return the GitHub MCP server."""
    handlers = GitHubMCPHandlers(access_token)

    tools = [
        MCPTool(
            name="gh_search_code",
            description="Search code on GitHub. Optionally scope to a specific repository.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Code search query.",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Optional repository (e.g., 'owner/repo') to search within.",
                    },
                },
                "required": ["query"],
            },
            handler=handlers.gh_search_code,
        ),
        MCPTool(
            name="gh_get_file",
            description="Get the content of a file from a GitHub repository.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository in 'owner/repo' format.",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path within the repository.",
                    },
                },
                "required": ["repo", "path"],
            },
            handler=handlers.gh_get_file,
        ),
        MCPTool(
            name="gh_search_issues",
            description="Search issues and pull requests on GitHub.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Issue search query.",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Optional repository to search within.",
                    },
                },
                "required": ["query"],
            },
            handler=handlers.gh_search_issues,
        ),
    ]

    return MCPServer(
        name="github",
        description="Search code, files, and issues on GitHub.",
        tools=tools,
    )
