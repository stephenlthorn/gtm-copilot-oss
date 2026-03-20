from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import NotificationPreference

logger = logging.getLogger(__name__)

DEFAULT_PREFERENCES: dict[str, dict[str, Any]] = {
    "pre_call_ready": {
        "enabled": True,
        "timing": "morning_of",
        "channel": "slack_dm",
    },
    "post_call_ready": {
        "enabled": True,
        "timing": "immediate",
        "channel": "slack_dm",
    },
    "deal_risk": {
        "enabled": True,
        "timing": "immediate",
        "channel": "slack_dm",
    },
    "competitive_intel": {
        "enabled": True,
        "timing": "immediate",
        "channel": "slack_channel",
        "channel_name": "#competitive-intel",
    },
    "system_alert": {
        "enabled": True,
        "timing": "immediate",
        "channel": "slack_dm",
    },
}


class NotificationPreferencesService:
    """Manage per-user notification preferences with sensible defaults."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_preferences(self, user_id: int) -> dict[str, dict[str, Any]]:
        stmt = select(NotificationPreference).where(
            NotificationPreference.user_id == user_id
        )
        rows = self._db.execute(stmt).scalars().all()

        result: dict[str, dict[str, Any]] = {}
        for key, defaults in DEFAULT_PREFERENCES.items():
            result[key] = dict(defaults)

        for row in rows:
            notification_type = row.notification_type
            if notification_type in result:
                result[notification_type]["enabled"] = row.enabled
                if row.timing:
                    result[notification_type]["timing"] = row.timing
                if row.channel:
                    result[notification_type]["channel"] = row.channel

        return result

    def get_preference_for_type(
        self, user_id: int, notification_type: str
    ) -> dict[str, Any]:
        prefs = self.get_preferences(user_id)
        return prefs.get(notification_type, DEFAULT_PREFERENCES.get(notification_type, {}))

    def update_preferences(
        self, user_id: int, org_id: int, prefs: dict[str, dict[str, Any]]
    ) -> list[NotificationPreference]:
        updated: list[NotificationPreference] = []

        for notification_type, settings in prefs.items():
            if notification_type not in DEFAULT_PREFERENCES:
                logger.warning("Ignoring unknown notification type: %s", notification_type)
                continue

            stmt = select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
            existing = self._db.execute(stmt).scalar_one_or_none()

            if existing:
                if "enabled" in settings:
                    existing.enabled = settings["enabled"]
                if "timing" in settings:
                    existing.timing = settings["timing"]
                if "channel" in settings:
                    existing.channel = settings["channel"]
                updated.append(existing)
            else:
                defaults = DEFAULT_PREFERENCES[notification_type]
                row = NotificationPreference(
                    user_id=user_id,
                    notification_type=notification_type,
                    enabled=settings.get("enabled", defaults["enabled"]),
                    timing=settings.get("timing", defaults["timing"]),
                    channel=settings.get("channel", defaults["channel"]),
                    org_id=org_id,
                )
                self._db.add(row)
                updated.append(row)

        self._db.commit()
        return updated
