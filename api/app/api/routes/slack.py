from __future__ import annotations

import json
import re
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AuditStatus, ChorusCall
from app.services.audit import write_audit_log
from app.services.chat_orchestrator import ChatOrchestrator
from app.services.llm import LLMService
from app.services.slack import SlackService
from app.prompts.templates import TIDB_EXPERT_CONTEXT, TIDB_AI_CONTEXT

router = APIRouter()


# ── Help text shown when user types /gtm help or empty command ───────────────

HELP_TEXT = """*GTM Copilot — Slack Commands*

`/gtm help`
Show this help message.

`/gtm ask <question>`
Ask anything — account research, deal strategy, competitive positioning, TiDB technical questions.
_Example:_ `/gtm ask what is PayNearMe's tech stack and how does TiDB fit?`

`/gtm intel <company name>`
Generate a full Account Intelligence brief — fit score, pain points, buy signals, next steps, opening pitch. Uses call history from the system if available.
_Example:_ `/gtm intel PayNearMe`

`/gtm call <question about a call>`
Analyze call history — risks, next steps, coaching points, MEDDPICC gaps.
_Example:_ `/gtm call what were the main objections from the last Acme call?`

`/gtm precall <company name>`
Quick pre-call research brief — company overview, tech stack hypothesis, pain signals, TiDB value props.
_Example:_ `/gtm precall Stripe`

`/gtm competitor <competitor> for <account>`
Competitive coaching — positioning, proof points, discovery questions, landmines.
_Example:_ `/gtm competitor CockroachDB for Acme`

All commands can also be used by @mentioning the bot in any channel.
"""


# ── Command routing ──────────────────────────────────────────────────────────

def _resolve_mode(command: str, text: str) -> tuple[str, str, str | None]:
    """Returns (mode, message, extra_param).

    Modes: help, oracle, call_assistant, account_intel, precall, competitor
    """
    normalized = (command or "").strip().lower()
    trimmed = (text or "").strip()
    lowered = trimmed.lower()

    if not trimmed or lowered in {"help", "--help", "-h"}:
        return "help", "", None

    if lowered.startswith("help"):
        return "help", "", None

    if lowered.startswith("intel "):
        return "account_intel", trimmed[6:].strip(), None

    if lowered.startswith("precall "):
        return "precall", trimmed[8:].strip(), None

    if lowered.startswith("call "):
        return "call_assistant", trimmed[5:].strip(), None

    if lowered.startswith("competitor "):
        rest = trimmed[11:].strip()
        if " for " in rest.lower():
            parts = re.split(r"\s+for\s+", rest, maxsplit=1, flags=re.IGNORECASE)
            return "competitor", parts[1].strip() if len(parts) > 1 else rest, parts[0].strip()
        return "competitor", rest, None

    if lowered.startswith("ask "):
        return "oracle", trimmed[4:].strip(), None

    if normalized in {"/oracle-call", "/call-assistant"}:
        return "call_assistant", trimmed, None

    return "oracle", trimmed, None


# ── Response formatters ──────────────────────────────────────────────────────

def _format_citations(citations: list[dict], max_items: int = 3) -> list[str]:
    lines: list[str] = []
    for citation in citations[:max_items]:
        title = citation.get("title") or "Untitled source"
        source_id = citation.get("source_id") or "-"
        chunk_id = citation.get("chunk_id") or "-"
        lines.append(f"- {title} (`{source_id}` | `{chunk_id}`)")
    return lines


def _format_oracle_reply(data: dict) -> str:
    answer = (data.get("answer") or "").strip() or "I couldn't generate an answer."
    citations = _format_citations(data.get("citations") or [])
    followups = data.get("follow_up_questions") or []

    parts = [answer]
    if citations:
        parts.append("")
        parts.append("*Sources*")
        parts.extend(citations)
    if followups:
        parts.append("")
        parts.append("*Follow-ups*")
        for idx, item in enumerate(followups[:3], start=1):
            parts.append(f"{idx}. {item}")
    return "\n".join(parts)[:3500]


def _format_call_assistant_reply(data: dict) -> str:
    sections = [
        ("What happened", data.get("what_happened") or []),
        ("Risks", data.get("risks") or []),
        ("Next steps", data.get("next_steps") or []),
        ("Questions to ask", data.get("questions_to_ask_next_call") or []),
    ]
    lines: list[str] = []
    for title, items in sections:
        if not items:
            continue
        lines.append(f"*{title}*")
        for item in items[:4]:
            lines.append(f"- {item}")
        lines.append("")
    citations = _format_citations(data.get("citations") or [])
    if citations:
        lines.append("*Sources*")
        lines.extend(citations)
    text = "\n".join(lines).strip()
    return (text or "No call analysis output available.")[:3500]


