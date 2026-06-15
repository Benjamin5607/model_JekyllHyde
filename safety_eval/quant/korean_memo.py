"""Korean memo helpers (display names, formatting). LLM reports use quant/harness.py."""

from __future__ import annotations

from safety_eval.quant.analyzer import QuantContext
from safety_eval.quant.formatting import fmt_krw_large, fmt_krw_price, fmt_quarter_row
from safety_eval.quant.market import analysis_anchor
from safety_eval.quant.research import CompanyDossier, ResearchHit, build_company_dossier

DISPLAY_KO: dict[str, str] = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "035420.KS": "NAVER",
    "035720.KS": "카카오",
}

_CATEGORY_KO = {
    "earnings": "실적",
    "strategy": "전략/투자",
    "risk": "리스크",
    "analyst": "애널리스트",
    "sector": "섹터",
    "news": "뉴스",
}


def _ko_name(ticker: str, fallback: str) -> str:
    return DISPLAY_KO.get(ticker, fallback)


def _headline_section(dossier: CompanyDossier, limit: int = 6) -> list[str]:
    lines: list[str] = []
    if not dossier.hits:
        lines.append("- 최근 헤드라인 수집 실패 (Yahoo Finance)")
        return lines
    for i, h in enumerate(dossier.hits[:limit], 1):
        cat = _CATEGORY_KO.get(h.category, h.category)
        lines.append(f"{i}. **[{h.date}] [{cat}] {h.title}**")
        if h.snippet and h.snippet != h.title:
            lines.append(f"   - 요약: {h.snippet}")
    return lines


def _peer_table(snapshots) -> str:
    header = "| 회사 | 티커 | 주가 | 일간 등락 | PER | PBR | ROE | 매출 추세 |\n|------|------|------|-----------|-----|-----|-----|-----------|"
    rows = []
    for s in snapshots:
        name = _ko_name(s.ticker, s.name)
        chg = f"{s.change_pct:+.2f}%" if s.change_pct is not None else "N/A"
        rows.append(
            f"| {name} | `{s.ticker}` | {fmt_krw_price(s.price)} | {chg} | "
            f"{s.fundamentals.per} | {s.fundamentals.pbr} | {s.fundamentals.roe} | {s.trend} |"
        )
    return header + "\n" + "\n".join(rows)


def _financial_detail(s) -> list[str]:
    name = _ko_name(s.ticker, s.name)
    lines = [f"### {name} (`{s.ticker}`)"]
    chg = f"{s.change_pct:+.2f}%" if s.change_pct is not None else "N/A"
    lines.append(f"- **주가:** {fmt_krw_price(s.price)} ({chg}, 출처: {s.source})")
    lines.append(f"- **밸류에이션:** PER {s.fundamentals.per} / PBR {s.fundamentals.pbr} / ROE {s.fundamentals.roe}")
    if s.fundamentals.quarterly_rows:
        lines.append("- **분기 실적 (Yahoo Finance):**")
        for row in s.fundamentals.quarterly_rows[:4]:
            lines.append(f"  - {fmt_quarter_row(row)}")
    else:
        lines.append("- **분기 실적:** 데이터 없음")
    return lines


_PROFILE_KO: dict[str, str] = {
    "005930.KS": "디바이스·메모리·파운드리 등 사업 다각화 구조",
    "000660.KS": "DRAM·NAND·HBM 중심의 메모리 집중 구조",
}


def _exec_summary(snapshots, anchor: dict) -> str:
    if len(snapshots) >= 2:
        parts = []
        for s in snapshots[:2]:
            n = _ko_name(s.ticker, s.name)
            prof = _PROFILE_KO.get(s.ticker, s.trend)
            parts.append(f"{n}({fmt_krw_price(s.price)}, {prof})")
        return (
            f"{anchor['quarter_label_ko']} 기준, {'와 '.join(parts[:2])}를 비교합니다. "
            f"AI/HBM 수요 사이클에 대한 민감도·밸류에이션이 상이합니다. "
            f"아래 수치·헤드라인은 Yahoo Finance/FDR 실시간 수집 데이터이며, 매수·매도 권유가 아닙니다."
        )
    s = snapshots[0]
    n = _ko_name(s.ticker, s.name)
    return (
        f"{anchor['quarter_label_ko']} 기준 {n}({fmt_krw_price(s.price)}) 분석 메모입니다. "
        f"매출 추세: {s.trend}. 투자 권유가 아닌 교육 목적 리포트입니다."
    )


