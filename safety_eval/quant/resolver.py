"""Resolve company names / queries to tickers."""

from __future__ import annotations

import re

from safety_eval.quant.tickers import NAME_TO_TICKER, TICKER_NAMES


def resolve_tickers(query: str, max_targets: int = 3) -> list[dict[str, str]]:
    q = query.strip()
    lower = q.lower()
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    # Explicit tickers in query (AAPL, 005930.KS, etc.)
    for match in re.findall(r"\b([A-Z0-9]{1,6}(?:\.[A-Z]{1,3})?)\b", q):
        if match in TICKER_NAMES or "." in match or len(match) <= 6:
            if match not in seen:
                name = TICKER_NAMES.get(match, match)
                found.append({"name": name, "ticker": match, "eng_key": f"{name} stock", "native_key": f"{name} 주가"})
                seen.add(match)

    # Name aliases
    for alias, ticker in NAME_TO_TICKER.items():
        if alias in lower and ticker not in seen:
            name = TICKER_NAMES.get(ticker, alias.title())
            found.append({"name": name, "ticker": ticker, "eng_key": f"{name} stock", "native_key": f"{name} 실적"})
            seen.add(ticker)

    # Reverse lookup display names
    for ticker, name in TICKER_NAMES.items():
        if name.lower() in lower and ticker not in seen:
            found.append({"name": name, "ticker": ticker, "eng_key": f"{name} stock", "native_key": f"{name} 뉴스"})
            seen.add(ticker)

    return found[:max_targets]
