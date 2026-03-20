from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NotificationType(str, Enum):
    PRE_CALL_READY = "pre_call_ready"
    POST_CALL_READY = "post_call_ready"
    DEAL_RISK = "deal_risk"
    COMPETITIVE_INTEL = "competitive_intel"
    SYSTEM_ALERT = "system_alert"


class DeliveryChannel(str, Enum):
    SLACK_DM = "slack_dm"
    SLACK_CHANNEL = "slack_channel"


class NotificationTiming(str, Enum):
    IMMEDIATE = "immediate"
    NIGHT_BEFORE = "night_before"
    MORNING_OF = "morning_of"
    ONE_HOUR_BEFORE = "1hr_before"
    TWO_HOURS_BEFORE = "2hrs_before"
    ONE_HOUR_AFTER = "1hr_after"
    END_OF_DAY = "end_of_day"


@dataclass(frozen=True)
class Notification:
    type: NotificationType
    title: str
    body: str
    user_id: int
    org_id: int
    metadata: dict = field(default_factory=dict)
    channel_override: str | None = None

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "title": self.title,
            "body": self.body,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "metadata": self.metadata,
            "channel_override": self.channel_override,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Notification:
        return cls(
            type=NotificationType(data["type"]),
            title=data["title"],
            body=data["body"],
            user_id=data["user_id"],
            org_id=data["org_id"],
            metadata=data.get("metadata", {}),
            channel_override=data.get("channel_override"),
        )