def _scenarios_ko(snapshots) -> list[str]:
    lines: list[str] = []
    for s in snapshots:
        name = _ko_name(s.ticker, s.name)
        chg = s.change_pct or 0
        lines.append(f"**{name}**")
        if chg > 2:
            lines.append("- **낙관:** AI 메모리/HBM 수요 지속 시 실적·밸류에이션 동반 개선 가능 (불확실)")
            lines.append("- **기본:** 최근 모멘텀·실적 추세 유지, 다음 분기 실적이 관건")
            lines.append("- **비관:** 메모리 가격 반전·수요 둔화 시 변동성 확대 (불확실)")
        else:
            lines.append("- **낙관:** 업황 회복·신제품(HBM 등) 믹스 개선 시 반등 여지")
            lines.append("- **기본:** 현 추세·밸류에이션 레인지 유지")
            lines.append("- **비관:** 경기 둔화·재고 조정 시 추가 조정 가능")
    return lines


def render_korean_equity_memo(ctx: QuantContext) -> str:
    """Build a full Korean memo from live API data — no LLM hallucination on numbers."""
    anchor = analysis_anchor()
    snapshots = [s for s in ctx.snapshots if s.price is not None or s.fundamentals.quarterly_rows]
    if not snapshots:
        return "## 데이터 부족\n실시간 시세·실적을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요."

    dossiers = ctx.dossiers
    if not dossiers:
        dossiers = [build_company_dossier(s.name, s.ticker, deep=True) for s in snapshots]

    if len(snapshots) >= 2:
        title = (
            f"{_ko_name(snapshots[1].ticker, snapshots[1].name)} vs "
            f"{_ko_name(snapshots[0].ticker, snapshots[0].name)} 투자 메모"
        )
        # Prefer 삼성 first when both present
        for s in snapshots:
            if s.ticker == "005930.KS":
                other = next(x for x in snapshots if x.ticker != s.ticker)
                title = f"{_ko_name(s.ticker, s.name)} vs {_ko_name(other.ticker, other.name)} 투자 메모"
                break
    else:
        title = f"{_ko_name(snapshots[0].ticker, snapshots[0].name)} 투자 메모"

    parts: list[str] = [
        f"# {title}",
        f"**데이터 기준일:** {anchor['date']} | **당분기:** {anchor['quarter_label_ko']}",
        "",
        "## 핵심 요약",
        _exec_summary(snapshots, anchor),
        "",
        "## 동종 비교 스냅샷",
        _peer_table(snapshots),
        "",
        "## 재무 상세",
    ]
    for s in snapshots:
        parts.extend(_financial_detail(s))
        parts.append("")

    parts.append("## 최근 주요 이슈 (Yahoo Finance / 웹 수집)")
    parts.append("*영문 헤드라인을 수집했으며, 본문은 한국어로 정리했습니다.*")
    parts.append("")
    for d in dossiers:
        parts.append(f"### {_ko_name(d.ticker, d.name)}")
        parts.extend(_headline_section(d))
        parts.append("")

    parts.extend([
        "## 섹터 맥락",
        ctx.market_weather,
        "",
        "- AI 데이터센터·HBM 수요가 메모리 업황의 핵심 변수로 부각 중",
        "- 글로벌 금리·환율·지정학 리스크는 반도체 밸류에이션에 영향",
        "",
        "## 시나리오 (가정, 투자 권유 아님)",
    ])
    parts.extend(_scenarios_ko(snapshots))
    parts.extend([
        "",
        "## 관점 변경 요인",
        "- 분기 실적(영업이익·HBM 비중) 서프라이즈/미스",
        "- 메모리 가격(DRAM/NAND) 사이클 전환",
        "- 미·중 수출 규제, capex 계획 변경",
        "",
        "## 면책 조항",
        "**본 메모는 교육 목적이며 투자 권유·매수·매도 추천이 아닙니다.** "
        "실제 투자 결정은 공시·증권사 리포트·전문가 상담을 병행하세요.",
        "",
        f"*수집: Yahoo Finance, FinanceDataReader | 생성: Jekyll & Hyde {anchor['date']}*",
    ])
    return "\n".join(parts)
