from __future__ import annotations

import httpx

from .base import CRMAccount, CRMContact, CRMDeal, SyncResult

_SF_API_VERSION = "v59.0"


class SalesforceConnector:
    """Salesforce CRM connector using the REST API."""

    def __init__(self, instance_url: str, access_token: str) -> None:
        self.instance_url = instance_url
        self.access_token = access_token
        self.client = httpx.AsyncClient(
            base_url=instance_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )

    async def get_account(self, account_id: str) -> CRMAccount:
        resp = await self.client.get(
            f"/services/data/{_SF_API_VERSION}/sobjects/Account/{account_id}"
        )
        resp.raise_for_status()
        data = resp.json()
        return CRMAccount(
            external_id=data["Id"],
            name=data.get("Name", ""),
            industry=data.get("Industry"),
            website=data.get("Website"),
            employee_count=data.get("NumberOfEmployees"),
            revenue_range=data.get("AnnualRevenue"),
            description=data.get("Description"),
            metadata={"type": data.get("Type"), "rating": data.get("Rating")},
        )

    async def get_deals(self, account_id: str) -> list[CRMDeal]:
        query = (
            "SELECT Id,Name,StageName,Amount,CloseDate,Owner.Email,IsClosed,IsWon "
            f"FROM Opportunity WHERE AccountId='{account_id}'"
        )
        resp = await self.client.get(
            f"/services/data/{_SF_API_VERSION}/query",
            params={"q": query},
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        deals: list[CRMDeal] = []
        for r in records:
            status = "won" if r.get("IsWon") else ("lost" if r.get("IsClosed") else "open")
            owner = r.get("Owner")
            deals.append(
                CRMDeal(
                    external_id=r["Id"],
                    account_external_id=account_id,
                    name=r.get("Name", ""),
                    stage=r.get("StageName", ""),
                    amount=r.get("Amount"),
                    close_date=r.get("CloseDate"),
                    owner_email=owner.get("Email") if isinstance(owner, dict) else None,
                    status=status,
                )
            )
        return deals

    async def get_contacts(self, account_id: str) -> list[CRMContact]:
        query = (
            "SELECT Id,Name,Title,Email "
            f"FROM Contact WHERE AccountId='{account_id}'"
        )
        resp = await self.client.get(
            f"/services/data/{_SF_API_VERSION}/query",
            params={"q": query},
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        return [
            CRMContact(
                external_id=r["Id"],
                account_external_id=account_id,
                name=r.get("Name", ""),
                title=r.get("Title"),
                email=r.get("Email"),
                linkedin_url=None,
            )
            for r in records
        ]

    async def sync_accounts(self) -> SyncResult:
        query = (
            "SELECT Id,Name,Industry,Website,NumberOfEmployees,"
            "AnnualRevenue,Description,Type,Rating "
            "FROM Account ORDER BY LastModifiedDate DESC LIMIT 1000"
        )
        resp = await self.client.get(
            f"/services/data/{_SF_API_VERSION}/query",
            params={"q": query},
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        return SyncResult(
            accounts_synced=len(records),
            deals_synced=0,
            contacts_synced=0,
            errors=[],
        )
