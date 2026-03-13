from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.models.entities import (
    AIRefinement,
    Conversation,
    Message,
    MessageRole,
    RefinementScope,
    User,
)
from app.services.llm_provider.base import LLMResponse
from app.services.llm_provider.openai_provider import OpenAIProvider
from app.services.mcp.router import MCPRouter, get_mcp_router

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 5
_HISTORY_LIMIT = 20

_SYSTEM_PROMPT = """You are GTM Copilot, an AI sales assistant. You help sales representatives,
sales engineers, and marketing professionals with account research, deal preparation,
competitive intelligence, and meeting preparation.

You have access to tools that can query internal databases, CRM systems, documents,
email, calendar, and external data sources. Use these tools proactively when they
would help answer the user's question.

When citing data from tools, be specific about the source. When you don't have
enough information, say so clearly rather than speculating.

Keep responses focused, actionable, and formatted for readability."""


class ChatService:
    """Service layer for the conversational chat interface with MCP tool integration."""

    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        openai_api_key: str | None = None,
        mcp_router: MCPRouter | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        api_key = openai_api_key or self._settings.openai_api_key or ""
        self._llm = OpenAIProvider(
            api_key=api_key,
            default_model=self._settings.openai_model,
            base_url=self._settings.openai_base_url,
        )
        self._mcp_router = mcp_router or get_mcp_router()

    def create_conversation(
        self,
        user_id: int,
        org_id: int,
        *,
        title: str | None = None,
        account_id: int | None = None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            org_id=org_id,
            title=title or "New Conversation",
            account_id=account_id,
        )
        self._db.add(conversation)
        self._db.commit()
        self._db.refresh(conversation)
        return conversation

    def get_conversations(self, user_id: int) -> list[dict[str, Any]]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(50)
        )
        rows = self._db.execute(stmt).scalars().all()
        return [
            {
                "id": c.id,
                "title": c.title,
                "account_id": c.account_id,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in rows
        ]

    def get_messages(self, conversation_id: int) -> list[dict[str, Any]]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        rows = self._db.execute(stmt).scalars().all()
        return [
            {
                "id": m.id,
                "role": m.role.value if isinstance(m.role, MessageRole) else m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "tool_results": m.tool_results,
                "tokens_used": m.tokens_used,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ]

    async def send_message(
        self,
        conversation_id: int,
        user_message: str,
        user_id: int,
        org_id: int,
    ) -> AsyncIterator[str]:
        """Send a message and stream the response. Handles tool calls in a loop."""
        conversation = self._db.get(Conversation, conversation_id)
        if not conversation:
            yield json.dumps({"error": "Conversation not found"})
            return

        self._store_message(
            conversation_id=conversation_id,
            role=MessageRole.user,
            content=user_message,
        )

        history = self._get_history(conversation_id)
        refinements = self._get_user_refinements(user_id)
        tools = self._mcp_router.get_tools_for_user(user_id)

        messages = self._build_messages(
            history=history,
            refinements=refinements,
            user_message=user_message,
        )

        tool_round = 0
        while tool_round < _MAX_TOOL_ROUNDS:
            response = await self._llm.chat(
                messages=messages,
                tools=tools if tools else None,
            )

            if not response.tool_calls:
                final_content = response.content or ""
                self._store_message(
                    conversation_id=conversation_id,
                    role=MessageRole.assistant,
                    content=final_content,
                    tokens_used=response.tokens_used,
                )
                conversation.updated_at = datetime.utcnow()
                self._db.commit()
                yield json.dumps({"content": final_content, "done": True})
                return

            messages.append({
                "role": "assistant",
                "content": response.content or None,
                "tool_calls": response.tool_calls,
            })

            tool_results_for_db: list[dict[str, Any]] = []
            for tc in response.tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    arguments = {}

                yield json.dumps({
                    "tool_call": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                })

                result = await self._mcp_router.execute_tool(
                    tool_name=tool_name,
                    arguments=arguments,
                    user_id=user_id,
                )

                result_str = json.dumps(result, default=str)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_str,
                })

                tool_results_for_db.append({
                    "tool_call_id": tc["id"],
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                })

            self._store_message(
                conversation_id=conversation_id,
                role=MessageRole.tool,
                content="",
                tool_calls=response.tool_calls,
                tool_results=tool_results_for_db,
                tokens_used=response.tokens_used,
            )

            tool_round += 1

        final_response = await self._llm.chat(messages=messages)
        final_content = final_response.content or "I was unable to complete the request within the tool call limit."
        self._store_message(
            conversation_id=conversation_id,
            role=MessageRole.assistant,
            content=final_content,
            tokens_used=final_response.tokens_used,
        )
        conversation.updated_at = datetime.utcnow()
        self._db.commit()
        yield json.dumps({"content": final_content, "done": True})

    def _get_history(self, conversation_id: int) -> list[dict[str, Any]]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(_HISTORY_LIMIT)
        )
        rows = list(reversed(self._db.execute(stmt).scalars().all()))
        history: list[dict[str, Any]] = []
        for m in rows:
            role = m.role.value if isinstance(m.role, MessageRole) else m.role
            if role == "tool" and m.tool_calls:
                history.append({
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": m.tool_calls,
                })
                if m.tool_results:
                    for tr in m.tool_results:
                        history.append({
                            "role": "tool",
                            "tool_call_id": tr.get("tool_call_id", ""),
                            "content": json.dumps(tr.get("result", {}), default=str),
                        })
            else:
                entry: dict[str, Any] = {"role": role, "content": m.content or ""}
                history.append(entry)
        return history

    def _get_user_refinements(self, user_id: int) -> list[str]:
        stmt = (
            select(AIRefinement)
            .where(
                AIRefinement.user_id == user_id,
                AIRefinement.active == True,
            )
            .order_by(AIRefinement.created_at.desc())
            .limit(10)
        )
        rows = self._db.execute(stmt).scalars().all()
        return [r.feedback_text for r in rows if r.feedback_text]

    def _build_messages(
        self,
        *,
        history: list[dict[str, Any]],
        refinements: list[str],
        user_message: str,
    ) -> list[dict[str, Any]]:
        system_content = _SYSTEM_PROMPT
        if refinements:
            refinement_text = "\n".join(f"- {r}" for r in refinements)
            system_content += (
                f"\n\nUser preferences and refinements:\n{refinement_text}"
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
        ]

        for h in history[:-1]:
            messages.append(h)

        return messages

    def _store_message(
        self,
        *,
        conversation_id: int,
        role: MessageRole,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        tokens_used: int | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
            tokens_used=tokens_used,
        )
        self._db.add(msg)
        self._db.commit()
        self._db.refresh(msg)
        return msg
