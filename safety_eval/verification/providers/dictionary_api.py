"""Free Dictionary API."""

from __future__ import annotations

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding

TIMEOUT = 8.0


def verify(*, query: str, **kwargs) -> VerificationFinding:
    word = query.split()[0][:40].lower()
    if not word.isalpha():
        return VerificationFinding(
            provider="dictionary",
            query=query,
            finding="No single English term extracted for dictionary lookup.",
            support="neutral",
            confidence=0.2,
            ok=True,
        )

    with client() as c:
        r = c.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")

    if r.status_code == 404:
        return VerificationFinding(
            provider="dictionary",
            query=query,
            finding=f"No dictionary entry for '{word}'.",
            support="neutral",
            confidence=0.3,
            ok=True,
        )
    r.raise_for_status()
    data = r.json()
    meanings = data[0].get("meanings", [])
    defs = []
    for m in meanings[:2]:
        for d in m.get("definitions", [])[:1]:
            defs.append(d.get("definition", "")[:150])

    return VerificationFinding(
        provider="dictionary",
        query=query,
        finding=f"'{word}': " + ("; ".join(defs) if defs else "definition unavailable"),
        support="neutral",
        confidence=0.55,
        ok=True,
    )
