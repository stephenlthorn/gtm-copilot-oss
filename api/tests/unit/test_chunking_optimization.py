"""Tests for chunking optimization changes."""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Task 1: Migration / model tests
# ---------------------------------------------------------------------------

def test_chorus_call_has_call_outcome_field():
    """ChorusCall model must expose call_outcome as a mapped attribute."""
    from app.models.entities import ChorusCall
    # Verify the column exists in the mapper (no DB needed)
    mapper = ChorusCall.__mapper__
    assert "call_outcome" in [c.key for c in mapper.column_attrs]


def test_migration_adds_call_outcome_column():
    """Migration upgrade/downgrade must not raise on SQLite (non-MySQL dialect)."""
    import importlib.util, sys
    from pathlib import Path
    migration_path = Path(__file__).parents[2] / "alembic" / "versions" / "20260324_000001_add_hnsw_index_and_call_outcome.py"
    spec = importlib.util.spec_from_file_location(
        "migration_20260324",
        migration_path,
    )
    migration = importlib.util.module_from_spec(spec)
    sys.modules["migration_20260324"] = migration
    spec.loader.exec_module(migration)

    mock_bind = MagicMock()
    mock_bind.dialect.name = "sqlite"

    with patch("alembic.op.get_bind", return_value=mock_bind), \
         patch("alembic.op.add_column") as mock_add, \
         patch("alembic.op.drop_column") as mock_drop:
        migration.upgrade()
        mock_add.assert_called_once()
        assert mock_add.call_args[0][0] == "chorus_calls"
        migration.downgrade()
        mock_drop.assert_called_once_with("chorus_calls", "call_outcome")
