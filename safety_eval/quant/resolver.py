"""Resolve company names / queries to tickers."""

from __future__ import annotations

import re

from safety_eval.quant.tickers import NAME_TO_TICKER, TICKER_NAMES

# Short uppercase tokens that are company-name fragments, not tickers.
_TICKER_BLOCKLIST = frozenset({
    "SK", "AI", "IT", "US", "UK", "EU", "VS", "PE", "PB", "ROE", "EPS", "ETF", "IPO",
    "CEO", "CFO", "GDP", "USD", "KRW", "Q1", "Q2", "Q3", "Q4",
})


def _is_valid_ticker_symbol(symbol: str) -> bool:
    if symbol in TICKER_NAMES:
        return True
    if re.fullmatch(r"\d{6}\.[A-Z]{2}", symbol):
        return True
    if "." in symbol and len(symbol) >= 4:
        return True
    return len(symbol) >= 2 and symbol not in _TICKER_BLOCKLIST and symbol.isalpha()


def resolve_tickers(query: str, max_targets: int = 3) -> list[dict[str, str]]:
    q = query.strip()
    lower = q.lower()
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    # Name aliases first (longest match wins — avoids SK vs SK Hynix)
    aliases = sorted(NAME_TO_TICKER.items(), key=lambda kv: len(kv[0]), reverse=True)
    for alias, ticker in aliases:
        if alias in lower and ticker not in seen:
            name = TICKER_NAMES.get(ticker, alias.title())
            found.append({"name": name, "ticker": ticker, "eng_key": f"{name} stock", "native_key": f"{name} 주가"})
            seen.add(ticker)

    # Reverse lookup display names
    for ticker, name in TICKER_NAMES.items():
        if name.lower() in lower and ticker not in seen:
            found.append({"name": name, "ticker": ticker, "eng_key": f"{name} stock", "native_key": f"{name} 뉴스"})
            seen.add(ticker)

    # Explicit tickers in query (AAPL, 005930.KS, etc.) — only known/valid symbols
    for match in re.findall(r"\b([A-Z0-9]{1,6}(?:\.[A-Z]{1,3})?)\b", q):
        if match in seen or not _is_valid_ticker_symbol(match):
            continue
        name = TICKER_NAMES.get(match, match)
        found.append({"name": name, "ticker": match, "eng_key": f"{name} stock", "native_key": f"{name} 주가"})
        seen.add(match)

    return found[:max_targets]
