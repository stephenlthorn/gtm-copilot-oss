from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 20.0

_HEADERS = {
    "User-Agent": "GTM-Copilot research@gtmcopilot.com",
    "Accept": "application/json",
}

_DB_KEYWORDS = [
    "mysql",
    "postgresql",
    "postgres",
    "oracle database",
    "aurora",
    "tidb",
    "database migration",
    "cloud database",
    "data platform",
    "data infrastructure",
    "data warehouse",
    "snowflake",
    "data center",
    "cloud infrastructure",
    "technology infrastructure",
    "information technology",
    "cloud migration",
]


def _find_cik(company_name: str, client: httpx.Client) -> str | None:
    """Return zero-padded CIK for the first matching company via EDGAR company search."""
    try:
        resp = client.get(
            "https://www.sec.gov/cgi-bin/browse-edgar",
            params={
                "company": company_name,
                "CIK": "",
                "type": "10-K",
                "dateb": "",
                "owner": "include",
                "count": "5",
                "search_text": "",
                "action": "getcompany",
                "output": "atom",
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.warning("EDGAR company search failed for %r", company_name, exc_info=True)
        return None

    match = re.search(r"<cik>(\d+)</cik>", resp.text, re.IGNORECASE)
    if match:
        return match.group(1).zfill(10)
    url_match = re.search(r"CIK=(\d{1,10})", resp.text, re.IGNORECASE)
    if url_match:
        return url_match.group(1).zfill(10)
    return None


def _fetch_recent_filings(cik: str, client: httpx.Client) -> list[dict]:
    """Use data.sec.gov submissions API to get recent 10-K and 10-Q filings."""
    try:
        resp = client.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers={"User-Agent": "GTM-Copilot research@gtmcopilot.com"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("EDGAR submissions fetch failed for CIK %s", cik, exc_info=True)
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])

    filings: list[dict] = []
    for form, date, acc in zip(forms, dates, accessions):
        if form not in ("10-K", "10-Q"):
            continue
        # Build filing index URL
        acc_clean = acc.replace("-", "")
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}"
            f"/{acc_clean}/{acc}-index.htm"
        )
        filings.append({"form": form, "date": date, "url": filing_url, "accession": acc})
        if len(filings) >= 4:
            break

    return filings


def _fetch_filing_excerpts(cik: str, accession: str, client: httpx.Client) -> list[str]:
    """Fetch the main 10-K/10-Q document and extract sentences mentioning DB keywords."""
    acc_clean = accession.replace("-", "")
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{accession}-index.htm"
    )
    try:
        index_resp = client.get(index_url, headers={"User-Agent": "GTM-Copilot research@gtmcopilot.com"}, timeout=10)
        index_resp.raise_for_status()
    except httpx.HTTPError:
        return []

    # EDGAR uses inline XBRL viewer links: /ix?doc=/Archives/edgar/data/...
    doc_matches = re.findall(
        r'href="/ix\?doc=(/Archives/edgar/data/\d+/[^"]+\.htm)"',
        index_resp.text
    )
    if not doc_matches:
        # Fall back: direct links to main filing document
        doc_matches = re.findall(
            r'href="(/Archives/edgar/data/\d+/' + re.escape(acc_clean) + r'/[^"]+\.htm)"',
            index_resp.text
        )
        doc_matches = [m for m in doc_matches if "-index" not in m and "exhibit" not in m.lower()]

    if not doc_matches:
        return []

    doc_url = f"https://www.sec.gov{doc_matches[0]}"
    try:
        doc_resp = client.get(
            doc_url,
            headers={"User-Agent": "GTM-Copilot research@gtmcopilot.com"},
            timeout=15
        )
        doc_resp.raise_for_status()
    except httpx.HTTPError:
        return []

    # Strip HTML tags and extract text
    text = re.sub(r"<[^>]+>", " ", doc_resp.text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)

    # Extract sentences around DB keyword mentions
    return _extract_relevant_excerpts(text)


def _extract_relevant_excerpts(text: str) -> list[str]:
    """Return sentences containing database-related keywords."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    relevant: list[str] = []
    seen: set[str] = set()

    for sentence in sentences:
        lower = sentence.lower()
        if any(kw in lower for kw in _DB_KEYWORDS):
            cleaned = sentence.strip()
            if len(cleaned) > 30 and cleaned not in seen:
                seen.add(cleaned)
                relevant.append(cleaned[:300])
            if len(relevant) >= 8:
                break

    return relevant


def fetch_edgar_data(company_name: str) -> dict:
    """Return SEC EDGAR filing data and DB-related excerpts for *company_name*.

    Uses data.sec.gov/submissions API for reliable filing metadata.
    Fetches excerpts from the latest 10-K for DB keyword mentions.
    Never raises; errors are logged and partial results returned.
    """
    result: dict = {
        "company_name": company_name,
        "cik": None,
        "filings": [],
    }

    try:
        with httpx.Client(
            headers=_HEADERS, timeout=_DEFAULT_TIMEOUT, follow_redirects=True
        ) as client:
            cik = _find_cik(company_name, client)
            if not cik:
                result["error"] = "Company not found in EDGAR"
                return result

            result["cik"] = cik
            filings = _fetch_recent_filings(cik, client)

            # Try to get excerpts from the most recent 10-K only (avoid slow fetches)
            for filing in filings:
                excerpts: list[str] = []
                if filing["form"] == "10-K":
                    try:
                        excerpts = _fetch_filing_excerpts(cik, filing["accession"], client)
                    except Exception:
                        pass
                filing["relevant_excerpts"] = excerpts
                result["filings"].append(filing)

    except Exception:
        logger.exception("Unexpected error fetching EDGAR data for %r", company_name)

    return result
