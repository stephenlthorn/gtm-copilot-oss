from __future__ import annotations

import re


_STOP_WORDS = frozenset({
    "what", "where", "when", "which", "who", "why", "how",
    "are", "the", "for", "and", "with", "from", "into",
    "this", "that", "your", "ours", "their", "about",
    "should", "could", "would", "please", "show", "tell", "give",
})


def contains_term(haystack: str, term: str) -> bool:
    pattern = rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])"
    return re.search(pattern, haystack) is not None


def query_terms(query: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9._-]{1,}", query.lower())
    seen: set[str] = set()
    terms: list[str] = []
    for token in tokens:
        if len(token) < 3 or token in _STOP_WORDS:
            continue
        if token not in seen:
            terms.append(token)
            seen.add(token)
    return terms


def lexical_overlap(text: str, query: str) -> float:
    terms = query_terms(query)
    if not terms:
        return 0.0
    lowered = text.lower()
    matches = sum(1 for term in terms if contains_term(lowered, term))
    return matches / max(1, len(terms))
