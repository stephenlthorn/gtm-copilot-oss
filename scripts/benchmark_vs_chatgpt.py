#!/usr/bin/env python3
"""
GTM Copilot vs ChatGPT — Pre-Call Brief Benchmark
====================================================
Usage:
    OPENAI_API_KEY=sk-... python3 scripts/benchmark_vs_chatgpt.py

    Or pass the key as --api-key:
    python3 scripts/benchmark_vs_chatgpt.py --api-key sk-...

    Output: benchmark_results_<timestamp>.md
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

COPILOT_BASE = "http://localhost:8000"
COPILOT_USER = os.environ.get("BENCHMARK_USER", "benchmark@yourcompany.com")
MODEL_VANILLA = "gpt-4o"
MODEL_JUDGE = "gpt-4o-mini"

# 3 prospects that represent TiDB's ICP: fintech, high-scale SaaS, gaming/ad-tech
TEST_PROSPECTS = [
    {
        "name": "Brex",
        "context": "B2B fintech startup, corporate credit cards and spend management for startups. ~$12B valuation. High-volume financial transaction data, real-time fraud detection.",
    },
    {
        "name": "Notion",
        "context": "Productivity SaaS, collaborative docs and databases. ~$10B valuation. Multi-tenant, rapid user growth, complex relational data at scale.",
    },
    {
        "name": "Riot Games",
        "context": "Online gaming company, League of Legends. High-concurrency player data, leaderboards, in-game economy, real-time analytics.",
    },
]

SCORING_CRITERIA = [
    "relevance",        # Is it specific to this company, not generic?
    "specificity",      # Does it cite actual company facts, signals, or tech stack details?
    "actionability",    # Can a rep act on this immediately? Are next steps concrete?
    "pain_point_fit",   # Does it map company pain to TiDB's actual strengths?
    "tidb_positioning", # Does it position TiDB correctly and competitively?
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict, headers: dict | None = None) -> dict:
    data = json.dumps(payload).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, method="POST", headers=h)
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


def _openai_chat(api_key: str, model: str, messages: list, temperature: float = 0.3) -> str:
    payload = {"model": model, "messages": messages, "temperature": temperature}
    result = _post(
        "https://api.openai.com/v1/chat/completions",
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return result["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# Brief generators
# ---------------------------------------------------------------------------

def run_copilot_brief(account: str, api_key: str) -> dict:
    """Call the local GTM Copilot /rep/account-brief endpoint."""
    try:
        result = _post(
            f"{COPILOT_BASE}/rep/account-brief",
            {"user": COPILOT_USER, "account": account},
            headers={"X-OpenAI-Token": api_key},
        )
        return {"ok": True, "data": result}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"ok": False, "error": f"HTTP {e.code}: {body[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


VANILLA_SYSTEM = (
    "You are a helpful sales research assistant. "
    "Produce a pre-call intelligence brief for an enterprise sales rep at a database company."
)

def run_chatgpt_brief(account: str, context: str, api_key: str) -> dict:
    """Call GPT-4o directly with no RAG, no persona, no TiDB-specific system prompt."""
    prompt = (
        f"Company: {account}\n"
        f"Context: {context}\n\n"
        "Generate a pre-call intelligence brief covering:\n"
        "1. Business summary and current situation\n"
        "2. Key business context and priorities\n"
        "3. Likely decision criteria for a database purchase\n"
        "4. Recommended assets or proof points to bring\n"
        "5. Suggested meeting agenda\n\n"
        "Be specific. Focus on what a database sales rep needs to know before the first call."
    )
    try:
        text = _openai_chat(
            api_key, MODEL_VANILLA,
            [{"role": "system", "content": VANILLA_SYSTEM},
             {"role": "user", "content": prompt}],
        )
        return {"ok": True, "data": text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = """\
You are an expert evaluator of B2B sales intelligence. Score two pre-call briefs — one from a specialized GTM copilot (System A) and one from a vanilla ChatGPT call (System B) — on five criteria.

For each criterion, output a JSON object:
{
  "criterion": "<name>",
  "score_a": <1-5>,
  "score_b": <1-5>,
  "winner": "A" | "B" | "tie",
  "reason": "<one sentence>",
  "gap": "<if B wins: specific thing A is missing or doing worse>"
}