def _format_account_intel_reply(profile: dict) -> str:
    """Format account intelligence JSON into readable Slack blocks."""
    lines: list[str] = []
    company = profile.get("company", "Unknown")
    score = profile.get("fit_score", "?")
    health = profile.get("relationship_health", "unknown")
    health_emoji = {"strong": ":large_green_circle:", "neutral": ":large_blue_circle:", "at-risk": ":large_yellow_circle:", "negative": ":red_circle:"}.get(health, ":white_circle:")

    lines.append(f"*{company}* — TiDB Account Intelligence Brief")
    lines.append(f"Fit Score: *{score}/10* | Relationship: {health_emoji} {health}")
    lines.append("")

    if profile.get("overview_1"):
        lines.append(profile["overview_1"])
    if profile.get("overview_2"):
        lines.append("")
        lines.append(f"_{profile['overview_2']}_")
    lines.append("")

    stack = profile.get("stack") or {}
    if stack.get("databases"):
        lines.append(f"*Stack:* {', '.join(stack['databases'])} | Cloud: {', '.join(stack.get('cloud', []))}")
    if stack.get("compatibility"):
        lines.append(f"*Migration:* {stack['compatibility']}")
    lines.append("")

    pain_points = profile.get("pain_points") or []
    if pain_points:
        lines.append("*Pain Points*")
        for p in pain_points[:4]:
            severity = p.get("severity", "").upper()
            lines.append(f"- [{severity}] *{p.get('title', '')}*: {p.get('pain', '')} → _{p.get('solution', '')}_")
        lines.append("")

    buy_signals = profile.get("buy_signals") or []
    if buy_signals:
        lines.append("*Signals & Risks*")
        for s in buy_signals[:5]:
            urgency = s.get("urgency", "")
            emoji = ":rotating_light:" if urgency == "risk" else ":arrow_up:" if urgency == "high" else ":arrow_right:" if urgency == "medium" else ":small_blue_diamond:"
            lines.append(f"- {emoji} *{s.get('title', '')}*: {s.get('text', '')}")
        lines.append("")

    competitors = profile.get("competitors") or []
    if competitors:
        lines.append("*Competitive Landscape*")
        for c in competitors[:3]:
            lines.append(f"- *{c.get('name', '')}* ({c.get('status', '')}) — {c.get('note', '')}")
        lines.append("")

    next_steps = profile.get("next_steps") or []
    if next_steps:
        lines.append("*Next Steps*")
        for step in next_steps[:3]:
            lines.append(f"- {step}")
        lines.append("")

    if profile.get("opening_pitch"):
        lines.append("*Opening Pitch*")
        lines.append(profile["opening_pitch"])

    return "\n".join(lines)[:3800]


def _format_reply(mode: str, data: dict) -> str:
    if mode == "call_assistant":
        return _format_call_assistant_reply(data)
    return _format_oracle_reply(data)


# ── Account Intelligence generator (reuses backend endpoint logic) ───────────

