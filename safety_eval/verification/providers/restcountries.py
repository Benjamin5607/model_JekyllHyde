"""REST Countries open API."""

from __future__ import annotations

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding

TIMEOUT = 8.0


def verify(*, query: str, **kwargs) -> VerificationFinding:
    token = query.split()[0][:40] if query.split() else query[:40]
    if len(token) < 3:
        return VerificationFinding(
            provider="restcountries",
            query=query,
            finding="Query too short for country lookup.",
            support="neutral",
            confidence=0.2,
            ok=True,
        )

    with client() as c:
        r = c.get(
            f"https://restcountries.com/v3.1/name/{token}",
            params={"fields": "name,capital,region,subregion,languages"},
        )

    if r.status_code == 404:
        return VerificationFinding(
            provider="restcountries",
            query=query,
            finding=f"No country match for '{token}'.",
            support="neutral",
            confidence=0.3,
            ok=True,
        )
    r.raise_for_status()
    data = r.json()[0]
    name = data.get("name", {}).get("common", token)
    capital = (data.get("capital") or ["?"])[0]
    region = data.get("region", "?")

    return VerificationFinding(
        provider="restcountries",
        query=query,
        finding=f"{name}: capital {capital}, region {region}",
        support="neutral",
        confidence=0.65,
        ok=True,
    )
