from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 20.0
_HN_ALGOLIA_SEARCH = "http://hn.algolia.com/api/v1/search"
_MAX_RESULTS_PER_QUERY = 5
_SECONDS_PER_DAY = 86_400


def _timestamp_days_ago(days: int) -> int:
    return int(time.time()) - days * _SECONDS_PER_DAY


def _parse_hit(hit: dict) -> dict:
    return {
        "title": hit.get("title") or hit.get("story_title") or "",
        "url": hit.get("url") or hit.get("story_url") or "",
        "points": hit.get("points") or 0,
        "num_comments": hit.get("num_comments") or 0,
        "created_at": hit.get("created_at") or "",
        "author": hit.get("author") or "",
        "objectID": hit.get("objectID") or "",
    }


def _fetch_query(query: str, since_ts: int, client: httpx.Client) -> list[dict]:
    """Execute a single Algolia search and return parsed hits (up to _MAX_RESULTS_PER_QUERY)."""
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{since_ts}",
        "hitsPerPage": str(_MAX_RESULTS_PER_QUERY),
    }
    try:
        resp = client.get(_HN_ALGOLIA_SEARCH, params=params)
        resp.raise_for_status()
        return [_parse_hit(h) for h in resp.json().get("hits", [])]
    except (httpx.HTTPError, ValueError):
        logger.warning("HN Algolia search failed for query %r", query, exc_info=True)
        return []


def search_company(company_name: str, days_back: int = 365) -> dict:
    """Search Hacker News for stories mentioning *company_name* and related tech terms.

    Executes three searches:
    - ``"{company_name}" database``
    - ``"{company_name}" mysql``
    - ``"{company_name}" infrastructure``

    Returns the top 5 results per query, deduped by objectID, with a
    ``total_found`` count reflecting the deduplicated total.

    Args:
        company_name: The company to search for.
        days_back: How far back to search (default: 365 days).

    Returns a dict with keys: hits (list of result dicts), total_found (int).
    Never raises; errors are logged and an empty result is returned.
    """
    since_ts = _timestamp_days_ago(days_back)

    queries = [
        f'"{company_name}" database',
        f'"{company_name}" mysql',
        f'"{company_name}" infrastructure',
    ]

    seen_ids: set[str] = set()
    deduplicated_hits: list[dict] = []

    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT, follow_redirects=True) as client:
            for query in queries:
                hits = _fetch_query(query, since_ts, client)
                for hit in hits:
                    oid = hit["objectID"]
                    if oid and oid not in seen_ids:
                        seen_ids.add(oid)
                        # Remove internal dedup key from the public result.
                        public_hit = {k: v for k, v in hit.items() if k != "objectID"}
                        deduplicated_hits.append(public_hit)
    except Exception:
        logger.exception("Unexpected error searching HN for %r", company_name)
        return {"hits": [], "total_found": 0}

    return {
        "hits": deduplicated_hits,
        "total_found": len(deduplicated_hits),
    }
