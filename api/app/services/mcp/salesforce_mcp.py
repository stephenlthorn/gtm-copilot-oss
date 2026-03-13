from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from app.services.crm.salesforce import SalesforceConnector
from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)

_SF_API_VERSION = "v59.0"


class SalesforceMCPHandlers:
    """Handlers that query Salesforce via the REST API."""

    def __init__(self, instance_url: str, access_token: str) -> None:
        self._instance_url = instance_url
        self._access_token = access_token

    def _connector(self) -> SalesforceConnector:
        return SalesforceConnector(
            instance_url=self._instance_url,
            access_token=self._access_token,
        )

    async def sf_get_pipeline(self, owner: str | None = None) -> dict[str, Any]:
        try:
            connector = self._connector()
            query = (
                "SELECT Id,Name,StageName,Amount,CloseDate,Owner.Name,AccountId,Account.Name "
                "FROM Opportunity WHERE IsClosed=false"
            )
            if owner:
                query += f" AND Owner.Name LIKE '%{owner}%'"
            query += " ORDER BY CloseDate ASC LIMIT 100"

            resp = await connector.client.get(
                f"/services/data/{_SF_API_VERSION}/query",
                params={"q": query},
            )
            resp.raise_for_status()
            records = resp.json().get("records", [])
            return {
                "pipeline": [
                    {
                        "id": r.get("Id"),
                        "name": r.get("Name"),
                        "stage": r.get("StageName"),
                        "amount": r.get("Amount"),
                        "close_date": r.get("CloseDate"),
                        "owner": (r.get("Owner") or {}).get("Name"),
                        "account_id": r.get("AccountId"),
                        "account_name": (r.get("Account") or {}).get("Name"),
                    }
                    for r in records
                ],
                "count": len(records),
            }
        except Exception as exc:
            logger.exception("Salesforce sf_get_pipeline error")
            return {"error": str(exc), "pipeline": []}

    async def sf_get_account(self, account_id: str) -> dict[str, Any]:
        try:
            connector = self._connector()
            account = await connector.get_account(account_id)
            return {"account": asdict(account)}
        except Exception as exc:
            logger.exception("Salesforce sf_get_account error")
            return {"error": str(exc)}

    async def sf_get_deals(self, account_id: str) -> dict[str, Any]:
        try:
            connector = self._connector()
            deals = await connector.get_deals(account_id)
            return {
                "deals": [asdict(d) for d in deals],
                "count": len(deals),
            }
        except Exception as exc:
            logger.exception("Salesforce sf_get_deals error")
            return {"error": str(exc), "deals": []}

    async def sf_get_contacts(self, account_id: str) -> dict[str, Any]:
        try:
            connector = self._connector()
            contacts = await connector.get_contacts(account_id)
            return {
                "contacts": [asdict(c) for c in contacts],
                "count": len(contacts),
            }
        except Exception as exc:
            logger.exception("Salesforce sf_get_contacts error")
            return {"error": str(exc), "contacts": []}

    async def sf_search(self, query: str) -> dict[str, Any]:
        try:
            connector = self._connector()
            resp = await connector.client.get(
                f"/services/data/{_SF_API_VERSION}/query",
                params={"q": query},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "records": data.get("records", []),
                "totalSize": data.get("totalSize", 0),
                "done": data.get("done", True),
            }
        except Exception as exc:
            logger.exception("Salesforce sf_search error")
            return {"error": str(exc), "records": []}


def create_salesforce_mcp_server(
    instance_url: str,
    access_token: str,
) -> MCPServer:
    """Create and return the Salesforce MCP server."""
    handlers = SalesforceMCPHandlers(instance_url, access_token)

    tools = [
        MCPTool(
            name="sf_get_pipeline",
            description="Get the live open pipeline from Salesforce. Optionally filter by owner name.",
            parameters={
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Optional owner name to filter pipeline.",
                    },
                },
            },
            handler=handlers.sf_get_pipeline,
        ),
        MCPTool(
            name="sf_get_account",
            description="Get a live Salesforce account by ID.",
            parameters={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The Salesforce Account ID.",
                    },
                },
                "required": ["account_id"],
            },
            handler=handlers.sf_get_account,
        ),
        MCPTool(
            name="sf_get_deals",
            description="Get live deals/opportunities for a Salesforce account.",
            parameters={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The Salesforce Account ID.",
                    },
                },
                "required": ["account_id"],
            },
            handler=handlers.sf_get_deals,
        ),
        MCPTool(
            name="sf_get_contacts",
            description="Get live contacts for a Salesforce account.",
            parameters={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The Salesforce Account ID.",
                    },
                },
                "required": ["account_id"],
            },
            handler=handlers.sf_get_contacts,
        ),
        MCPTool(
            name="sf_search",
            description="Execute a SOQL query against Salesforce.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SOQL query string.",
                    },
                },
                "required": ["query"],
            },
            handler=handlers.sf_search,
        ),
    ]

    return MCPServer(
        name="salesforce",
        description="Access live Salesforce CRM data: pipeline, accounts, deals, contacts, and SOQL queries.",
        tools=tools,
    )