def _generate_account_intel(company: str, user_email: str) -> str:
    """Build an account intelligence brief, pulling call history from the DB."""
    db: Session = SessionLocal()
    try:
        calls = db.execute(
            select(ChorusCall)
            .where(ChorusCall.account.ilike(f"%{company}%"))
            .order_by(ChorusCall.date.desc())
            .limit(10)
        ).scalars().all()

        call_summaries = [
            f"[{c.date}] {c.meeting_summary}"
            for c in calls
            if c.meeting_summary
        ]
        call_count = len(calls)
    finally:
        db.close()

    if call_summaries:
        call_block = (
            f"INTERNAL CALL INTELLIGENCE — {call_count} calls on record, "
            f"{len(call_summaries)} with notes (newest first):\n\n"
            + "\n\n".join(f"Call {i+1}: {s}" for i, s in enumerate(call_summaries))
            + "\n\nAnalyze these calls for relationship sentiment, objections, blockers, "
            "competitor mentions, champion status, and deal velocity. "
            "These signals are HIGHEST PRIORITY — external research fills gaps, not overrides."
        )
    else:
        call_block = "No internal call history — base full analysis on external research."

    prompt = f"""Generate an Account Intelligence brief for "{company}".

{call_block}

Research this company and return ONLY valid JSON (no markdown, no code fences):
{{
  "company": "full name",
  "domain": "website",
  "hq": "City, State/Country",
  "founded": "year",
  "sector": "sector",
  "funding": "Series/Public info",
  "employees": "count",
  "fit_score": 7.0,
  "relationship_health": "strong | neutral | at-risk | negative",
  "overview_1": "2-3 sentences: what they do, their scale, why technically interesting",
  "overview_2": "2-3 sentences: honest deal status based on calls + research",
  "stack": {{
    "databases": ["MySQL", "Redis"],
    "cloud": ["AWS"],
    "compatibility": "migration path to TiDB"
  }},
  "pain_points": [
    {{"title": "name", "pain": "specific pain", "solution": "TiDB capability", "severity": "high|medium"}}
  ],
  "buy_signals": [
    {{"title": "signal", "text": "evidence", "urgency": "high|medium|low|risk"}}
  ],
  "competitors": [
    {{"name": "competitor", "status": "incumbent|evaluating|preferred", "note": "positioning"}}
  ],
  "next_steps": ["action item 1", "action item 2"],
  "opening_pitch": "3-4 sentence personalized opener reflecting actual relationship state"
}}

Fit score: base 4.0. MySQL/Aurora +2.0, Oracle +1.8, PostgreSQL +1.2, high TPS +1.4, AI/ML +1.5, HTAP +1.0. Subtract: security objection -2.5, unhappiness -1.5, not interested -3.0, competitor preferred -2.0. Calls override stack fit.
Always say "TiDB Cloud Starter" (never Serverless)."""

    system = (
        TIDB_EXPERT_CONTEXT
        + "\n\n"
        + TIDB_AI_CONTEXT
        + "\n\nYou are producing a structured account intelligence profile. "
        "Apply your full TiDB technical knowledge. "
        "Return ONLY valid JSON with no markdown, code fences, or explanation."
    )

    llm = LLMService()
    answer = llm._responses_text(system, prompt)
    if not answer:
        last = getattr(llm, "last_error", None)
        return f"Could not generate intel brief for {company}. {last or 'No LLM credentials configured.'}"

    try:
        json_match = re.search(r"\{[\s\S]*\}", answer)
        if json_match:
            profile = json.loads(json_match.group())
            return _format_account_intel_reply(profile)
    except (json.JSONDecodeError, ValueError):
        pass

    return answer[:3500]


# ── Slack form parser ────────────────────────────────────────────────────────

def _parse_slack_form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {k: values[-1] if values else "" for k, values in parsed.items()}


# ── Slash command endpoint ───────────────────────────────────────────────────

