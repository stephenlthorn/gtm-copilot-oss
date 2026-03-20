from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class CRMAccount:
    external_id: str
    name: str
    industry: str | None
    website: str | None
    employee_count: int | None
    revenue_range: str | None
    description: str | None
    metadata: dict | None = None


@dataclass(frozen=True)
class CRMDeal:
    external_id: str
    account_external_id: str
    name: str
    stage: str
    amount: float | None
    close_date: str | None
    owner_email: str | None
    status: str
    metadata: dict | None = None


@dataclass(frozen=True)
class CRMContact:
    external_id: str
    account_external_id: str
    name: str
    title: str | None
    email: str | None
    linkedin_url: str | None
    metadata: dict | None = None


@dataclass(frozen=True)
class SyncResult:
    accounts_synced: int
    deals_synced: int
    contacts_synced: int
    errors: list[str] = field(default_factory=list)


class CRMConnector(Protocol):
    async def get_account(self, account_id: str) -> CRMAccount: ...

    async def get_deals(self, account_id: str) -> list[CRMDeal]: ...

    async def get_contacts(self, account_id: str) -> list[CRMContact]: ...

    async def sync_accounts(self) -> SyncResult: ...
