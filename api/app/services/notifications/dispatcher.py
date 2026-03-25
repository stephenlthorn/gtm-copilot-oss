from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.entities import NotificationPreference, User, UserRole
from app.services.notifications.preferences import NotificationPreferencesService
from app.services.notifications.slack_service import SlackService
from app.services.notifications.types import (
    DeliveryChannel,
    Notification,
    NotificationType,
    NotificationTiming,
)

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """Route notifications to the appropriate channel based on user preferences."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()
        self._preferences_service = NotificationPreferencesService(db)
        self._slack: SlackService | None = None
        if self._settings.slack_bot_token:
            self._slack = SlackService(bot_token=self._settings.slack_bot_token)

    def _get_user(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def _resolve_channel_target(
        self, user: User, pref: dict[str, Any], notification: Notification
    ) -> tuple[str, str | None]:
        """Return (delivery_method, target) for a notification.

        delivery_method is 'dm' or 'channel'.
        target is the Slack channel name (for channel delivery) or None (for DM).
        """
        if notification.channel_override:
            return "channel", notification.channel_override

        channel = pref.get("channel", DeliveryChannel.SLACK_DM.value)

        if channel == DeliveryChannel.SLACK_CHANNEL.value:
            channel_name = pref.get(
                "channel_name",
                self._settings.slack_default_channel or "#general",
            )
            return "channel", channel_name

        return "dm", None

    def dispatch(self, notification: Notification) -> bool:
        if not self._slack:
            logger.error("Slack service not configured; cannot dispatch notification")
            return False

        user = self._get_user(notification.user_id)
        if not user:
            logger.error("User %d not found", notification.user_id)
            return False

        pref = self._preferences_service.get_preference_for_type(
            notification.user_id, notification.type.value
        )

        if not pref.get("enabled", True):
            logger.info(
                "Notification type %s disabled for user %d",
                notification.type.value,
                notification.user_id,
            )
            return False

        timing = pref.get("timing", NotificationTiming.IMMEDIATE.value)
        if timing != NotificationTiming.IMMEDIATE.value:
            return self._schedule_notification(notification, timing)

        return self._send_now(notification, user, pref)

    def _send_now(
        self, notification: Notification, user: User, pref: dict[str, Any]
    ) -> bool:
        if not self._slack:
            return False

        delivery_method, target = self._resolve_channel_target(user, pref, notification)

        formatter = self._get_formatter(notification)
        if formatter:
            text, blocks = formatter
        else:
            text = f"*{notification.title}*\n{notification.body}"
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text[:3000]},
                },
            ]

        if delivery_method == "dm":
            return self._slack.send_dm(
                user_email=user.email,
                message=text,
                blocks=blocks,
            )

        channel = target or self._settings.slack_default_channel or "#general"
        return self._slack.send_channel_message(
            channel=channel,
            message=text,
            blocks=blocks,
        )

    def _get_formatter(
        self, notification: Notification
    ) -> tuple[str, list[dict]] | None:
        if not self._slack:
            return None

        metadata = notification.metadata
        if not isinstance(metadata, dict):
            logger.warning(
                "Notification metadata is not a dict (got %s); skipping formatter",
                type(metadata).__name__,
            )
            return None

        try:
            if notification.type == NotificationType.PRE_CALL_READY and metadata.get("report"):
                return self._slack.format_precall_notification(metadata["report"])

            if notification.type == NotificationType.POST_CALL_READY and metadata.get("report"):
                return self._slack.format_postcall_notification(metadata["report"])

            if notification.type == NotificationType.DEAL_RISK and metadata.get("risk"):
                return self._slack.format_deal_risk_notification(metadata["risk"])

            if notification.type == NotificationType.COMPETITIVE_INTEL and metadata.get("intel"):
                return self._slack.format_competitive_intel(metadata["intel"])
        except (KeyError, TypeError, AttributeError):
            logger.warning(
                "Malformed metadata for notification type %s; falling back to default formatter",
                notification.type,
            )
            return None

        return None

    def _schedule_notification(
        self, notification: Notification, timing: str
    ) -> bool:
        try:
            from app.tasks.notification_tasks import scheduled_notification

            eta_seconds = _timing_to_seconds(timing)
            scheduled_notification.apply_async(
                args=[notification.to_dict()],
                countdown=eta_seconds,
            )
            logger.info(
                "Scheduled notification %s for user %d in %d seconds",
                notification.type.value,
                notification.user_id,
                eta_seconds,
            )
            return True
        except Exception:
            logger.exception("Failed to schedule notification")
            return False

    def dispatch_system_alert(self, message: str, org_id: int) -> bool:
        if not self._slack:
            logger.error("Slack service not configured; cannot dispatch system alert")
            return False

        stmt = select(User).where(
            User.org_id == org_id,
            User.role == UserRole.admin,
        )
        admins = self._db.execute(stmt).scalars().all()

        if not admins:
            logger.warning("No admin users found for org %d", org_id)
            return False

        success = False
        for admin in admins:
            notification = Notification(
                type=NotificationType.SYSTEM_ALERT,
                title="System Alert",
                body=message,
                user_id=admin.id,
                org_id=org_id,
            )
            if self.dispatch(notification):
                success = True

        return success


def _timing_to_seconds(timing: str) -> int:
    mapping = {
        NotificationTiming.NIGHT_BEFORE.value: 0,
        NotificationTiming.MORNING_OF.value: 0,
        NotificationTiming.ONE_HOUR_BEFORE.value: 0,
        NotificationTiming.TWO_HOURS_BEFORE.value: 0,
        NotificationTiming.ONE_HOUR_AFTER.value: 3600,
        NotificationTiming.END_OF_DAY.value: 0,
        NotificationTiming.IMMEDIATE.value: 0,
    }
    return mapping.get(timing, 0)
