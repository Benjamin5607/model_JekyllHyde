"""Human-readable KRW / financial formatting for LLM prompts."""

from __future__ import annotations

DISPLAY_KO: dict[str, str] = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "035420.KS": "NAVER",
    "035720.KS": "카카오",
}


def ko_display_name(ticker: str, fallback: str) -> str:
    return DISPLAY_KO.get(ticker, fallback)


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
