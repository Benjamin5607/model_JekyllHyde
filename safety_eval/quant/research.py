"""Deep equity research dossier — news, strategy, issues from open web search."""

from __future__ import annotations

import datetime
import re
import time
from dataclasses import dataclass, field
from typing import Any

from safety_eval.quant.market import analysis_anchor

TICKER_THEMES: dict[str, list[str]] = {
    "005930.KS": ["HBM AI memory", "파운드리 foundry", "갤럭시 Galaxy", "반도체 사이클"],
    "000660.KS": ["HBM AI memory", "DRAM NAND", "엔비디아 Nvidia supply", "메모리 capex"],
    "NVDA": ["AI datacenter", "HBM supply chain"],
    "AAPL": ["iPhone services", "AI strategy"],
}


@dataclass
class ResearchHit:
    title: str
    date: str
    snippet: str
    url: str
    query: str
    category: str = "news"


@dataclass
class CompanyDossier:
    name: str
    ticker: str
    profile: str = ""
    hits: list[ResearchHit] = field(default_factory=list)

    def to_block(self) -> str:
        lines = [f"### {self.name} ({self.ticker}) — RESEARCH DOSSIER"]
        if self.profile:
            lines.append(f"Company profile: {self.profile[:600]}")
        if not self.hits:
            lines.append("Recent headlines: none retrieved — state 'recent news unavailable'.")
            return "\n".join(lines)

        lines.append("Recent headlines & issues (cite these by title/date in your report):")
        for i, h in enumerate(self.hits[:12], 1):
            lines.append(
                f"{i}. [{h.category}] [{h.date}] {h.title}\n"
                f"   Snippet: {h.snippet[:320]}\n"
                f"   Source: {h.url or 'web search'}"
            )
        return "\n".join(lines)


_DOSSIER_CACHE: dict[str, tuple[float, CompanyDossier]] = {}
_CACHE_TTL_SEC = 900


def _cache_get(key: str) -> CompanyDossier | None:
    hit = _DOSSIER_CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL_SEC:
        return hit[1]
    return None


def _cache_put(key: str, dossier: CompanyDossier) -> None:
    _DOSSIER_CACHE[key] = (time.time(), dossier)


def fetch_yfinance_news(ticker: str, max_results: int = 8) -> list[ResearchHit]:
    hits: list[ResearchHit] = []
    try:
        import yfinance as yf

        raw = yf.Ticker(ticker).news or []
    except Exception:
        return hits

    for item in raw[:max_results]:
        content = item.get("content") if isinstance(item.get("content"), dict) else item
        if not isinstance(content, dict):
            continue
        title = (content.get("title") or "").strip()
        if not title:
            continue
        summary = (content.get("summary") or content.get("description") or "").strip()
        pub = content.get("pubDate") or content.get("displayTime") or "?"
        url = ""
        cu = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        if isinstance(cu, dict):
            url = cu.get("url") or ""
        hits.append(
            ResearchHit(
                title=title,
                date=str(pub)[:10],
                snippet=summary[:400] if summary else title,
                url=url,
                query=f"yfinance:{ticker}",
                category="news",
            )
        )
    return hits


def _search_ddgs(query: str, *, max_results: int = 4, timelimit: str = "m") -> list[dict[str, Any]]:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []
    rows: list[dict[str, Any]] = []
    try:
        with DDGS() as ddgs:
            news = list(ddgs.news(query, timelimit=timelimit, max_results=max_results))
            if news:
                return news
            return list(ddgs.text(query, timelimit=timelimit, max_results=max_results))
    except Exception:
        return rows


def _categorize_query(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ("capex", "plan", "strategy", "계획", "투자", "business")):
        return "strategy"
    if any(k in q for k in ("risk", "issue", "lawsuit", "regulat", "이슈", "리스크", "우려")):
        return "risk"
    if any(k in q for k in ("earnings", "실적", "quarter", "guidance", "전망")):
        return "earnings"
    if any(k in q for k in ("analyst", "목표", "리포트", "research")):
        return "analyst"
    return "news"


