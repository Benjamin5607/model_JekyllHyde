"""Pocket Quant capabilities for Jekyll & Hyde."""

from safety_eval.quant.analyzer import (
    QuantContext,
    build_quant_context,
    compare_snapshots,
    is_finance_query,
    scan_market_universe,
)
from safety_eval.quant.market import get_market_indices, market_weather_text
from safety_eval.quant.resolver import resolve_tickers
from safety_eval.quant.tickers import MARKET_SAMPLES, TICKER_NAMES

__all__ = [
    "QuantContext",
    "build_quant_context",
    "compare_snapshots",
    "is_finance_query",
    "scan_market_universe",
    "get_market_indices",
    "market_weather_text",
    "resolve_tickers",
    "MARKET_SAMPLES",
    "TICKER_NAMES",
]
