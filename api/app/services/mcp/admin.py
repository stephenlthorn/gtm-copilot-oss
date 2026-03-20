from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import SystemConfig
from app.services.mcp.router import get_mcp_router

logger = logging.getLogger(__name__)

_CONFIG_KEY_PREFIX = "mcp_server_"


class MCPAdminService:
    """Administrative service for managing MCP server configurations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_servers(self) -> list[dict[str, Any]]:
        """List all registered MCP servers with their config and status."""
        router = get_mcp_router()
        servers = router.registry.list_servers()

        for server in servers:
            config = self._load_config(server["name"])
            if config is not None:
                server["config"] = config

        return servers

    def update_server(
        self,
        name: str,
        *,
        enabled: bool | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update a server's enabled state and/or configuration."""
        router = get_mcp_router()

        server = router.registry.get_server(name)
        if server is None:
            return {"error": f"Server '{name}' not found"}

        if enabled is not None:
            router.registry.set_enabled(name, enabled)

        if config is not None:
            self._save_config(name, config)

        updated = router.registry.get_server(name)
        result: dict[str, Any] = {
            "name": name,
            "enabled": updated.enabled if updated else False,
            "tool_count": len(updated.tools) if updated else 0,
        }
        saved_config = self._load_config(name)
        if saved_config is not None:
            result["config"] = saved_config
        return result

    def _load_config(self, server_name: str) -> dict[str, Any] | None:
        """Load server config from the system_config table."""
        key = f"{_CONFIG_KEY_PREFIX}{server_name}"
        stmt = select(SystemConfig).where(SystemConfig.config_key == key)
        row = self._db.execute(stmt).scalars().first()
        if row is None:
            return None
        return row.config_value_plain if row.config_value_plain else None

    def _save_config(self, server_name: str, config: dict[str, Any]) -> None:
        """Save server config to the system_config table."""
        key = f"{_CONFIG_KEY_PREFIX}{server_name}"
        stmt = select(SystemConfig).where(SystemConfig.config_key == key)
        row = self._db.execute(stmt).scalars().first()

        if row is None:
            row = SystemConfig(
                config_key=key,
                config_value_plain=config,
                org_id=1,
            )
            self._db.add(row)
        else:
            row.config_value_plain = config

        self._db.commit()
