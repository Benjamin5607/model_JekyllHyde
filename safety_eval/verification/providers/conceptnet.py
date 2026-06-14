"""ConceptNet open API."""

from __future__ import annotations

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding

TIMEOUT = 8.0


def verify(*, query: str, **kwargs) -> VerificationFinding:
    term = query.split()[0][:30].lower().replace(" ", "_")
    with client() as c:
        r = c.get(f"http://api.conceptnet.io/c/en/{term}")

    if r.status_code == 404:
        return VerificationFinding(
            provider="conceptnet",
            query=query,
            finding=f"No ConceptNet node for '{term}'.",
            support="neutral",
            confidence=0.25,
            ok=True,
        )
    r.raise_for_status()
    data = r.json()
    edges = data.get("edges") or []
    rels = []
    for e in edges[:4]:
        rel = e.get("rel", {}).get("label", "?")
        end = e.get("end", {}).get("label", "?")
        rels.append(f"{rel}->{end}")

    return VerificationFinding(
        provider="conceptnet",
        query=query,
        finding="ConceptNet: " + (", ".join(rels) if rels else "no relations"),
        support="neutral",
        confidence=0.5,
        ok=True,
    )
