"""Open Library search API."""

from __future__ import annotations

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding

TIMEOUT = 8.0


def verify(*, query: str, **kwargs) -> VerificationFinding:
    with client() as c:
        r = c.get(
            "https://openlibrary.org/search.json",
            params={"q": query[:80], "limit": 2, "fields": "title,author_name,first_publish_year"},
        )
        r.raise_for_status()
        docs = r.json().get("docs") or []

    if not docs:
        return VerificationFinding(
            provider="openlibrary",
            query=query,
            finding="Open Library: no books matched.",
            support="neutral",
            confidence=0.25,
            ok=True,
        )

    parts = []
    for d in docs[:2]:
        title = d.get("title", "?")
        author = (d.get("author_name") or ["?"])[0]
        year = d.get("first_publish_year", "?")
        parts.append(f"{title} by {author} ({year})")

    return VerificationFinding(
        provider="openlibrary",
        query=query,
        finding="Open Library: " + "; ".join(parts),
        support="neutral",
        confidence=0.5,
        ok=True,
    )
