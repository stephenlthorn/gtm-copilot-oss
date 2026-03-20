from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    _HAS_SLACK_SDK = True
except ImportError:
    _HAS_SLACK_SDK = False

_SLACK_API_BASE = "https://slack.com/api"


class SlackService:
    """Send notifications via Slack DMs and channels.

    Uses slack_sdk when available, falls back to httpx for direct API calls.
    """

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token
        self._client: Any | None = None
        if _HAS_SLACK_SDK and bot_token:
            self._client = WebClient(token=bot_token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _lookup_user_by_email(self, email: str) -> str | None:
        if self._client:
            try:
                resp = self._client.users_lookupByEmail(email=email)
                if resp.get("ok"):
                    return resp["user"]["id"]
            except Exception:
                logger.warning("slack_sdk lookup failed for %s, trying httpx", email)

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{_SLACK_API_BASE}/users.lookupByEmail",
                    params={"email": email},
                    headers=self._headers(),
                )
                data = resp.json()
                if data.get("ok"):
                    return data["user"]["id"]
                logger.warning("Slack user lookup failed for %s: %s", email, data.get("error"))
        except Exception:
            logger.exception("Failed to lookup Slack user by email: %s", email)

        return None

    def _open_dm_channel(self, user_id: str) -> str | None:
        if self._client:
            try:
                resp = self._client.conversations_open(users=[user_id])
                if resp.get("ok"):
                    return resp["channel"]["id"]
            except Exception:
                logger.warning("slack_sdk conversations.open failed for %s, trying httpx", user_id)

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{_SLACK_API_BASE}/conversations.open",
                    json={"users": user_id},
                    headers=self._headers(),
                )
                data = resp.json()
                if data.get("ok"):
                    return data["channel"]["id"]
                logger.warning("Slack conversations.open failed: %s", data.get("error"))
        except Exception:
            logger.exception("Failed to open DM channel for user: %s", user_id)

        return None

    def _post_message(self, channel: str, text: str, blocks: list[dict] | None = None) -> bool:
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks

        if self._client:
            try:
                resp = self._client.chat_postMessage(**payload)
                return bool(resp.get("ok"))
            except Exception:
                logger.warning("slack_sdk chat.postMessage failed, trying httpx")

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{_SLACK_API_BASE}/chat.postMessage",
                    json=payload,
                    headers=self._headers(),
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.error("Slack postMessage error: %s", data.get("error"))
                    return False
                return True
        except Exception:
            logger.exception("Failed to post Slack message to %s", channel)
            return False

    def send_dm(self, user_email: str, message: str, blocks: list[dict] | None = None) -> bool:
        slack_user_id = self._lookup_user_by_email(user_email)
        if not slack_user_id:
            logger.error("Could not find Slack user for email: %s", user_email)
            return False

        dm_channel = self._open_dm_channel(slack_user_id)
        if not dm_channel:
            logger.error("Could not open DM channel for user: %s", slack_user_id)
            return False

        return self._post_message(dm_channel, message, blocks)

    def send_channel_message(
        self, channel: str, message: str, blocks: list[dict] | None = None
    ) -> bool:
        return self._post_message(channel, message, blocks)

    def format_precall_notification(self, report: dict) -> tuple[str, list[dict]]:
        account = report.get("account", "Unknown Account")
        meeting_time = report.get("meeting_time", "")
        summary = report.get("summary", "Your pre-call brief is ready.")

        text = f"Pre-Call Brief Ready: {account}"
        if meeting_time:
            text += f" ({meeting_time})"

        blocks: list[dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Pre-Call Brief: {account}"},
            },
        ]

        if meeting_time:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Meeting:* {meeting_time}"},
            })

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary[:2000]},
        })

        key_points = report.get("key_points", [])
        if key_points:
            points_text = "\n".join(f"* {p}" for p in key_points[:5])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Key Points:*\n{points_text}"},
            })

        report_url = report.get("report_url")
        if report_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Full Brief"},
                        "url": report_url,
                        "action_id": "view_precall_brief",
                    }
                ],
            })

        return text, blocks

    def format_postcall_notification(self, report: dict) -> tuple[str, list[dict]]:
        account = report.get("account", "Unknown Account")
        summary = report.get("summary", "Your post-call analysis is ready.")

        text = f"Post-Call Analysis Ready: {account}"

        blocks: list[dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Post-Call Analysis: {account}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary[:2000]},
            },
        ]

        next_steps = report.get("next_steps", [])
        if next_steps:
            steps_text = "\n".join(f"* {s}" for s in next_steps[:5])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Next Steps:*\n{steps_text}"},
            })

        risks = report.get("risks", [])
        if risks:
            risk_text = "\n".join(f"* :warning: {r}" for r in risks[:3])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Risks Identified:*\n{risk_text}"},
            })

        report_url = report.get("report_url")
        if report_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Full Report"},
                        "url": report_url,
                        "action_id": "view_postcall_report",
                    }
                ],
            })

        return text, blocks

    def format_deal_risk_notification(self, risk: dict) -> tuple[str, list[dict]]:
        account = risk.get("account", "Unknown Account")
        severity = risk.get("severity", "medium")
        description = risk.get("description", "A deal risk has been detected.")

        severity_emoji = {
            "critical": ":rotating_light:",
            "high": ":warning:",
            "medium": ":large_yellow_circle:",
            "low": ":information_source:",
        }.get(severity.lower(), ":warning:")

        text = f"{severity_emoji} Deal Risk Alert: {account} ({severity.upper()})"

        blocks: list[dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Deal Risk Alert: {account}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:* {severity_emoji} {severity.upper()}"},
                    {"type": "mrkdwn", "text": f"*Account:* {account}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": description[:2000]},
            },
        ]

        deal_name = risk.get("deal_name")
        if deal_name:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Deal:* {deal_name}"},
            })

        return text, blocks

    def format_competitive_intel(self, intel: dict) -> tuple[str, list[dict]]:
        competitor = intel.get("competitor_name", "Unknown Competitor")
        title = intel.get("title", "New competitive intelligence detected.")
        summary = intel.get("summary", "")
        intel_type = intel.get("intel_type", "other")
        source_url = intel.get("source_url", "")

        text = f"Competitive Intel: {competitor} - {title}"

        blocks: list[dict] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Competitive Intel: {competitor}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:* {intel_type.replace('_', ' ').title()}"},
                    {"type": "mrkdwn", "text": f"*Competitor:* {competitor}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n{summary[:1500]}"},
            },
        ]

        if source_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Source"},
                        "url": source_url,
                        "action_id": "view_competitive_intel_source",
                    }
                ],
            })

        return text, blocks
