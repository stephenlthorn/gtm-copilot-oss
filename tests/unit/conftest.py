"""Lightweight conftest for unit tests that don't need the full app."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///test.db")
os.environ.setdefault("AUTO_CREATE_SCHEMA", "true")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OPENAI_BASE_URL", "")
os.environ.setdefault("CHORUS_API_KEY", "")
os.environ.setdefault("CHORUS_BASE_URL", "")
os.environ.setdefault("DISABLE_CODEX_AUTH", "true")
