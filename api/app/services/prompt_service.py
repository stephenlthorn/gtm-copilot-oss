from __future__ import annotations

import time
from sqlalchemy.orm import Session
from app.models.prompt_models import PromptRegistry, PromptVersion, PromptUserOverride

CACHE_TTL_SECONDS = 300  # 5 minutes
_cache: dict[str, tuple[float, str]] = {}


def clear_cache() -> None:
    """Clear all cached prompt content. Intended for tests."""
    _cache.clear()


class PromptService:
    def __init__(self, db: Session):
        self.db = db

    # ── Resolution ────────────────────────────────────────────

    def resolve(
        self, prompt_id: str, *, user_email: str | None = None
    ) -> str | None:
        # Check user override first
        if user_email:
            override = (
                self.db.query(PromptUserOverride)
                .filter_by(prompt_id=prompt_id, user_email=user_email)
                .first()
            )
            if override:
                return override.content

        # Check cache
        cache_key = f"prompt:{prompt_id}"
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        # Query DB
        prompt = self.db.get(PromptRegistry, prompt_id)
        if prompt is None:
            return None

        # Cache and return
        _cache[cache_key] = (time.time(), prompt.current_content)
        return prompt.current_content

    # ── CRUD ──────────────────────────────────────────────────

    def list_all(self) -> list[dict]:
        prompts = self.db.query(PromptRegistry).order_by(PromptRegistry.category, PromptRegistry.name).all()
        return [
            {
                "id": p.id,
                "category": p.category,
                "name": p.name,
                "description": p.description,
                "variables": p.variables,
                "updated_by": p.updated_by,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in prompts
        ]

    def get(self, prompt_id: str) -> dict | None:
        prompt = self.db.get(PromptRegistry, prompt_id)
        if prompt is None:
            return None
        return {
            "id": prompt.id,
            "category": prompt.category,
            "name": prompt.name,
            "description": prompt.description,
            "default_content": prompt.default_content,
            "current_content": prompt.current_content,
            "variables": prompt.variables,
            "updated_by": prompt.updated_by,
            "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
        }

    def save(
        self,
        prompt_id: str,
        content: str,
        *,
        edited_by: str,
        note: str | None = None,
    ) -> None:
        prompt = self.db.get(PromptRegistry, prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt '{prompt_id}' not found")

        # Determine next version number
        max_version = (
            self.db.query(PromptVersion.version)
            .filter_by(prompt_id=prompt_id)
            .order_by(PromptVersion.version.desc())
            .first()
        )
        next_version = (max_version[0] + 1) if max_version else 1

        # Create version record
        version = PromptVersion(
            prompt_id=prompt_id,
            version=next_version,
            content=content,
            edited_by=edited_by,
            note=note,
        )
        self.db.add(version)

        # Update current content
        prompt.current_content = content
        prompt.updated_by = edited_by
        self.db.commit()

        # Invalidate cache
        _cache.pop(f"prompt:{prompt_id}", None)

    def reset(self, prompt_id: str, *, reset_by: str) -> None:
        prompt = self.db.get(PromptRegistry, prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        self.save(prompt_id, prompt.default_content, edited_by=reset_by, note="Reset to factory default")

    def rollback(self, prompt_id: str, version: int, *, rolled_back_by: str) -> None:
        ver = (
            self.db.query(PromptVersion)
            .filter_by(prompt_id=prompt_id, version=version)
            .first()
        )
        if ver is None:
            raise ValueError(f"Version {version} not found for '{prompt_id}'")
        self.save(prompt_id, ver.content, edited_by=rolled_back_by, note=f"Rollback to v{version}")

    def get_versions(self, prompt_id: str) -> list[dict]:
        versions = (
            self.db.query(PromptVersion)
            .filter_by(prompt_id=prompt_id)
            .order_by(PromptVersion.version.desc())
            .all()
        )
        return [
            {
                "version": v.version,
                "content": v.content,
                "edited_by": v.edited_by,
                "edited_at": v.edited_at.isoformat() if v.edited_at else None,
                "note": v.note,
            }
            for v in versions
        ]

    def get_version(self, prompt_id: str, version: int) -> dict | None:
        ver = (
            self.db.query(PromptVersion)
            .filter_by(prompt_id=prompt_id, version=version)
            .first()
        )
        if ver is None:
            return None
        return {
            "version": ver.version,
            "content": ver.content,
            "edited_by": ver.edited_by,
            "edited_at": ver.edited_at.isoformat() if ver.edited_at else None,
            "note": ver.note,
        }

    # ── User Overrides ────────────────────────────────────────

    def get_user_override(self, prompt_id: str, user_email: str) -> dict | None:
        override = (
            self.db.query(PromptUserOverride)
            .filter_by(prompt_id=prompt_id, user_email=user_email)
            .first()
        )
        if override is None:
            return None
        return {
            "prompt_id": override.prompt_id,
            "user_email": override.user_email,
            "content": override.content,
            "updated_at": override.updated_at.isoformat() if override.updated_at else None,
        }

    def save_user_override(self, prompt_id: str, user_email: str, content: str) -> None:
        override = (
            self.db.query(PromptUserOverride)
            .filter_by(prompt_id=prompt_id, user_email=user_email)
            .first()
        )
        if override:
            override.content = content
        else:
            override = PromptUserOverride(
                prompt_id=prompt_id, user_email=user_email, content=content
            )
            self.db.add(override)
        self.db.commit()

    def delete_user_override(self, prompt_id: str, user_email: str) -> None:
        override = (
            self.db.query(PromptUserOverride)
            .filter_by(prompt_id=prompt_id, user_email=user_email)
            .first()
        )
        if override:
            self.db.delete(override)
            self.db.commit()
