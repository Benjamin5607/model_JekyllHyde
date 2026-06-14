"""Wikipedia open REST API."""

from __future__ import annotations

import httpx

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding

TIMEOUT = 8.0


def verify(*, query: str, **kwargs) -> VerificationFinding:
    with client() as c:
        r = c.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": query, "limit": 1, "format": "json"},
        )
        r.raise_for_status()
        titles = r.json()[1]
        if not titles:
            return VerificationFinding(
                provider="wikipedia",
                query=query,
                finding="No Wikipedia article found for context.",
                support="neutral",
                confidence=0.3,
                ok=True,
            )
        title = titles[0]
        sr = c.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}")
        if sr.status_code != 200:
            return VerificationFinding(
                provider="wikipedia",
                query=query,
                finding=f"Wikipedia article '{title}' found but summary unavailable.",
                support="neutral",
                confidence=0.4,
                ok=True,
            )
        data = sr.json()
        extract = data.get("extract", "")[:350]
        return VerificationFinding(
            provider="wikipedia",
            query=query,
            finding=f"Wikipedia '{title}': {extract}",
            support="neutral",
            confidence=0.65,
            ok=True,
            meta={"title": title, "url": data.get("content_urls", {}).get("desktop", {}).get("page", "")},
        )
