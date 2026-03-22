from __future__ import annotations

PRE_CALL_SOURCES = {
    "name": "Pre-Call Intelligence",
    "sources": [
        {"name": "LinkedIn Contact", "search": "{contact} {company} site:linkedin.com", "priority": 1, "why": "Verify current title, tenure, and previous employers — only use what search returns, never infer"},
        {"name": "Competitive DB Moves", "search": "{company} YugabyteDB OR CockroachDB OR PlanetScale OR Spanner OR AlloyDB OR distributed SQL 2024 OR 2025 OR 2026", "priority": 1, "why": "CRITICAL: detect active competitor evaluation or selection — completely changes call strategy if found"},
        {"name": "DB Migration News", "search": "{company} database migration infrastructure modernization 2024 OR 2025 OR 2026", "priority": 1, "why": "Active migration = live budget + confirmed pain + potential displacement opportunity"},
        {"name": "Recent Financials", "search": "{company} revenue annual report earnings 2025 OR 2026", "priority": 1, "why": "Current ARR/revenue for deal sizing and urgency — must be from search, not training data"},
        {"name": "SEC EDGAR", "search": "site:sec.gov {company} 10-K OR 10-Q", "priority": 1, "why": "Technology strategy, infrastructure spend, vendor mentions in official filings"},
        {"name": "Earnings Transcripts", "search": "{company} earnings call transcript 2025 OR 2026", "priority": 1, "why": "CTO/CFO discuss infrastructure modernization plans in their own words"},
        {"name": "DB Tech Stack", "search": "{company} MySQL OR PostgreSQL OR Aurora OR Vitess OR sharding database engineering", "priority": 1, "why": "Identify primary DB and scaling approach — Vitess/Aurora = direct TiDB pain signal"},
        {"name": "BuiltWith/StackShare", "search": "{company} technology stack site:stackshare.io OR site:builtwith.com", "priority": 2, "why": "Broad stack signal including MySQL, PostgreSQL, Oracle usage"},
        {"name": "GitHub", "search": "site:github.com {company} mysql OR database OR migration OR sharding", "priority": 2, "why": "Sharding code, Vitess/ProxySQL repos = scale pain signals"},
        {"name": "Engineering Blog DB", "search": "{company} engineering blog database OR MySQL OR distributed 2024 OR 2025 OR 2026", "priority": 2, "why": "First-party accounts of DB challenges and scale decisions"},
        {"name": "Job Postings", "search": "{company} hiring database engineer OR DBA OR platform engineer 2025", "priority": 2, "why": "Hiring for DB roles = active infrastructure investment signal"},
        {"name": "Crunchbase", "search": "site:crunchbase.com {company}", "priority": 2, "why": "Funding stage, investors, acquisition history for deal context"},
        {"name": "Reddit/HN", "search": "site:reddit.com OR site:news.ycombinator.com {company} database OR infrastructure", "priority": 3, "why": "Unfiltered developer sentiment about DB pain"},
    ],
}

POST_CALL_SOURCES = {
    "name": "Post-Call Coaching",
    "sources": [
        {"name": "MEDDPICC Validation", "type": "framework", "priority": 1, "why": "Validate: Metrics, Economic Buyer, Decision Criteria/Process, Paper Process, Implicate Pain, Champion, Competition"},
        {"name": "Competitor Battlecards", "search": "{competitor} vs TiDB OR distributed SQL comparison", "priority": 1, "why": "Counter competitor claims from the call"},
        {"name": "Technical Verification", "search": "{technical_claim} benchmark OR documentation", "priority": 2, "why": "Verify technical claims made during the call"},
        {"name": "Deal Qualification", "type": "framework", "priority": 1, "why": "Score: Champion strength, access to EB, compelling event, decision timeline"},
    ],
}

POC_TECHNICAL_SOURCES = {
    "name": "POC & Technical Evaluation",
    "sources": [
        {"name": "TiDB Docs", "search": "site:docs.pingcap.com {topic}", "priority": 1, "why": "Official documentation for architecture, compatibility, migration guides"},
        {"name": "DB-Engines", "search": "site:db-engines.com {database} vs TiDB", "priority": 2, "why": "Ranking, trend data, system properties comparison"},
        {"name": "Jepsen", "search": "site:jepsen.io tidb", "priority": 2, "why": "Consistency/correctness test results — strong proof point"},
        {"name": "GitHub pingcap", "search": "site:github.com/pingcap {topic}", "priority": 1, "why": "Source code, issues, release notes, community activity"},
        {"name": "PingCAP Blog", "search": "site:pingcap.com/blog {topic}", "priority": 1, "why": "Case studies, benchmarks, migration stories"},
        {"name": "Percona Community", "search": "site:percona.com {topic} MySQL", "priority": 3, "why": "MySQL ecosystem context — Percona users are TiDB prospects"},
        {"name": "Stack Overflow", "search": "site:stackoverflow.com tidb OR distributed SQL {topic}", "priority": 2, "why": "Developer Q&A, common issues, community solutions"},
        {"name": "Competitor Docs", "search": "site:cockroachlabs.com OR site:planetscale.com OR docs.aws.amazon.com/AmazonRDS {topic}", "priority": 3, "why": "Comparison selling — understand competitor capabilities"},
    ],
}

DEFAULT_SOURCE_PROFILES = {
    "pre_call": PRE_CALL_SOURCES,
    "post_call": POST_CALL_SOURCES,
    "poc_technical": POC_TECHNICAL_SOURCES,
}

MODE_TO_PROFILE = {
    "oracle": "pre_call",
    "call_assistant": "post_call",
    "se": "poc_technical",
    "rep": "pre_call",
    "marketing": "pre_call",
}


def get_source_profile(mode: str, custom_profiles: dict | None = None) -> dict | None:
    profile_key = MODE_TO_PROFILE.get(mode)
    if not profile_key:
        return None
    if custom_profiles and profile_key in custom_profiles:
        return custom_profiles[profile_key]
    return DEFAULT_SOURCE_PROFILES.get(profile_key)


def format_source_instructions(profile: dict | None) -> str:
    if not profile or not profile.get("sources"):
        return ""
    lines = [
        f"=== WEB SEARCH INSTRUCTIONS FOR {profile['name'].upper()} ===",
        "Execute searches in this priority order. Use the exact search patterns provided.",
        "For each HIGH priority source, you MUST attempt a search before answering.",
        "",
    ]
    for source in sorted(profile["sources"], key=lambda s: s.get("priority", 99)):
        if not source.get("search"):
            continue
        priority_label = {1: "HIGH ⚡ (required)", 2: "MEDIUM", 3: "LOW (if time permits)"}.get(source.get("priority", 3), "LOW")
        lines.append(f"[{priority_label}] {source['name']}")
        lines.append(f"  Search: {source['search']}")
        if source.get("why"):
            lines.append(f"  Why: {source['why']}")
    return "\n".join(lines)