@router.post("/command")
async def slack_command(request: Request) -> dict:
    body = await request.body()
    slack = SlackService()
    try:
        slack.verify_signature(request.headers, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    payload = _parse_slack_form(body)
    command = payload.get("command", "")
    mode, message, extra = _resolve_mode(command, payload.get("text", ""))

    if mode == "help" or not message:
        return {"response_type": "ephemeral", "text": HELP_TEXT}

    user_email = await slack.resolve_user_email(payload.get("user_id"), payload.get("user_name"))

    if mode == "account_intel":
        try:
            reply = _generate_account_intel(message, user_email)
            return {"response_type": "in_channel", "text": reply}
        except Exception as exc:
            return {"response_type": "ephemeral", "text": f"Account intel failed: {exc}"}

    if mode == "precall":
        message = f"Produce a concise pre-call research brief for a sales call with {message}. Cover: company overview, tech stack hypothesis, pain signals, TiDB value props, and meeting goal."
        mode = "oracle"

    if mode == "competitor":
        competitor = extra or "unknown"
        message = f"Competitive coaching for {message} — primary competitor: {competitor}. Cover: TiDB positioning vs {competitor}, top objections with responses, proof points, discovery questions."
        mode = "oracle"

    db: Session = SessionLocal()
    orchestrator = ChatOrchestrator(db)
    input_payload = {
        "mode": mode,
        "source": "slack_command",
        "command": command,
        "user_id": payload.get("user_id"),
        "user_name": payload.get("user_name"),
        "channel_id": payload.get("channel_id"),
        "message": message,
    }

    try:
        data, retrieval = orchestrator.run(
            mode=mode,
            user=user_email,
            message=message,
            top_k=8,
            filters={},
            context={},
        )
        write_audit_log(
            db,
            actor=user_email,
            action="chat_slack_command",
            input_payload=input_payload,
            retrieval_payload=retrieval,
            output_payload=data,
            status=AuditStatus.OK,
        )
        return {"response_type": "in_channel", "text": _format_reply(mode, data)}
    except Exception as exc:
        db.rollback()
        write_audit_log(
            db,
            actor=user_email,
            action="chat_slack_command",
            input_payload=input_payload,
            retrieval_payload={},
            output_payload={},
            status=AuditStatus.ERROR,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GTM Copilot Slack command failed.",
        ) from exc
    finally:
        db.close()


# ── Event subscription (bot @mentions) ───────────────────────────────────────

@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks) -> dict:
    body = await request.body()

    # Handle URL verification challenge BEFORE signature check —
    # Slack sends this during initial setup and expects an immediate response.
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body.") from exc

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    # For all other events, verify signature
    slack = SlackService()
    try:
        slack.verify_signature(request.headers, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    if payload.get("type") != "event_callback":
        return {"ok": True}

    event = payload.get("event") or {}
    if event.get("type") != "app_mention":
        return {"ok": True}
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return {"ok": True}

    channel = str(event.get("channel") or "").strip()
    if not channel:
        return {"ok": True}

    mention_text = re.sub(r"<@[^>]+>", "", str(event.get("text") or "")).strip()
    mode, message, extra = _resolve_mode("", mention_text)

    if mode == "help" or not message:
        background_tasks.add_task(
            _post_help,
            channel,
            str(event.get("thread_ts") or event.get("ts") or ""),
        )
        return {"ok": True}

    background_tasks.add_task(
        _handle_slack_event,
        {
            "mode": mode,
            "event_id": payload.get("event_id"),
            "channel": channel,
            "thread_ts": str(event.get("thread_ts") or event.get("ts") or ""),
            "message": message,
            "user_id": str(event.get("user") or ""),
            "extra": extra,
        },
    )
    return {"ok": True}


async def _post_help(channel: str, thread_ts: str) -> None:
    slack = SlackService()
    await slack.post_message(channel, HELP_TEXT, thread_ts=thread_ts)


async def _handle_slack_event(event_input: dict) -> None:
    slack = SlackService()
    user_email = await slack.resolve_user_email(event_input.get("user_id"), None)
    channel = event_input.get("channel") or ""
    thread_ts = event_input.get("thread_ts")
    mode = event_input.get("mode") or "oracle"
    message = event_input.get("message") or ""
    extra = event_input.get("extra")

    if mode == "account_intel":
        try:
            reply = _generate_account_intel(message, user_email)
        except Exception as exc:
            reply = f"Account intel failed: {exc}"
        await slack.post_message(channel, reply, thread_ts=thread_ts)
        return

    if mode == "precall":
        message = f"Produce a concise pre-call research brief for a sales call with {message}. Cover: company overview, tech stack hypothesis, pain signals, TiDB value props, and meeting goal."
        mode = "oracle"

    if mode == "competitor":
        competitor = extra or "unknown"
        message = f"Competitive coaching for {message} — primary competitor: {competitor}. Cover: TiDB positioning vs {competitor}, top objections with responses, proof points, discovery questions."
        mode = "oracle"

    db: Session = SessionLocal()
    orchestrator = ChatOrchestrator(db)
    input_payload = {
        "mode": mode,
        "source": "slack_event",
        "event_id": event_input.get("event_id"),
        "channel": channel,
        "thread_ts": thread_ts,
        "message": message,
    }

    try:
        data, retrieval = orchestrator.run(
            mode=mode,
            user=user_email,
            message=message,
            top_k=8,
            filters={},
            context={},
        )
        await slack.post_message(
            channel=channel,
            text=_format_reply(mode, data),
            thread_ts=thread_ts,
        )
        write_audit_log(
            db,
            actor=user_email,
            action="chat_slack_event",
            input_payload=input_payload,
            retrieval_payload=retrieval,
            output_payload=data,
            status=AuditStatus.OK,
        )
    except Exception as exc:
        db.rollback()
        write_audit_log(
            db,
            actor=user_email,
            action="chat_slack_event",
            input_payload=input_payload,
            retrieval_payload={},
            output_payload={},
            status=AuditStatus.ERROR,
            error_message=str(exc),
        )
    finally:
        db.close()


# ── Direct message post (used by UI Share buttons) ───────────────────────────

class SlackSendRequest(BaseModel):
    channel: str
    text: str
    thread_ts: str | None = None


@router.post("/send")
async def slack_send(req: SlackSendRequest) -> dict:
    """Post a message to a Slack channel. Used by the UI Share feature."""
    slack = SlackService()
    if not slack.bot_token:
        raise HTTPException(status_code=503, detail="Slack bot token not configured. Set SLACK_BOT_TOKEN.")
    try:
        await slack.post_message(req.channel, req.text, thread_ts=req.thread_ts)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Slack API error: {exc}") from exc
    return {"ok": True}
