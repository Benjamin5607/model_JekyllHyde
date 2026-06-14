"""DuckDuckGo instant answer API (no key)."""

from __future__ import annotations

import httpx

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding


def verify(*, query: str, **kwargs) -> VerificationFinding:
    with client() as c:
        r = c.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1, "skip_disambig": 1},
        )
        r.raise_for_status()
        data = r.json()

    abstract = (data.get("AbstractText") or "").strip()
    answer = (data.get("Answer") or "").strip()
    related = data.get("RelatedTopics") or []

    parts = []
    if answer:
        parts.append(f"Answer: {answer}")
    if abstract:
        parts.append(f"Abstract: {abstract[:300]}")
    if not parts and related:
        first = related[0]
        if isinstance(first, dict) and first.get("Text"):
            parts.append(f"Related: {first['Text'][:200]}")

    if not parts:
        return VerificationFinding(
            provider="duckduckgo",
            query=query,
            finding="No instant answer — query may be too niche for DDG.",
            support="neutral",
            confidence=0.25,
            ok=True,
        )

    return VerificationFinding(
        provider="duckduckgo",
        query=query,
        finding=" | ".join(parts)[:400],
        support="neutral",
        confidence=0.6,
        ok=True,
        meta={"heading": data.get("Heading", "")},
    )
