from __future__ import annotations

import json
import logging

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a retrieval query optimizer for a go-to-market intelligence system.
Its knowledge base contains: sales call transcripts (with speaker turns), competitive battlecards,
technical documentation, internal playbooks, and deal notes.

Given a user query and mode, return JSON with exactly these keys:
- "variants": array of 3 distinct rephrasings that maximize vector-search recall. Each should use
  different terminology, specificity, or perspective — imagine 3 different ways a sales rep,
  a solutions engineer, or a prospect might have phrased the same idea in a document.
- "hyde": a single short passage (3-5 sentences) written AS IF it were the ideal retrieved document
  excerpt that would perfectly answer the query. Write it in the voice/style of the source content
  (e.g. call transcript tone for call_assistant mode, doc/article tone for oracle mode).

Respond only with valid JSON. No explanation."""

_MODE_CONTEXT = {
    "oracle": (
        "Source content: sales call transcripts, competitive analyses, battlecards, "
        "technical docs, internal strategy docs. Write variants as declarative statements "
        "or questions a sales enablement doc would address. Write hyde as a document excerpt."
    ),
    "call_assistant": (
        "Source content: sales call transcripts with timestamped speaker turns. "
        "Write variants using call/meeting language: objections raised, pain points expressed, "
        "next steps discussed, pricing pushback, champion behavior. "
        "Write hyde as a realistic call transcript excerpt."
    ),
    "se": (
        "Source content: technical documentation, architecture guides, POC results, "
        "benchmarks, migration guides. Write variants using technical terminology. "
        "Write hyde as a technical doc excerpt."
    ),
    "rep": (
        "Source content: sales playbooks, call transcripts, email threads, deal notes, "
        "coaching notes. Write variants in sales execution language. "
        "Write hyde as a coaching note or deal update excerpt."
    ),
}


class QueryRewriter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        if self._client is None and self.settings.openai_api_key:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )
        return self._client

    def rewrite(self, query: str, mode: str) -> str:
        """Legacy single-string interface — returns the primary rewritten variant."""
        result = self.expand(query, mode)
        return result["variants"][0] if result["variants"] else query

    def expand(self, query: str, mode: str) -> dict:
        """Returns {"variants": [str, str, str], "hyde": str}.

        Falls back gracefully if LLM is unavailable.
        """
        client = self._get_client()
        if not client:
            return {"variants": [query], "hyde": query}

        mode_ctx = _MODE_CONTEXT.get(mode, _MODE_CONTEXT["oracle"])
        user_msg = f"Mode: {mode}\n{mode_ctx}\n\nQuery: {query}"

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=700,
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            variants = [v for v in (data.get("variants") or []) if isinstance(v, str) and v.strip()]
            hyde = (data.get("hyde") or "").strip()
            if not variants:
                variants = [query]
            return {"variants": variants[:3], "hyde": hyde or query}
        except Exception as exc:
            logger.warning("QueryRewriter.expand failed: %s", exc)
            return {"variants": [query], "hyde": query}
