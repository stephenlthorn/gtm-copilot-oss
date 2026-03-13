from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Contact, CRMSource, Deal, DealStatus
from app.services.crm.salesforce import SalesforceConnector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncResult:
    accounts_synced: int = 0
    deals_synced: int = 0
    contacts_synced: int = 0
    errors: list[str] = field(default_factory=list)


class SalesforceSyncService:
    """Syncs accounts, deals, and contacts from Salesforce into local tables."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def sync_all(
        self, org_id: int, instance_url: str, access_token: str
    ) -> SyncResult:
        connector = SalesforceConnector(
            instance_url=instance_url, access_token=access_token
        )

        errors: list[str] = []
        accounts_count = 0
        deals_count = 0
        contacts_count = 0

        try:
            accounts_count = await self._sync_accounts(connector, org_id)
        except Exception as exc:
            logger.exception("Failed to sync accounts")
            errors.append(f"accounts: {exc}")

        try:
            deals_count = await self._sync_deals(connector, org_id)
        except Exception as exc:
            logger.exception("Failed to sync deals")
            errors.append(f"deals: {exc}")

        try:
            contacts_count = await self._sync_contacts(connector, org_id)
        except Exception as exc:
            logger.exception("Failed to sync contacts")
            errors.append(f"contacts: {exc}")

        self.db.commit()
        return SyncResult(
            accounts_synced=accounts_count,
            deals_synced=deals_count,
            contacts_synced=contacts_count,
            errors=errors,
        )

    async def _sync_accounts(
        self, connector: SalesforceConnector, org_id: int
    ) -> int:
        crm_accounts = await self._fetch_all_accounts(connector)
        count = 0
        for acct in crm_accounts:
            self._upsert_account(acct, org_id)
            count += 1
        self.db.flush()
        return count

    async def _fetch_all_accounts(
        self, connector: SalesforceConnector
    ) -> list[dict]:
        resp = await connector.client.get(
            f"/services/data/v59.0/query",
            params={
                "q": (
                    "SELECT Id,Name,Industry,Website,NumberOfEmployees,"
                    "AnnualRevenue,Description,Type,Rating "
                    "FROM Account ORDER BY LastModifiedDate DESC LIMIT 1000"
                )
            },
        )
        resp.raise_for_status()
        return resp.json().get("records", [])

    def _upsert_account(self, data: dict, org_id: int) -> Account:
        external_id = data["Id"]
        existing = self.db.execute(
            select(Account).where(
                Account.external_id == external_id,
                Account.crm_source == CRMSource.salesforce,
            )
        ).scalar_one_or_none()

        if existing:
            existing.name = data.get("Name", existing.name)
            existing.industry = data.get("Industry")
            existing.website = data.get("Website")
            existing.employee_count = data.get("NumberOfEmployees")
            existing.revenue_range = str(data.get("AnnualRevenue")) if data.get("AnnualRevenue") else None
            existing.description = data.get("Description")
            existing.metadata_ = {"type": data.get("Type"), "rating": data.get("Rating")}
            existing.updated_at = datetime.utcnow()
            return existing

        row = Account(
            external_id=external_id,
            crm_source=CRMSource.salesforce,
            name=data.get("Name", ""),
            industry=data.get("Industry"),
            website=data.get("Website"),
            employee_count=data.get("NumberOfEmployees"),
            revenue_range=str(data.get("AnnualRevenue")) if data.get("AnnualRevenue") else None,
            description=data.get("Description"),
            metadata_={"type": data.get("Type"), "rating": data.get("Rating")},
            org_id=org_id,
        )
        self.db.add(row)
        return row

    async def _sync_deals(
        self, connector: SalesforceConnector, org_id: int
    ) -> int:
        resp = await connector.client.get(
            f"/services/data/v59.0/query",
            params={
                "q": (
                    "SELECT Id,Name,StageName,Amount,CloseDate,AccountId,"
                    "IsClosed,IsWon,Owner.Email "
                    "FROM Opportunity ORDER BY LastModifiedDate DESC LIMIT 1000"
                )
            },
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])

        count = 0
        for rec in records:
            self._upsert_deal(rec, org_id)
            count += 1
        self.db.flush()
        return count

    def _upsert_deal(self, data: dict, org_id: int) -> Deal:
        external_id = data["Id"]
        existing = self.db.execute(
            select(Deal).where(Deal.external_id == external_id)
        ).scalar_one_or_none()

        status_str = "won" if data.get("IsWon") else ("lost" if data.get("IsClosed") else "open")
        status = DealStatus(status_str)

        account_ext_id = data.get("AccountId")
        account = self.db.execute(
            select(Account).where(
                Account.external_id == account_ext_id,
                Account.crm_source == CRMSource.salesforce,
            )
        ).scalar_one_or_none()

        if not account:
            return existing if existing else Deal()

        if existing:
            existing.name = data.get("Name")
            existing.stage = data.get("StageName")
            existing.amount = data.get("Amount")
            existing.close_date = data.get("CloseDate")
            existing.status = status
            existing.updated_at = datetime.utcnow()
            return existing

        row = Deal(
            external_id=external_id,
            account_id=account.id,
            name=data.get("Name"),
            stage=data.get("StageName"),
            amount=data.get("Amount"),
            close_date=data.get("CloseDate"),
            status=status,
            org_id=org_id,
        )
        self.db.add(row)
        return row

    async def _sync_contacts(
        self, connector: SalesforceConnector, org_id: int
    ) -> int:
        resp = await connector.client.get(
            f"/services/data/v59.0/query",
            params={
                "q": (
                    "SELECT Id,Name,Title,Email,AccountId "
                    "FROM Contact ORDER BY LastModifiedDate DESC LIMIT 1000"
                )
            },
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])

        count = 0
        for rec in records:
            self._upsert_contact(rec, org_id)
            count += 1
        self.db.flush()
        return count

    def _upsert_contact(self, data: dict, org_id: int) -> Contact:
        external_id = data["Id"]
        existing = self.db.execute(
            select(Contact).where(Contact.external_id == external_id)
        ).scalar_one_or_none()

        account_ext_id = data.get("AccountId")
        account = self.db.execute(
            select(Account).where(
                Account.external_id == account_ext_id,
                Account.crm_source == CRMSource.salesforce,
            )
        ).scalar_one_or_none()

        if not account:
            return existing if existing else Contact()

        if existing:
            existing.name = data.get("Name")
            existing.title = data.get("Title")
            existing.email = data.get("Email")
            return existing

        row = Contact(
            external_id=external_id,
            account_id=account.id,
            name=data.get("Name"),
            title=data.get("Title"),
            email=data.get("Email"),
            org_id=org_id,
        )
        self.db.add(row)
        return row
