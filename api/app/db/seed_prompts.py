from sqlalchemy.orm import Session
from app.models.prompt_models import PromptRegistry
from app.prompts.defaults import ALL_DEFAULTS


def seed_prompts(db: Session) -> int:
    """Seed prompt_registry with factory defaults. Idempotent — skips existing rows."""
    seeded = 0
    for prompt_id, meta in ALL_DEFAULTS.items():
        existing = db.get(PromptRegistry, prompt_id)
        if existing is not None:
            continue
        prompt = PromptRegistry(
            id=prompt_id,
            category=meta["category"],
            name=meta["name"],
            description=meta["description"],
            default_content=meta["content"],
            current_content=meta["content"],
            variables=meta["variables"],
        )
        db.add(prompt)
        seeded += 1
    db.commit()
    return seeded
