from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.services.mcp.admin import MCPAdminService

router = APIRouter()


class MCPServerUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


@router.get("/mcp-servers")
def list_mcp_servers(db: Session = Depends(db_session)) -> list[dict[str, Any]]:
    """List all registered MCP servers with their status and configuration."""
    service = MCPAdminService(db)
    return service.list_servers()


@router.put("/mcp-servers/{name}")
def update_mcp_server(
    name: str,
    body: MCPServerUpdate,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """Update an MCP server's enabled state and/or configuration."""
    service = MCPAdminService(db)
    result = service.update_server(
        name,
        enabled=body.enabled,
        config=body.config,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
