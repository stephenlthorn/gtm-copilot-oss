from __future__ import annotations

PRE_CALL_SOURCES = {
    "name": "Pre-Call Intelligence",
    "sources": [
        {"name": "SEC EDGAR", "search": "site:sec.gov {company} 10-K OR 10-Q", "priority": 1, "why": "Technology strategy, infrastructure spend, vendor mentions"},
        {"name": "Earnings Transcripts", "search": "{company} earnings call transcript", "priority": 1, "why": "CTO/CFO discuss infrastructure modernization plans"},
        {"name": "LinkedIn", "search": "site:linkedin.com {company} {contact}", "priority": 1, "why": "Job titles, tenure, career history, connections"},
        {"name": "Crunchbase", "search": "site:crunchbase.com {company}", "priority": 2, "why": "Funding, investors, leadership, acquisition history"},
        {"name": "BuiltWith/StackShare", "search": "{company} technology stack OR site:stackshare.io {company}", "priority": 1, "why": "Identify MySQL, PostgreSQL, Oracle usage — migration opportunity"},
        {"name": "GitHub", "search": "site:github.com {company} mysql OR database OR migration", "priority": 2, "why": "Sharding code, Vitess/ProxySQL = scale pain signals"},
        {"name": "G2/TrustRadius", "search": "site:g2.com OR site:trustradius.com {company} database review", "priority": 2, "why": "Pain with incumbent DB vendors"},
        {"name": "Job Postings", "search": "{company} hiring database engineer OR DBA OR platform engineer", "priority": 2, "why": "Hiring for DB roles = infrastructure investment signal"},
        {"name": "Google News", "search": "{company} expansion OR funding OR acquisition OR migration", "priority": 2, "why": "Recent events affecting buying decisions"},
        {"name": "Reddit/HN", "search": "site:reddit.com OR site:news.ycombinator.com {company} database", "priority": 3, "why": "Unfiltered developer sentiment"},
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
