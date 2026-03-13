from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.entities import (
    Account,
    CallArtifact,
    ChorusCall,
    Contact,
    Deal,
    DealStatus,
    ResearchReport,
)
from app.services.mcp.base import MCPServer, MCPTool

logger = logging.getLogger(__name__)


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy model instance to a plain dict."""
    result: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.key, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[column.key] = value
    return result


class TiDBMCPHandlers:
    """Handlers that query the local TiDB/PostgreSQL database."""

    def __init__(self, db_factory: Any) -> None:
        self._db_factory = db_factory

    def _get_db(self) -> Session:
        return self._db_factory()

    async def query_accounts(self, search_term: str) -> dict[str, Any]:
        db = self._get_db()
        try:
            term = f"%{search_term}%"
            stmt = (
                select(Account)
                .where(
                    or_(
                        Account.name.ilike(term),
                        Account.industry.ilike(term),
                        Account.website.ilike(term),
                    )
                )
                .limit(20)
            )
            rows = db.execute(stmt).scalars().all()
            return {
                "accounts": [_row_to_dict(r) for r in rows],
                "count": len(rows),
            }
        except Exception as exc:
            logger.exception("TiDB query_accounts error")
            return {"error": str(exc), "accounts": []}
        finally:
            db.close()

    async def get_account_details(self, account_id: int) -> dict[str, Any]:
        db = self._get_db()
        try:
            account = db.get(Account, account_id)
            if not account:
                return {"error": f"Account {account_id} not found"}

            deals_stmt = select(Deal).where(Deal.account_id == account_id).limit(50)
            deals = db.execute(deals_stmt).scalars().all()

            contacts_stmt = select(Contact).where(Contact.account_id == account_id).limit(50)
            contacts = db.execute(contacts_stmt).scalars().all()

            return {
                "account": _row_to_dict(account),
                "deals": [_row_to_dict(d) for d in deals],
                "contacts": [_row_to_dict(c) for c in contacts],
            }
        except Exception as exc:
            logger.exception("TiDB get_account_details error")
            return {"error": str(exc)}
        finally:
            db.close()

    async def query_deals(
        self,
        account_id: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        db = self._get_db()
        try:
            stmt = select(Deal)
            if account_id is not None:
                stmt = stmt.where(Deal.account_id == account_id)
            if status is not None:
                try:
                    deal_status = DealStatus(status)
                    stmt = stmt.where(Deal.status == deal_status)
                except ValueError:
                    pass
            stmt = stmt.order_by(Deal.updated_at.desc()).limit(50)
            rows = db.execute(stmt).scalars().all()
            return {
                "deals": [_row_to_dict(r) for r in rows],
                "count": len(rows),
            }
        except Exception as exc:
            logger.exception("TiDB query_deals error")
            return {"error": str(exc), "deals": []}
        finally:
            db.close()

    async def query_research_reports(
        self,
        account_id: int | None = None,
        report_type: str | None = None,
    ) -> dict[str, Any]:
        db = self._get_db()
        try:
            stmt = select(ResearchReport)
            if account_id is not None:
                stmt = stmt.where(ResearchReport.account_id == account_id)
            if report_type is not None:
                stmt = stmt.where(ResearchReport.report_type == report_type)
            stmt = stmt.order_by(ResearchReport.created_at.desc()).limit(20)
            rows = db.execute(stmt).scalars().all()
            return {
                "reports": [_row_to_dict(r) for r in rows],
                "count": len(rows),
            }
        except Exception as exc:
            logger.exception("TiDB query_research_reports error")
            return {"error": str(exc), "reports": []}
        finally:
            db.close()

    async def query_call_history(
        self,
        account_name: str | None = None,
        rep_email: str | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        db = self._get_db()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            stmt = select(ChorusCall).where(ChorusCall.date >= cutoff.date())

            if account_name:
                stmt = stmt.where(ChorusCall.account.ilike(f"%{account_name}%"))
            if rep_email:
                stmt = stmt.where(ChorusCall.rep_email == rep_email)

            stmt = stmt.order_by(ChorusCall.date.desc()).limit(50)
            calls = db.execute(stmt).scalars().all()

            results: list[dict[str, Any]] = []
            for call in calls:
                call_dict = _row_to_dict(call)
                artifact_stmt = (
                    select(CallArtifact)
                    .where(CallArtifact.chorus_call_id == call.chorus_call_id)
                    .limit(1)
                )
                artifact = db.execute(artifact_stmt).scalars().first()
                if artifact:
                    call_dict["artifact"] = _row_to_dict(artifact)
                results.append(call_dict)

            return {
                "calls": results,
                "count": len(results),
            }
        except Exception as exc:
            logger.exception("TiDB query_call_history error")
            return {"error": str(exc), "calls": []}
        finally:
            db.close()


def create_tidb_mcp_server(db_factory: Any) -> MCPServer:
    """Create and return the TiDB MCP server with all tools registered."""
    handlers = TiDBMCPHandlers(db_factory)

    tools = [
        MCPTool(
            name="query_accounts",
            description="Search for accounts by name, industry, or website.",
            parameters={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Search term to match against account name, industry, or website.",
                    },
                },
                "required": ["search_term"],
            },
            handler=handlers.query_accounts,
        ),
        MCPTool(
            name="get_account_details",
            description="Get full account details including deals and contacts.",
            parameters={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "The account ID to look up.",
                    },
                },
                "required": ["account_id"],
            },
            handler=handlers.get_account_details,
        ),
        MCPTool(
            name="query_deals",
            description="Search deals, optionally filtered by account or status (open/won/lost).",
            parameters={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "Optional account ID to filter deals by.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "won", "lost"],
                        "description": "Optional deal status filter.",
                    },
                },
            },
            handler=handlers.query_deals,
        ),
        MCPTool(
            name="query_research_reports",
            description="Search research reports, optionally filtered by account or report type (pre_call/post_call).",
            parameters={
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "integer",
                        "description": "Optional account ID to filter reports by.",
                    },
                    "report_type": {
                        "type": "string",
                        "enum": ["pre_call", "post_call"],
                        "description": "Optional report type filter.",
                    },
                },
            },
            handler=handlers.query_research_reports,
        ),
        MCPTool(
            name="query_call_history",
            description="Search call history with optional filters for account name, rep email, and time range.",
            parameters={
                "type": "object",
                "properties": {
                    "account_name": {
                        "type": "string",
                        "description": "Optional account name to filter calls.",
                    },
                    "rep_email": {
                        "type": "string",
                        "description": "Optional rep email to filter calls.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back (default: 30).",
                        "default": 30,
                    },
                },
            },
            handler=handlers.query_call_history,
        ),
    ]

    return MCPServer(
        name="tidb",
        description="Query the internal CRM database for accounts, deals, reports, and call history.",
        tools=tools,
    )
