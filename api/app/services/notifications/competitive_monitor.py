from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.entities import CompetitorIntel, IntelType, TrackedCompetitor, User, UserRole
from app.services.notifications.dispatcher import NotificationDispatcher
from app.services.notifications.types import Notification, NotificationType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompetitorIntelResult:
    competitor_name: str
    intel_type: str
    title: str
    summary: str
    source_url: str
    is_notable: bool
    raw_content: str = ""


class CompetitiveMonitorService:
    """Monitor tracked competitors for news, reviews, and website changes."""

    def __init__(self, db: Session, openai_api_key: str | None = None) -> None:
        self._db = db
        self._settings = get_settings()
        self._openai_api_key = openai_api_key or self._settings.openai_api_key

    def run_monitoring(self, org_id: int) -> list[CompetitorIntelResult]:
        competitors = self._get_tracked_competitors(org_id)
        if not competitors:
            logger.info("No active tracked competitors for org %d", org_id)
            return []

        all_intel: list[CompetitorIntelResult] = []

        for competitor in competitors:
            try:
                intel_items = self._monitor_competitor(competitor, org_id)
                all_intel.extend(intel_items)
            except Exception:
                logger.exception(
                    "Failed to monitor competitor: %s", competitor.name
                )

        self._store_intel(all_intel, org_id)
        self._notify_notable(all_intel, org_id)

        return all_intel

    def _get_tracked_competitors(self, org_id: int) -> list[TrackedCompetitor]:
        stmt = select(TrackedCompetitor).where(
            TrackedCompetitor.org_id == org_id,
            TrackedCompetitor.active == True,  # noqa: E712
        )
        return list(self._db.execute(stmt).scalars().all())

    def _monitor_competitor(
        self, competitor: TrackedCompetitor, org_id: int
    ) -> list[CompetitorIntelResult]:
        results: list[CompetitorIntelResult] = []

        news_items = self._scrape_news(competitor)
        results.extend(news_items)

        review_items = self._check_reviews(competitor)
        results.extend(review_items)

        website_changes = self._check_website(competitor)
        results.extend(website_changes)

        if results and self._openai_api_key:
            results = self._ai_analyze(results, competitor.name)

        return results

    def _scrape_news(self, competitor: TrackedCompetitor) -> list[CompetitorIntelResult]:
        try:
            from app.services.connectors.firecrawl import FirecrawlConnector

            connector = FirecrawlConnector()
            search_query = f"{competitor.name} news announcements"
            raw_results = connector.search(query=search_query, limit=5)

            items: list[CompetitorIntelResult] = []
            for result in raw_results:
                items.append(
                    CompetitorIntelResult(
                        competitor_name=competitor.name,
                        intel_type=IntelType.news.value,
                        title=result.get("title", "News Item"),
                        summary=result.get("description", "")[:500],
                        source_url=result.get("url", ""),
                        is_notable=False,
                        raw_content=result.get("content", "")[:2000],
                    )
                )
            return items
        except ImportError:
            logger.warning("FirecrawlConnector not available; skipping news scrape")
            return []
        except Exception:
            logger.exception("Failed to scrape news for %s", competitor.name)
            return []

    def _check_reviews(self, competitor: TrackedCompetitor) -> list[CompetitorIntelResult]:
        try:
            from app.services.connectors.firecrawl import FirecrawlConnector

            connector = FirecrawlConnector()
            search_query = f"{competitor.name} G2 reviews TrustRadius"
            raw_results = connector.search(query=search_query, limit=3)

            items: list[CompetitorIntelResult] = []
            for result in raw_results:
                items.append(
                    CompetitorIntelResult(
                        competitor_name=competitor.name,
                        intel_type=IntelType.review.value,
                        title=result.get("title", "Review"),
                        summary=result.get("description", "")[:500],
                        source_url=result.get("url", ""),
                        is_notable=False,
                        raw_content=result.get("content", "")[:2000],
                    )
                )
            return items
        except ImportError:
            logger.warning("FirecrawlConnector not available; skipping review check")
            return []
        except Exception:
            logger.exception("Failed to check reviews for %s", competitor.name)
            return []

    def _check_website(self, competitor: TrackedCompetitor) -> list[CompetitorIntelResult]:
        if not competitor.website:
            return []

        try:
            from app.services.connectors.firecrawl import FirecrawlConnector

            connector = FirecrawlConnector()
            raw_result = connector.scrape(url=competitor.website)

            if raw_result:
                return [
                    CompetitorIntelResult(
                        competitor_name=competitor.name,
                        intel_type=IntelType.other.value,
                        title=f"{competitor.name} Website Update",
                        summary=raw_result.get("description", "")[:500],
                        source_url=competitor.website,
                        is_notable=False,
                        raw_content=raw_result.get("content", "")[:2000],
                    )
                ]
            return []
        except ImportError:
            logger.warning("FirecrawlConnector not available; skipping website check")
            return []
        except Exception:
            logger.exception("Failed to check website for %s", competitor.name)
            return []

    def _ai_analyze(
        self,
        items: list[CompetitorIntelResult],
        competitor_name: str,
    ) -> list[CompetitorIntelResult]:
        if not self._openai_api_key:
            return items

        try:
            from app.services.llm_provider.openai_provider import OpenAIProvider
            import asyncio

            provider = OpenAIProvider(
                api_key=self._openai_api_key,
                default_model=self._settings.openai_model,
            )

            summaries = "\n\n".join(
                f"- [{item.intel_type}] {item.title}: {item.summary}"
                for item in items
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a competitive intelligence analyst. "
                        "Analyze the following intel items about a competitor "
                        "and determine which are notable (significant product launches, "
                        "pricing changes, major partnerships, or strategic shifts). "
                        "Respond with a JSON array of objects with fields: "
                        "index (0-based), is_notable (bool), enhanced_summary (str)."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Competitor: {competitor_name}\n\n"
                        f"Intel items:\n{summaries}"
                    ),
                },
            ]

            loop = asyncio.new_event_loop()
            try:
                response = loop.run_until_complete(provider.chat(messages))
            finally:
                loop.close()

            import json

            try:
                analysis = json.loads(response.content)
            except (json.JSONDecodeError, TypeError):
                logger.warning("AI analysis returned non-JSON response")
                return items

            enhanced: list[CompetitorIntelResult] = []
            for i, item in enumerate(items):
                match = next(
                    (a for a in analysis if a.get("index") == i),
                    None,
                )
                if match:
                    enhanced.append(
                        CompetitorIntelResult(
                            competitor_name=item.competitor_name,
                            intel_type=item.intel_type,
                            title=item.title,
                            summary=match.get("enhanced_summary", item.summary),
                            source_url=item.source_url,
                            is_notable=match.get("is_notable", False),
                            raw_content=item.raw_content,
                        )
                    )
                else:
                    enhanced.append(item)

            return enhanced

        except Exception:
            logger.exception("AI analysis failed for %s", competitor_name)
            return items

    def _store_intel(
        self, items: list[CompetitorIntelResult], org_id: int
    ) -> None:
        for item in items:
            row = CompetitorIntel(
                competitor_name=item.competitor_name,
                intel_type=IntelType(item.intel_type) if item.intel_type else None,
                title=item.title,
                summary=item.summary,
                source_url=item.source_url,
                raw_content=item.raw_content,
                is_notable=item.is_notable,
                org_id=org_id,
            )
            self._db.add(row)

        self._db.commit()

    def _notify_notable(
        self, items: list[CompetitorIntelResult], org_id: int
    ) -> None:
        notable = [i for i in items if i.is_notable]
        if not notable:
            return

        dispatcher = NotificationDispatcher(self._db)

        stmt = select(User).where(
            User.org_id == org_id,
            User.role.in_([UserRole.admin, UserRole.se, UserRole.sales_rep]),
        )
        users = self._db.execute(stmt).scalars().all()

        for item in notable:
            for user in users:
                notification = Notification(
                    type=NotificationType.COMPETITIVE_INTEL,
                    title=f"Competitive Intel: {item.competitor_name}",
                    body=item.summary,
                    user_id=user.id,
                    org_id=org_id,
                    metadata={
                        "intel": {
                            "competitor_name": item.competitor_name,
                            "intel_type": item.intel_type,
                            "title": item.title,
                            "summary": item.summary,
                            "source_url": item.source_url,
                        }
                    },
                )
                try:
                    dispatcher.dispatch(notification)
                except Exception:
                    logger.exception(
                        "Failed to notify user %d about intel for %s",
                        user.id,
                        item.competitor_name,
                    )
