"""Human-readable KRW / financial formatting for LLM prompts."""

from __future__ import annotations


def fmt_krw_price(amount: float | None) -> str:
    if amount is None:
        return "N/A"
    return f"{amount:,.0f} KRW"


def fmt_krw_large(amount: float | None) -> str:
    """Revenue / market cap style numbers."""
    if amount is None:
        return "N/A"
    abs_amt = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_amt >= 1e12:
        return f"{sign}{abs_amt / 1e12:.2f}조원"
    if abs_amt >= 1e8:
        return f"{sign}{abs_amt / 1e8:.0f}억원"
    return f"{sign}{amount:,.0f}원"


def fmt_quarter_row(row: dict) -> str:
    period = row.get("period", "?")
    rev = fmt_krw_large(row.get("Total Revenue"))
    ni = fmt_krw_large(row.get("Net Income"))
    return f"{period}: 매출 {rev}, 순이익 {ni}"
