from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import AIRefinement, RefinementScope, User

logger = logging.getLogger(__name__)


class RefinementService:
    """Manages AI refinement feedback that customizes report generation."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def add_refinement(
        self,
        user_id: int,
        output_type: str,
        feedback_text: str,
        context_filter: dict[str, Any] | None = None,
        scope: str = "personal",
    ) -> AIRefinement:
        """Create a new AI refinement rule for a user."""
        refinement = AIRefinement(
            user_id=user_id,
            output_type=output_type,
            feedback_text=feedback_text,
            context_filter=context_filter,
            scope=RefinementScope(scope),
            active=True,
            effectiveness=0,
        )
        self._db.add(refinement)
        self._db.commit()
        self._db.refresh(refinement)
        return refinement

    def get_refinements(
        self,
        user_id: int,
        output_type: str,
        org_id: int | None = None,
    ) -> list[AIRefinement]:
        """Return personal refinements for this user plus team refinements for the org.

        Personal refinements belong to the user. Team refinements are visible
        to all users in the org if org_id is provided.
        """
        personal = (
            self._db.query(AIRefinement)
            .filter_by(user_id=user_id, output_type=output_type, active=True)
            .filter(AIRefinement.scope == RefinementScope.personal)
            .all()
        )

        team: list[AIRefinement] = []
        if org_id is not None:
            team_users = (
                self._db.query(User.id)
                .filter_by(org_id=org_id)
                .all()
            )
            team_user_ids = [u.id for u in team_users]
            if team_user_ids:
                team = (
                    self._db.query(AIRefinement)
                    .filter(
                        AIRefinement.user_id.in_(team_user_ids),
                        AIRefinement.output_type == output_type,
                        AIRefinement.scope == RefinementScope.team,
                        AIRefinement.active == True,  # noqa: E712
                    )
                    .all()
                )

        return list(personal) + list(team)

    def promote_to_team(
        self, refinement_id: int, admin_user_id: int
    ) -> AIRefinement:
        """Promote a personal refinement to team scope (admin only)."""
        refinement = self._db.query(AIRefinement).get(refinement_id)
        if not refinement:
            raise ValueError(f"Refinement not found: {refinement_id}")

        admin_user = self._db.query(User).get(admin_user_id)
        if not admin_user or admin_user.role.value != "admin":
            raise PermissionError("Only admin users can promote refinements to team scope")

        refinement.scope = RefinementScope.team
        self._db.commit()
        self._db.refresh(refinement)
        return refinement

    def update_effectiveness(self, refinement_id: int, delta: int) -> None:
        """Adjust the effectiveness score of a refinement by delta."""
        refinement = self._db.query(AIRefinement).get(refinement_id)
        if not refinement:
            raise ValueError(f"Refinement not found: {refinement_id}")

        refinement.effectiveness = (refinement.effectiveness or 0) + delta
        self._db.commit()

    @staticmethod
    def format_refinements_prompt(refinements: list[AIRefinement]) -> str:
        """Format refinements as coaching instructions for the LLM system prompt.

        Refinements are sorted by effectiveness (highest first) and formatted
        as numbered instructions for the LLM to follow.
        """
        if not refinements:
            return ""

        sorted_refinements = sorted(
            refinements,
            key=lambda r: r.effectiveness or 0,
            reverse=True,
        )

        lines: list[str] = ["Based on user feedback, follow these additional guidelines:"]
        for idx, ref in enumerate(sorted_refinements, 1):
            scope_tag = "[team]" if ref.scope == RefinementScope.team else "[personal]"
            lines.append(f"{idx}. {scope_tag} {ref.feedback_text}")
            if ref.context_filter:
                lines.append(f"   Context: {ref.context_filter}")

        return "\n".join(lines)
