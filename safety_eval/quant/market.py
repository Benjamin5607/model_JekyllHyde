"""Market data collection — yfinance, FinanceDataReader, DuckDuckGo news."""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from safety_eval.quant.tickers import MARKET_INDICES, TICKER_NAMES


@dataclass
class Fundamentals:
    per: str = "N/A"
    pbr: str = "N/A"
    roe: str = "N/A"
    quarterly_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StockSnapshot:
    ticker: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    source: str = "N/A"
    fundamentals: Fundamentals = field(default_factory=Fundamentals)
    news: str = ""
    trend: str = "unknown"
    data_as_of: str = ""


def analysis_anchor() -> dict[str, str]:
    now = datetime.datetime.now(datetime.UTC).astimezone()
    month = now.month
    quarter = (month - 1) // 3 + 1
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M %Z"),
        "year": str(now.year),
        "quarter": f"Q{quarter} {now.year}",
        "quarter_label_ko": f"{now.year}년 {quarter}분기",
    }


def _format_period(col: Any) -> str:
    if hasattr(col, "strftime"):
        dt = col.to_pydatetime() if hasattr(col, "to_pydatetime") else col
        if isinstance(dt, datetime.datetime):
            q = (dt.month - 1) // 3 + 1
            return f"Q{q} {dt.year}"
        return col.strftime("%Y-%m")
    text = str(col)
    m = re.match(r"(\d{4})-(\d{2})", text)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        q = (month - 1) // 3 + 1
        return f"Q{q} {year}"
    return text


def _fdr_symbol(ticker: str) -> str:
    if ".VN" in ticker:
        return ticker.split(".")[0]
    if ".JK" in ticker:
        return f"IDX:{ticker.split('.')[0]}"
    if ".KS" in ticker or ".KQ" in ticker:
        return ticker.split(".")[0]
    if ".T" in ticker:
        return f"TSE:{ticker.split('.')[0]}"
    return ticker


def get_market_indices() -> dict[str, tuple[float, float]]:
    try:
        import yfinance as yf
    except ImportError:
        return {}

    data: dict[str, tuple[float, float]] = {}
    try:
        df = yf.download(list(MARKET_INDICES.values()), period="5d", progress=False)["Close"]
        for name, sym in MARKET_INDICES.items():
            if sym not in df.columns:
                continue
            series = df[sym].dropna()
            if len(series) >= 2:
                curr, prev = float(series.iloc[-1]), float(series.iloc[-2])
                data[name] = (curr, ((curr - prev) / prev) * 100)
    except Exception:
        pass
    return data


def get_fundamentals(ticker: str) -> Fundamentals:
    fund = Fundamentals()
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        per = info.get("trailingPE")
        pbr = info.get("priceToBook")
        roe = info.get("returnOnEquity")
        fund.per = f"{per:.2f}" if per else "N/A"
        fund.pbr = f"{pbr:.2f}" if pbr else "N/A"
        fund.roe = f"{roe * 100:.2f}%" if roe else "N/A"

        q_fin = yf.Ticker(ticker).quarterly_financials
        if q_fin is not None and not q_fin.empty:
            rows = [r for r in ("Total Revenue", "Operating Revenue", "Net Income") if r in q_fin.index]
            for col in q_fin.columns[:4]:
                entry: dict[str, Any] = {"period": _format_period(col)}
                for row in rows:
                    val = q_fin.loc[row, col]
                    entry[row] = float(val) if val == val else None  # noqa: PLR0124
                fund.quarterly_rows.append(entry)
    except Exception:
        pass
    return fund


def fetch_news(keyword: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return _fetch_news_httpx(keyword, max_results)

    lines: list[str] = []
    seen: set[str] = set()
    queries = [
        f"{keyword} earnings stock news",
        f"{keyword} 실적 주가",
        f"{keyword} quarterly results",
    ]
    try:
        with DDGS() as ddgs:
            for q in queries:
                results = list(ddgs.news(q, timelimit="m", max_results=max_results))
                if not results:
                    results = list(ddgs.text(q, timelimit="m", max_results=max_results))
                for r in results:
                    url = r.get("url") or r.get("href") or ""
                    if url in seen:
                        continue
                    title = r.get("title") or r.get("body", "")[:120]
                    lines.append(f"[{r.get('date', '?')}] {title}")
                    seen.add(url)
                if len(lines) >= max_results:
                    break
    except Exception:
        return _fetch_news_httpx(keyword, max_results)
    return "\n".join(lines[:max_results]) if lines else "No recent news found."


def _fetch_news_httpx(keyword: str, max_results: int) -> str:
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(
                "https://api.duckduckgo.com/",
                params={"q": f"{keyword} stock news", "format": "json", "no_html": 1},
            )
            data = r.json()
            abstract = data.get("AbstractText") or data.get("Answer") or ""
            return abstract[:500] if abstract else "No recent news found."
    except Exception:
        return "News unavailable."


def get_price_data(ticker: str, name: str) -> tuple[float | None, float | None, str]:
    try:
        import FinanceDataReader as fdr

        hist = fdr.DataReader(_fdr_symbol(ticker), start=(datetime.datetime.now() - datetime.timedelta(days=7)))
        if not hist.empty:
            curr, prev = float(hist["Close"].iloc[-1]), float(hist["Close"].iloc[-2])
            return curr, ((curr - prev) / prev) * 100, "FDR"
    except Exception:
        pass

    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        price = stock.fast_info.last_price
        prev = stock.fast_info.previous_close
        if price and prev:
            return float(price), ((float(price) - float(prev)) / float(prev)) * 100, "Yahoo"
    except Exception:
        pass

    return None, None, "Fail"


def _infer_trend(quarterly: list[dict[str, Any]]) -> str:
    rev_key = "Total Revenue"
    if len(quarterly) < 2:
        return "insufficient data"
    vals = [q.get(rev_key) for q in quarterly if q.get(rev_key) is not None]
    if len(vals) < 2:
        return "insufficient data"
    if vals[0] > vals[-1] * 1.02:
        return "revenue improving (recent quarters)"
    if vals[0] < vals[-1] * 0.98:
        return "revenue declining (recent quarters)"
    return "revenue flat"


def get_stock_snapshot(ticker: str, name: str | None = None) -> StockSnapshot:
    anchor = analysis_anchor()
    display = name or TICKER_NAMES.get(ticker, ticker)
    price, chg, source = get_price_data(ticker, display)
    fund = get_fundamentals(ticker)
    news = fetch_news(f"{display} {ticker}")
    trend = _infer_trend(fund.quarterly_rows)
    return StockSnapshot(
        ticker=ticker,
        name=display,
        price=price,
        change_pct=chg,
        source=source,
        fundamentals=fund,
        news=news[:800],
        trend=trend,
        data_as_of=anchor["date"],
    )


def market_weather_text() -> str:
    anchor = analysis_anchor()
    indices = get_market_indices()
    header = f"Analysis as of {anchor['date']} ({anchor['quarter']}). Current quarter focus: {anchor['quarter_label_ko']}."
    if not indices:
        return f"{header} Market indices unavailable."
    parts = [f"{k}: {v[0]:,.0f} ({v[1]:+.2f}%)" for k, v in indices.items()]
    return f"{header}\nMarket weather: " + ", ".join(parts)
