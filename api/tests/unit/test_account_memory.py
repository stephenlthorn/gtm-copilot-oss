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


def test_canonicalize_account():
    from app.services.account_memory import canonicalize_account
    assert canonicalize_account("Brex") == "brex"
    assert canonicalize_account("  BREX Inc. ") == "brex inc."


def test_get_or_create_new_account():
    from app.services.account_memory import AccountMemoryService
    from app.models import AccountDealMemory

    db = MagicMock()
    db.get.return_value = None  # not found
    svc = AccountMemoryService(db)
    result = svc.get_or_create("Brex")
    db.add.assert_called_once()
    db.flush.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.account == "brex"
    assert added.is_new_business is True


def test_get_or_create_existing_account():
    from app.services.account_memory import AccountMemoryService
    from app.models import AccountDealMemory

    existing = AccountDealMemory(account="brex", is_new_business=False)
    db = MagicMock()
    db.get.return_value = existing
    svc = AccountMemoryService(db)
    result = svc.get_or_create("Brex")
    db.add.assert_not_called()
    assert result is existing


def test_detect_is_new_business_from_stage():
    from app.services.account_memory import AccountMemoryService
    from app.models import ChorusCall
    from datetime import date

    db = MagicMock()
    svc = AccountMemoryService(db)
    call = ChorusCall(account="brex", date=date.today(), rep_email="r@t.com", stage="Discovery")
    assert svc._detect_is_new_business("brex", call) is False


def test_detect_is_new_business_no_prior_calls():
    from app.services.account_memory import AccountMemoryService
    from app.models import ChorusCall
    from datetime import date

    db = MagicMock()
    db.get.return_value = None
    db.execute.return_value.scalar_one_or_none.return_value = None
    svc = AccountMemoryService(db)
    call = ChorusCall(account="newco", date=date.today(), rep_email="r@t.com")
    assert svc._detect_is_new_business("newco", call) is True


def test_merge_delta_into_memory():
    from app.services.account_memory import AccountMemoryService
    from app.models import AccountDealMemory

    db = MagicMock()
    svc = AccountMemoryService(db)
    memory = AccountDealMemory(
        account="brex",
        meddpicc={"metrics": {"score": 1, "evidence": "old", "missing": "x"}},
        key_contacts=[],
        open_items=[],
        tech_stack={"likely": [], "possible": [], "confirmed": [], "unknown": []},
    )
    delta = {
        "meddpicc_updates": {"metrics": {"score": 3, "evidence": "new evidence", "missing": "none"}},
        "key_contacts_add": [{"name": "Panos", "title": "Lead", "role": "champion", "linkedin": ""}],
        "open_items_add": [{"item": "Send POC", "owner": "rep", "due_date": "2026-03-28", "priority": "high"}],
        "deal_stage": "Discovery",
        "summary": "Updated summary.",
    }
    svc._apply_approved_delta(memory, delta)
    assert memory.meddpicc["metrics"]["score"] == 3
    assert len(memory.key_contacts) == 1
    assert memory.key_contacts[0]["name"] == "Panos"
    assert len(memory.open_items) == 1
    assert memory.deal_stage == "Discovery"
    assert memory.summary == "Updated summary."
