"""Wikidata open search API."""

from __future__ import annotations

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding


def verify(*, query: str, **kwargs) -> VerificationFinding:
    with client() as c:
        r = c.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": query[:80],
                "language": "en",
                "format": "json",
                "limit": 3,
            },
        )
        r.raise_for_status()
        data = r.json()

    hits = data.get("search") or []
    if not hits:
        return VerificationFinding(
            provider="wikidata",
            query=query,
            finding="No Wikidata entities matched.",
            support="neutral",
            confidence=0.25,
            ok=True,
        )

    labels = [f"{h.get('label', '?')} ({h.get('description', '')[:80]})" for h in hits[:3]]
    return VerificationFinding(
        provider="wikidata",
        query=query,
        finding="Wikidata: " + "; ".join(labels),
        support="neutral",
        confidence=0.55,
        ok=True,
        meta={"ids": [h.get("id") for h in hits[:3]]},
    )