Criteria and what 5 vs 1 means:
- relevance: 5=entirely about this specific company; 1=could be any company
- specificity: 5=cites actual company facts, tech stack, funding, signals; 1=all generic
- actionability: 5=concrete next steps a rep can execute today; 1=vague platitudes
- pain_point_fit: 5=maps company's exact pain to a database solution's strengths; 1=misses the pain or maps it wrong
- tidb_positioning: 5=positions TiDB precisely and competitively for this account; 1=no positioning or wrong positioning

Output a JSON array of 5 objects (one per criterion), then a "summary" object:
{
  "summary": {
    "wins_a": <count>,
    "wins_b": <count>,
    "ties": <count>,
    "overall_winner": "A" | "B" | "tie",
    "top_gaps_in_a": ["<gap 1>", "<gap 2>", "<gap 3>"],
    "prompt_recommendations": ["<specific prompt change 1>", "<specific prompt change 2>", "<specific prompt change 3>"]
  }
}
"""


def score_briefs(account: str, brief_a: str, brief_b: str, api_key: str) -> dict:
    """Use GPT-4o-mini as judge to score both briefs."""
    prompt = (
        f"Account being researched: {account}\n\n"
        f"=== SYSTEM A (GTM Copilot) ===\n{brief_a}\n\n"
        f"=== SYSTEM B (ChatGPT vanilla) ===\n{brief_b}\n\n"
        "Score both on all five criteria. Return valid JSON only."
    )
    try:
        raw = _openai_chat(
            api_key, MODEL_JUDGE,
            [{"role": "system", "content": JUDGE_SYSTEM},
             {"role": "user", "content": prompt}],
            temperature=0.1,
        )
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        return {"error": str(e), "raw": raw if "raw" in dir() else ""}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def copilot_brief_to_text(data: dict) -> str:
    lines = [f"**Summary:** {data.get('summary', '')}"]
    for section, label in [
        ("business_context", "Business Context"),
        ("decision_criteria", "Decision Criteria"),
        ("recommended_assets", "Recommended Assets"),
        ("next_meeting_agenda", "Meeting Agenda"),
    ]:
        items = data.get(section, [])
        if items:
            lines.append(f"\n**{label}:**")
            lines.extend(f"- {i}" for i in items)
    return "\n".join(lines)


def score_bar(score: int, total: int = 5) -> str:
    filled = "█" * score
    empty = "░" * (total - score)
    return f"{filled}{empty} {score}/{total}"


def render_criterion_row(c: dict) -> str:
    winner_mark = {"A": "🏆 A", "B": "🏆 B", "tie": "🤝 tie"}[c["winner"]]
    return (
        f"| {c['criterion']} | {score_bar(c['score_a'])} | {score_bar(c['score_b'])} | {winner_mark} | {c['reason']} |"
    )


# ---------------------------------------------------------------------------
# Report renderer
# ---------------------------------------------------------------------------

def render_report(results: list[dict]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# GTM Copilot vs ChatGPT — Pre-Call Brief Benchmark",
        f"*Generated: {ts}*",
        "",
        "**System A:** GTM Copilot (local API, RAG + TiDB persona + structured prompt)  ",
        "**System B:** ChatGPT GPT-4o (vanilla, no system context, no RAG)",
        "",
        "---",
        "",
    ]

    all_gaps = []
    all_prompt_recs = []
    overall_wins_a = 0
    overall_wins_b = 0

    for r in results:
        account = r["account"]
        lines.append(f"## {account}")
        lines.append("")

        if not r["copilot_ok"]:
            lines.append(f"> ⚠️ Copilot failed: {r['copilot_error']}")
        if not r["chatgpt_ok"]:
            lines.append(f"> ⚠️ ChatGPT failed: {r['chatgpt_error']}")
        if not r["copilot_ok"] or not r["chatgpt_ok"]:
            lines.append("")
            continue

        # Side-by-side briefs
        lines += [
            "<details>",
            "<summary>View full briefs</summary>",
            "",
            "### GTM Copilot brief",
            r["copilot_text"],
            "",
            "### ChatGPT brief",
            r["chatgpt_text"],
            "",
            "</details>",
            "",
        ]

        scores = r.get("scores")
        if not scores or "error" in scores:
            lines.append(f"> ⚠️ Scoring failed: {scores}")
            lines.append("")
            continue

        # Scores table
        lines += [
            "### Scores",
            "",
            "| Criterion | System A (Copilot) | System B (ChatGPT) | Winner | Reason |",
            "|---|---|---|---|---|",
        ]

        criteria_list = [s for s in scores if isinstance(s, dict) and "criterion" in s]
        for c in criteria_list:
            lines.append(render_criterion_row(c))
            if c["winner"] == "B" and c.get("gap"):
                all_gaps.append(f"**{account} / {c['criterion']}:** {c['gap']}")

        summary = scores.get("summary", {})
        if summary:
            wins_a = summary.get("wins_a", 0)
            wins_b = summary.get("wins_b", 0)
            overall_wins_a += wins_a
            overall_wins_b += wins_b
            winner = summary.get("overall_winner", "?")
            winner_label = {"A": "🏆 GTM Copilot", "B": "🏆 ChatGPT", "tie": "🤝 Tie"}.get(winner, winner)

            lines += [
                "",
                f"**Result: {winner_label}** ({wins_a}–{wins_b})",
                "",
            ]

            if summary.get("top_gaps_in_a"):
                lines.append("**Gaps in Copilot output:**")
                for g in summary["top_gaps_in_a"]:
                    lines.append(f"- {g}")
                lines.append("")

            if summary.get("prompt_recommendations"):
                all_prompt_recs.extend(summary["prompt_recommendations"])

        lines.append("---")
        lines.append("")

    # Overall summary
    lines += [
        "## Overall Summary",
        "",
        f"| | GTM Copilot | ChatGPT |",
        f"|---|---|---|",
        f"| Criterion wins | {overall_wins_a} | {overall_wins_b} |",
        "",
    ]

    if all_gaps:
        lines += [
            "### Identified Gaps in Copilot",
            "",
        ]
        for g in all_gaps:
            lines.append(f"- {g}")
        lines.append("")

    if all_prompt_recs:
        # Deduplicate while preserving order
        seen = set()
        unique_recs = []
        for r in all_prompt_recs:
            if r not in seen:
                seen.add(r)
                unique_recs.append(r)

        lines += [
            "### Targeted Prompt Optimizations",
            "",
            "These are concrete changes to `SYSTEM_PRE_CALL_INTEL` or `SYSTEM_REP_EXECUTION` "
            "to close the identified gaps:",
            "",
        ]
        for i, rec in enumerate(unique_recs, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GTM Copilot vs ChatGPT benchmark")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--output", help="Output file path (default: benchmark_results_<ts>.md)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No OpenAI API key. Set OPENAI_API_KEY or pass --api-key", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or f"benchmark_results_{ts}.md"

    print(f"Running benchmark against {len(TEST_PROSPECTS)} prospects...")
    print(f"Copilot API: {COPILOT_BASE}")
    print(f"Vanilla model: {MODEL_VANILLA} | Judge: {MODEL_JUDGE}")
    print()

    results = []

    for prospect in TEST_PROSPECTS:
        account = prospect["name"]
        context = prospect["context"]
        print(f"[{account}] Running copilot brief...", end=" ", flush=True)

        copilot_result = run_copilot_brief(account, api_key)
        print("✓" if copilot_result["ok"] else "✗")

        print(f"[{account}] Running ChatGPT brief...", end=" ", flush=True)
        chatgpt_result = run_chatgpt_brief(account, context, api_key)
        print("✓" if chatgpt_result["ok"] else "✗")

        copilot_text = ""
        chatgpt_text = ""

        if copilot_result["ok"]:
            copilot_text = copilot_brief_to_text(copilot_result["data"])
        if chatgpt_result["ok"]:
            chatgpt_text = chatgpt_result["data"]

        scores = {}
        if copilot_result["ok"] and chatgpt_result["ok"]:
            print(f"[{account}] Scoring...", end=" ", flush=True)
            scores = score_briefs(account, copilot_text, chatgpt_text, api_key)
            print("✓")

        results.append({
            "account": account,
            "copilot_ok": copilot_result["ok"],
            "copilot_error": copilot_result.get("error", ""),
            "copilot_text": copilot_text,
            "chatgpt_ok": chatgpt_result["ok"],
            "chatgpt_error": chatgpt_result.get("error", ""),
            "chatgpt_text": chatgpt_text,
            "scores": scores,
        })

        time.sleep(1)  # avoid rate limits

    print()
    print("Rendering report...")
    report = render_report(results)

    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()
