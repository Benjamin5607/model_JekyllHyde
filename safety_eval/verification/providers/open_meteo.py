"""Open-Meteo geocoding (weather fact context)."""

from __future__ import annotations

from safety_eval.verification.http_client import client
from safety_eval.verification.base import VerificationFinding

TIMEOUT = 8.0


def verify(*, query: str, **kwargs) -> VerificationFinding:
    # Only run if query looks weather/location related
    lower = query.lower()
    if not any(w in lower for w in ("weather", "temperature", "rain", "climate", "날씨", "기온")):
        place = query.split(",")[0].split()[0][:40]
    else:
        place = query[:40]

    with client() as c:
        gr = c.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": place, "count": 1, "language": "en", "format": "json"},
        )
        gr.raise_for_status()
        results = gr.json().get("results") or []
        if not results:
            return VerificationFinding(
                provider="open_meteo",
                query=query,
                finding=f"Open-Meteo: no location match for '{place}'.",
                support="neutral",
                confidence=0.25,
                ok=True,
            )
        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        wr = c.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code"},
        )
        wr.raise_for_status()
        current = wr.json().get("current") or {}

    return VerificationFinding(
        provider="open_meteo",
        query=query,
        finding=(
            f"{loc.get('name')}, {loc.get('country', '')}: "
            f"temp {current.get('temperature_2m', '?')}°C, code {current.get('weather_code', '?')}"
        ),
        support="neutral",
        confidence=0.7,
        ok=True,
        meta={"lat": lat, "lon": lon},
    )
