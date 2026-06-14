"""arXiv open API for research/policy citations."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding

TIMEOUT = 10.0
NS = {"a": "http://www.w3.org/2005/Atom"}


def verify(*, query: str, **kwargs) -> VerificationFinding:
    q = query.replace(" ", "+")[:100]
    with client() as c:
        r = c.get(
            "http://export.arxiv.org/api/query",
            params={"search_query": f"all:{q}", "start": 0, "max_results": 2},
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)

    entries = root.findall("a:entry", NS)
    if not entries:
        return VerificationFinding(
            provider="arxiv",
            query=query,
            finding="No arXiv papers matched — topic may be non-academic.",
            support="neutral",
            confidence=0.3,
            ok=True,
        )

    titles = []
    for e in entries[:2]:
        t = e.find("a:title", NS)
        if t is not None and t.text:
            titles.append(t.text.strip().replace("\n", " ")[:120])

    return VerificationFinding(
        provider="arxiv",
        query=query,
        finding="arXiv refs: " + " | ".join(titles),
        support="neutral",
        confidence=0.5,
        ok=True,
    )