def _build_queries(name: str, ticker: str) -> list[tuple[str, str]]:
    anchor = analysis_anchor()
    year = anchor["year"]
    themes = TICKER_THEMES.get(ticker, ["earnings", "strategy"])
    queries: list[tuple[str, str]] = []

    ko = [
        (f"{name} {year} 실적 전망 earnings", "earnings"),
        (f"{name} 사업계획 투자 capex 전략", "strategy"),
        (f"{name} 이슈 리스크 논란", "risk"),
        (f"{name} 주가 뉴스 최신", "news"),
    ]
    en = [
        (f"{name} {ticker} earnings outlook {year}", "earnings"),
        (f"{name} business strategy investment plan", "strategy"),
        (f"{name} stock news issues risks", "risk"),
        (f"{name} analyst report semiconductor", "analyst"),
    ]
    queries.extend(ko + en)
    for theme in themes[:3]:
        queries.append((f"{name} {theme} {year}", "sector"))
    return queries


def get_company_profile(ticker: str, name: str) -> str:
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
    except Exception:
        return ""

    parts: list[str] = []
    sector = info.get("sector") or info.get("industry")
    if sector:
        parts.append(f"Sector: {sector}")
    summary = info.get("longBusinessSummary") or info.get("description")
    if summary:
        parts.append(summary[:500])
    cap = info.get("marketCap")
    if cap:
        parts.append(f"Market cap (Yahoo): {cap:,.0f}")
    emp = info.get("fullTimeEmployees")
    if emp:
        parts.append(f"Employees: {emp:,}")
    hi, lo = info.get("fiftyTwoWeekHigh"), info.get("fiftyTwoWeekLow")
    if hi and lo:
        parts.append(f"52w range: {lo:,.0f} – {hi:,.0f}")
    return " | ".join(parts) if parts else ""


def build_company_dossier(name: str, ticker: str, *, deep: bool = True) -> CompanyDossier:
    cache_key = f"{ticker}:{deep}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    dossier = CompanyDossier(name=name, ticker=ticker, profile=get_company_profile(ticker, name))
    seen: set[str] = set()

    # Primary: Yahoo Finance headlines (reliable, dated)
    for hit in fetch_yfinance_news(ticker, max_results=10 if deep else 5):
        key = hit.title
        if key not in seen:
            seen.add(key)
            dossier.hits.append(hit)

    queries = _build_queries(name, ticker)
    limit_per_query = 2 if deep else 1
    max_hits = 16 if deep else 8

    if len(dossier.hits) < 4:
        for query, default_cat in queries:
            if len(dossier.hits) >= max_hits:
                break
            for r in _search_ddgs(query, max_results=limit_per_query, timelimit="w"):
                url = (r.get("url") or r.get("href") or "").strip()
                title = (r.get("title") or "").strip()
                key = url or title
                if not title or key in seen:
                    continue
                seen.add(key)
                body = (r.get("body") or r.get("snippet") or r.get("description") or "").strip()
                body = re.sub(r"\s+", " ", body)
                dossier.hits.append(
                    ResearchHit(
                        title=title,
                        date=str(r.get("date") or r.get("published") or "?"),
                        snippet=body[:400] if body else title,
                        url=url,
                        query=query,
                        category=default_cat,
                    )
                )
                if len(dossier.hits) >= max_hits:
                    break
    _cache_put(cache_key, dossier)
    return dossier


def dossiers_to_research_block(dossiers: list[CompanyDossier]) -> str:
    if not dossiers:
        return ""
    anchor = analysis_anchor()
    lines = [
        "=== EQUITY RESEARCH DOSSIER (web search — cite headlines below, NOT generic filler) ===",
        f"Research gathered: {anchor['date']} | Focus: {anchor['quarter_label_ko']}",
    ]
    for d in dossiers:
        lines.append("")
        lines.append(d.to_block())
    return "\n".join(lines)


def build_research_block(names: list[tuple[str, str]], *, deep: bool = True) -> str:
    """names: list of (display_name, ticker)."""
    if not names:
        return ""
    anchor = analysis_anchor()
    lines = [
        "=== EQUITY RESEARCH DOSSIER (web search — cite headlines below, NOT generic filler) ===",
        f"Research gathered: {anchor['date']} | Focus: {anchor['quarter_label_ko']}",
        "RULE: Write like a sell-side analyst. Ground thesis, catalysts, and risks in SPECIFIC items below.",
        "Do NOT write vague lines like 'positive consumption' or 'competition may intensify' without naming the event.",
        "If dossier is thin, say what is missing — do not invent analyst reports.",
    ]
    for name, ticker in names:
        lines.append("")
        lines.append(build_company_dossier(name, ticker, deep=deep).to_block())
    lines.append(
        "\nREPORT STYLE: executive summary → business model & strategy → recent developments "
        "→ quarterly metrics (from LIVE DATA) → sector context → peer table → catalysts/risks "
        "→ scenarios → what changes the view → disclaimer."
    )
    return "\n".join(lines)
