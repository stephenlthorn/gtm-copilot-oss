from __future__ import annotations

from app.utils.email_utils import blocked_recipients, is_internal_email


def test_internal_email_allowlist():
    assert is_internal_email("rep@example.com", ["example.com"])
    assert not is_internal_email("x@gmail.com", ["example.com"])


def test_blocked_recipients():
    blocked = blocked_recipients(["rep@example.com", "foo@example.com"], ["example.com"])
    assert blocked == ["foo@example.com"]
