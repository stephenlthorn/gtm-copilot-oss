from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 20.0
_BUILTWITH_API = "https://api.builtwith.com/v21/api.json"

_DATABASE_TECH_NAMES = {
    "mysql",
    "postgresql",
    "oracle",
    "mongodb",
    "redis",
    "cassandra",
    "tidb",
    "planetscale",
    "cockroachdb",
    "aurora",
    "rds",
    "dynamodb",
    "vitess",
}

_CLOUD_CATEGORY_KEYWORDS = {"cdn", "hosting", "paas", "iaas", "cloud"}
_FRAMEWORK_CATEGORY_KEYWORDS = {"framework", "javascript", "cms", "web server", "analytics"}


def _normalise_tech_name(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def _is_database(tech: dict) -> bool:
    name_norm = _normalise_tech_name(tech.get("Name", ""))
    if name_norm in _DATABASE_TECH_NAMES:
        return True
    # Some entries use alternate display names; check for substring matches.
    for db_name in _DATABASE_TECH_NAMES:
        if db_name in name_norm:
            return True
    return False


def _is_cloud(tech: dict) -> bool:
    categories = [c.lower() for c in (tech.get("Categories") or [])]
    name_norm = _normalise_tech_name(tech.get("Name", ""))
    return any(kw in cat for kw in _CLOUD_CATEGORY_KEYWORDS for cat in categories) or any(
        kw in name_norm for kw in {"cloudflare", "awscloudfront", "fastly", "akamai"}
    )


def _is_framework(tech: dict) -> bool:
    categories = [c.lower() for c in (tech.get("Categories") or [])]
    return any(kw in cat for kw in _FRAMEWORK_CATEGORY_KEYWORDS for cat in categories)


def _parse_technologies(data: dict) -> tuple[list[str], list[str], list[str], int]:
    """Parse the BuiltWith v21 response into (databases, cloud, frameworks, raw_count)."""
    databases: list[str] = []
    cloud: list[str] = []
    frameworks: list[str] = []
    raw_count = 0

    results = data.get("Results", [])
    for result in results:
        paths = result.get("Result", {}).get("Paths", [])
        for path in paths:
            technologies = path.get("Technologies", [])
            for tech in technologies:
                raw_count += 1
                name = tech.get("Name", "")
                if not name:
                    continue
                if _is_database(tech):
                    if name not in databases:
                        databases.append(name)
                elif _is_cloud(tech):
                    if name not in cloud:
                        cloud.append(name)
                elif _is_framework(tech):
                    if name not in frameworks:
                        frameworks.append(name)

    return databases, cloud, frameworks, raw_count


def fetch_builtwith_data(api_key: str, domain: str) -> dict:
    """Return technology-stack data for *domain* via the BuiltWith API.

    Args:
        api_key: BuiltWith API key (v21).
        domain: The domain to look up (e.g. ``"example.com"``).

    Returns a dict with keys: domain, databases, cloud, frameworks, raw_count.
    Never raises; errors are logged and a minimal empty result is returned.
    """
    empty: dict = {
        "domain": domain,
        "databases": [],
        "cloud": [],
        "frameworks": [],
        "raw_count": 0,
    }

    if not api_key:
        logger.warning("BuiltWith API key not provided; skipping lookup for %r", domain)
        return empty

    params = {"KEY": api_key, "LOOKUP": domain}

    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(_BUILTWITH_API, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "BuiltWith API request failed (status=%s) for %r: %s",
            exc.response.status_code,
            domain,
            exc.response.text[:200],
        )
        return empty
    except (httpx.HTTPError, ValueError):
        logger.warning("BuiltWith request error for %r", domain, exc_info=True)
        return empty

    # API-level errors are surfaced in the Errors list.
    errors = data.get("Errors", [])
    if errors:
        logger.warning("BuiltWith returned errors for %r: %s", domain, errors)
        return empty

    databases, cloud, frameworks, raw_count = _parse_technologies(data)

    return {
        "domain": domain,
        "databases": databases,
        "cloud": cloud,
        "frameworks": frameworks,
        "raw_count": raw_count,
    }
