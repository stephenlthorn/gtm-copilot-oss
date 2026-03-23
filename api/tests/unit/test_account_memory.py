"""Tests for AccountDealMemory model and AccountMemoryService."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from datetime import date


def test_account_deal_memory_model_importable():
    from app.models import AccountDealMemory
    assert AccountDealMemory.__tablename__ == "account_deal_memory"


def test_account_deal_memory_defaults():
    from app.models import AccountDealMemory
    m = AccountDealMemory(account="brex")
    assert m.is_new_business is True
    assert m.status == "active"
    assert m.pending_review is False
    assert m.call_count == 0


def test_chorus_call_source_type_default():
    from app.models import ChorusCall
    c = ChorusCall(
        account="brex",
        date=date.today(),
        rep_email="rep@test.com",
    )
    assert c.source_type == "chorus"


def test_chorus_call_chorus_call_id_nullable():
    from app.models import ChorusCall
    col = ChorusCall.__table__.columns["chorus_call_id"]
    assert col.nullable is True
