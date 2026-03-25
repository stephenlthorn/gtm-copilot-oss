from __future__ import annotations

import json
import logging
import threading
from typing import Any

from app.core.settings import Settings, get_settings
from app.db.session import SessionLocal
from app.services.mcp.base import MCPRegistry, MCPServer
from app.services.mcp.tidb_mcp import create_tidb_mcp_server
from app.services.mcp.salesforce_mcp import create_salesforce_mcp_server
from app.services.mcp.slack_mcp import create_slack_mcp_server
from app.services.mcp.drive_mcp import create_drive_mcp_server
from app.services.mcp.feishu_mcp import create_feishu_mcp_server
from app.services.mcp.gmail_mcp import create_gmail_mcp_server
from app.services.mcp.calendar_mcp import create_calendar_mcp_server
from app.services.mcp.zoominfo_mcp import create_zoominfo_mcp_server
from app.services.mcp.linkedin_mcp import create_linkedin_mcp_server
from app.services.mcp.github_mcp import create_github_mcp_server
from app.services.mcp.crunchbase_mcp import create_crunchbase_mcp_server

logger = logging.getLogger(__name__)


class MCPRouter:
    """Integrates MCP servers with the chat service.

    Responsible for building the registry of enabled MCP servers,
    providing tool definitions for the LLM, and executing tool calls.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._registry = MCPRegistry()
        self._register_default_servers()

    def _register_default_servers(self) -> None:
        """Register all MCP servers that have their dependencies configured."""
        self._registry.register(create_tidb_mcp_server(SessionLocal))

        slack_server = create_slack_mcp_server(self._settings)
        if not self._settings.slack_bot_token:
            slack_server = MCPServer(
                name=slack_server.name,
                description=slack_server.description,
                tools=slack_server.tools,
                enabled=False,
            )
        self._registry.register(slack_server)

        if self._settings.feishu_app_id and self._settings.feishu_app_secret:
            self._registry.register(create_feishu_mcp_server(self._settings))

    def register_user_servers(
        self,
        *,
        salesforce_instance_url: str | None = None,
        salesforce_access_token: str | None = None,
        google_access_token: str | None = None,
        linkedin_access_token: str | None = None,
        zoominfo_api_key: str | None = None,
        firecrawl_api_key: str | None = None,  # deprecated — kept for API compat
        github_access_token: str | None = None,
        crunchbase_api_key: str | None = None,
    ) -> None:
        """Register per-user MCP servers that require user-specific credentials."""
        if salesforce_instance_url and salesforce_access_token:
            self._registry.register(
                create_salesforce_mcp_server(salesforce_instance_url, salesforce_access_token)
            )

        if google_access_token:
            self._registry.register(create_drive_mcp_server(google_access_token))
            self._registry.register(create_gmail_mcp_server(google_access_token))
            self._registry.register(create_calendar_mcp_server(google_access_token))

        if zoominfo_api_key:
            self._registry.register(create_zoominfo_mcp_server(zoominfo_api_key))

        if linkedin_access_token:
            self._registry.register(create_linkedin_mcp_server(linkedin_access_token))

        if github_access_token:
            self._registry.register(create_github_mcp_server(github_access_token))

        if crunchbase_api_key:
            self._registry.register(create_crunchbase_mcp_server(crunchbase_api_key))

    @property
    def registry(self) -> MCPRegistry:
        return self._registry

    def get_tools_for_user(self, user_id: int) -> list[dict[str, Any]]:
        """Get all enabled tool definitions formatted for OpenAI function calling."""
        return self._registry.get_enabled_tools()

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: int,
    ) -> dict[str, Any]:
        """Execute a tool call by dispatching to the appropriate handler."""
        handler = self._registry.get_handler(tool_name)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            result = await handler(**arguments)
            if isinstance(result, dict):
                return result
            return {"result": result}
        except TypeError as exc:
            logger.exception("Tool argument mismatch for %s", tool_name)
            return {"error": f"Invalid arguments for {tool_name}: {exc}"}
        except Exception as exc:
            logger.exception("Tool execution error for %s", tool_name)
            return {"error": f"Tool execution failed: {exc}"}


_router_instance: MCPRouter | None = None
_router_lock = threading.Lock()


def get_mcp_router() -> MCPRouter:
    """Return the singleton MCPRouter instance."""
    global _router_instance
    if _router_instance is None:
        with _router_lock:
            if _router_instance is None:
                _router_instance = MCPRouter()
    return _router_instance
