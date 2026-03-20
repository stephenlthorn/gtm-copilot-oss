from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class MCPServer:
    name: str
    description: str
    tools: list[MCPTool] = field(default_factory=list)
    enabled: bool = True


class MCPRegistry:
    """Central registry of all MCP servers and their tools."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServer] = {}

    def register(self, server: MCPServer) -> None:
        self._servers[server.name] = server
        logger.info("Registered MCP server: %s (%d tools)", server.name, len(server.tools))

    def unregister(self, server_name: str) -> None:
        self._servers.pop(server_name, None)

    def get_enabled_tools(self) -> list[dict[str, Any]]:
        """Returns OpenAI function-calling tool definitions for all enabled servers."""
        tools: list[dict[str, Any]] = []
        for server in self._servers.values():
            if not server.enabled:
                continue
            for tool in server.tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": f"{server.name}__{tool.name}",
                        "description": f"[{server.name}] {tool.description}",
                        "parameters": tool.parameters,
                    },
                })
        return tools

    def get_handler(self, tool_name: str) -> Callable[..., Awaitable[Any]] | None:
        """Look up handler by namespaced tool name (server__tool)."""
        parts = tool_name.split("__", 1)
        if len(parts) != 2:
            return None
        server_name, func_name = parts
        server = self._servers.get(server_name)
        if not server:
            return None
        for tool in server.tools:
            if tool.name == func_name:
                return tool.handler
        return None

    def list_servers(self) -> list[dict[str, Any]]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "enabled": s.enabled,
                "tool_count": len(s.tools),
            }
            for s in self._servers.values()
        ]

    def set_enabled(self, server_name: str, enabled: bool) -> bool:
        """Enable or disable a server. Returns True if server was found."""
        server = self._servers.get(server_name)
        if not server:
            return False
        updated = MCPServer(
            name=server.name,
            description=server.description,
            tools=server.tools,
            enabled=enabled,
        )
        self._servers[server_name] = updated
        return True

    def get_server(self, server_name: str) -> MCPServer | None:
        return self._servers.get(server_name)
