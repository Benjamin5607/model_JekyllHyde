"""
Multi-stage investment memo pipeline (2B-model aware).

Stage 1 [CODE]  collect context       — QuantContext (market + dossiers)
Stage 2 [CODE]  render facts block    — prices, quarters, headline list
Stage 3 [LLM×N] headline digest      — 2 Korean sentences per headline (~128 tok)
Stage 4 [LLM×M] section analysis     — one section per call (~200 tok)
Stage 5 [CODE]  assemble final memo   — facts + analysis + disclaimer
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from safety_eval.i18n.apac import language_generation_reminder
from safety_eval.quant.analyzer import QuantContext
from safety_eval.quant.formatting import fmt_krw_price, fmt_quarter_row
from safety_eval.quant.market import analysis_anchor
from safety_eval.quant.research import CompanyDossier, ResearchHit

GenerateFn = Callable[[list[dict[str, str]], float, int], tuple[str, Any]]

DISPLAY_KO: dict[str, str] = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
}

SECTION_SPECS_KO: list[tuple[str, str, int, bool]] = [
    ("핵심 요약", "두 회사 포지션 차이와 이번 분기 관전 포인트.", 55, True),
    ("사업 모델 및 전략", "삼성전자(다각화) vs SK하이닉스(메모리 집중).", 65, False),
    ("최근 동향 및 이슈", "HEADLINE DIGEST [H번호] 인용.", 70, True),
    ("섹터·거시 맥락", "AI/HBM·메모리 사이클·거시.", 55, False),
    ("촉매 요인", "1–2분기 내 구체 이벤트.", 45, True),
    ("리스크", "실적·사이클·규제.", 45, False),
    ("시나리오", "낙관·기본·비관 bullet.", 50, False),
]

SourceKind = Literal["code", "llm", "fallback"]


@dataclass
class StageRecord:
    stage: str
    source: SourceKind
    detail: str = ""


@dataclass
class MemoPipelineResult:
    markdown: str
    stages: list[StageRecord] = field(default_factory=list)
    llm_calls: int = 0
    runtime: Any = None


def _ko_name(ticker: str, fallback: str) -> str:
    return DISPLAY_KO.get(ticker, fallback)


def _trend_ko(trend: str) -> str:
    return {
        "revenue improving (recent quarters)": "매출 개선",
        "revenue declining (recent quarters)": "매출 둔화",
        "revenue flat": "매출 보합",
    }.get(trend, trend)


def iter_unique_headlines(
    dossiers: list[CompanyDossier],
    *,
    max_total: int = 5,
) -> list[tuple[str, str, ResearchHit]]:
    out: list[tuple[str, str, ResearchHit]] = []
    seen: set[str] = set()
    n = 0
    for d in dossiers:
        name = _ko_name(d.ticker, d.name)
        for h in d.hits:
            key = re.sub(r"\s+", " ", h.title.strip().lower())[:100]
            if key in seen:
                continue
            seen.add(key)
            n += 1
            out.append((f"H{n}", name, h))
            if n >= max_total:
                return out
    return out


def build_headlines_index(
    dossiers: list[CompanyDossier],
    *,
    max_total: int = 5,
) -> tuple[str, dict[str, str]]:
    lines: list[str] = []
    index: dict[str, str] = {}
    for hid, name, h in iter_unique_headlines(dossiers, max_total=max_total):
        index[hid] = h.title
        snippet = (h.snippet or "")[:200]
        lines.append(f"[{hid}] ({name}) {h.date} | {h.title}\n    {snippet}")
    if not lines:
        lines.append("(헤드라인 수집 없음)")
    return "\n".join(lines), index


def stage_render_facts(ctx: QuantContext, user_message: str) -> str:
    anchor = analysis_anchor()
    snapshots = [s for s in ctx.snapshots if s.price is not None or s.fundamentals.quarterly_rows]
    snapshots.sort(key=lambda s: (0 if s.ticker == "005930.KS" else 1, s.ticker))

    if len(snapshots) >= 2:
        title = (
            f"{_ko_name(snapshots[0].ticker, snapshots[0].name)} vs "
            f"{_ko_name(snapshots[1].ticker, snapshots[1].name)} 투자 메모"
        )
    elif snapshots:
        title = f"{_ko_name(snapshots[0].ticker, snapshots[0].name)} 투자 메모"
    else:
        title = "투자 메모"

    lines = [
        f"# {title}",
        f"**데이터 기준일:** {anchor['date']} | **당분기:** {anchor['quarter_label_ko']}",
        "",
        "## 재무 스냅샷 *(실시간 수집 — Yahoo Finance / FDR)*",
        "| 회사 | 티커 | 주가 | 일간 등락 | PER | PBR | ROE |",
        "|------|------|------|-----------|-----|-----|-----|",
    ]
    for s in snapshots:
        name = _ko_name(s.ticker, s.name)
        chg = f"{s.change_pct:+.2f}%" if s.change_pct is not None else "N/A"
        lines.append(
            f"| {name} | `{s.ticker}` | {fmt_krw_price(s.price)} | {chg} | "
            f"{s.fundamentals.per} | {s.fundamentals.pbr} | {s.fundamentals.roe} |"
        )
    for s in snapshots:
        name = _ko_name(s.ticker, s.name)
        lines.extend(["", f"### {name} (`{s.ticker}`) 분기 실적"])
        for row in s.fundamentals.quarterly_rows[:4]:
            lines.append(f"- {fmt_quarter_row(row)}")
        if not s.fundamentals.quarterly_rows:
            lines.append("- 분기 데이터 없음")

    headlines, _ = build_headlines_index(ctx.dossiers)
    lines.extend(["", "## 수집 헤드라인", headlines, "", "---", ""])
    return "\n".join(lines)


def build_compact_fact_digest(ctx: QuantContext) -> str:
    anchor = analysis_anchor()
    lines = [f"기준: {anchor['date']}, {anchor['quarter_label_ko']}"]
    for s in ctx.snapshots:
        name = _ko_name(s.ticker, s.name)
        chg = f", 일간 {s.change_pct:+.2f}%" if s.change_pct is not None else ""
        lines.append(f"- {name}: {fmt_krw_price(s.price)}{chg}, {_trend_ko(s.trend)}")
        if s.fundamentals.quarterly_rows:
            lines.append(f"  {fmt_quarter_row(s.fundamentals.quarterly_rows[0])}")
    return "\n".join(lines)


def _clean_llm_text(text: str) -> str:
    t = (text or "").strip()
    for marker in ("<start_of_turn>", "\nuser\n", "\nmodel\n"):
        if marker in t:
            t = t.split(marker)[0].strip()
    return re.sub(r"^---+.*$", "", t, flags=re.M).strip()


def _fallback_headline_digest(hid: str, hit: ResearchHit) -> str:
    t = hit.title.lower()
    if "memory" in t or "hbm" in t or "dram" in t:
        topic = "AI·메모리 수요"
    elif "iran" in t or "geopolit" in t:
        topic = "지정학 완화·risk-on"
    elif "listing" in t or "sec" in t or "calendar" in t:
        topic = "미국 상장 일정"
    else:
        topic = "반도체 섹터"
    return f"[{hid}] ({topic}) {hit.title[:90]}"


def stage_digest_headlines(
    ctx: QuantContext,
    generate_fn: GenerateFn,
    *,
    user_message: str,
) -> tuple[dict[str, str], int, Any]:
    digests: dict[str, str] = {}
    llm_calls = 0
    runtime: Any = None

    for hid, company, hit in iter_unique_headlines(ctx.dossiers, max_total=5):
        prompt = (
            f"영문 뉴스를 한국어 2문장으로 요약. 반드시 [{hid}]로 시작.\n"
            f"종목: {company}\n제목: {hit.title}\n내용: {(hit.snippet or '')[:280]}\n"
            "티커·주가 숫자 새로 만들지 마세요."
        )
        text, runtime = generate_fn([{"role": "user", "content": prompt}], 0.35, 120)
        text = _clean_llm_text(text)
        if len(re.findall(r"[가-힣]", text)) < 18 or f"[{hid}]" not in text:
            digests[hid] = _fallback_headline_digest(hid, hit)
        else:
            digests[hid] = text
            llm_calls += 1

    return digests, llm_calls, runtime


def format_digest_block(digests: dict[str, str]) -> str:
    return "\n".join(digests[k] for k in sorted(digests)) if digests else "(없음)"


def _fallback_section(title: str, ctx: QuantContext, digests: dict[str, str]) -> str:
    hkeys = sorted(digests)
    if title == "핵심 요약":
        anchor = analysis_anchor()
        names = "·".join(_ko_name(s.ticker, s.name) for s in ctx.snapshots)
        ref = f" [{hkeys[0]}]" if hkeys else ""
        return f"{anchor['quarter_label_ko']} {names} 비교.{ref} AI/HBM·메모리 사이클이 관건."
    if title == "사업 모델 및 전략":
        return (
            "- **삼성전자:** 메모리·파운드리·모바일 등 **다각화**.\n"
            "- **SK하이닉스:** DRAM/NAND·HBM **메모리 집중**, 업황 민감."
        )
    if title == "최근 동향 및 이슈":
        return "\n".join(f"- {digests[k]}" for k in hkeys[:4]) or "- 수집 헤드라인 참고."
    if title == "섹터·거시 맥락":
        return f"- {ctx.market_weather[:200]}\n- AI/HBM이 메모리 업황 견인."
    if title == "촉매 요인":
        lines = [f"- {digests[k]}" for k in hkeys[:2]]
        lines.append("- 분기 실적·HBM 믹스")
        return "\n".join(lines)
    if title == "리스크":
        return "- 메모리 가격 사이클 반전\n- 수요 둔화·환율·규제"
    if title == "시나리오":
        return (
            "- **낙관:** HBM 수요 지속 (가정)\n"
            "- **기본:** 추세 유지 (가정)\n"
            "- **비관:** 메모리 가격 하락 (가정)"
        )
    return "- (생성 실패)"


def _validate_section(text: str, *, min_hangul: int, need_h: bool) -> bool:
    if len(re.findall(r"[가-힣]", text)) < min_hangul:
        return False
    if re.search(r"\b0\d{5}\.[A-Z]{2,3}\b", text):
        return False
    if need_h and not re.search(r"\[H\d+\]", text):
        return False
    return True


def stage_analyze_sections(
    ctx: QuantContext,
    user_message: str,
    fact_digest: str,
    digests: dict[str, str],
    generate_fn: GenerateFn,
) -> tuple[list[tuple[str, str, SourceKind]], int, Any]:
    names = ", ".join(_ko_name(s.ticker, s.name) for s in ctx.snapshots)
    digest_block = format_digest_block(digests)
    sections: list[tuple[str, str, SourceKind]] = []
    llm_calls = 0
    runtime: Any = None

    for title, hint, min_h, need_h in SECTION_SPECS_KO:
        prompt = (
            f"**{title}** 섹션 본문만 한국어로 작성 (## 제목 쓰지 마세요).\n"
            f"대상: {names}\n과제: {hint}\n요청: {user_message}\n\n"
            f"FACTS:\n{fact_digest}\n\n"
            f"HEADLINE DIGEST:\n{digest_block}\n\n"
            "규칙: 주가·티커·표 금지. [H1] 형식 인용. 3문장 이상.\n"
            f"{language_generation_reminder(user_message)}"
        )
        text, runtime = generate_fn([{"role": "user", "content": prompt}], 0.38, 220)
        text = _clean_llm_text(text)
        text = re.sub(rf"^#+\s*{re.escape(title)}\s*", "", text).strip()
        source: SourceKind = "llm"

        if not _validate_section(text, min_hangul=min_h, need_h=need_h):
            text2, runtime = generate_fn(
                [{"role": "user", "content": prompt + "\n\n[재시도] [H1] 인용 필수. 한국어 3문장."}],
                0.30,
                220,
            )
            text2 = _clean_llm_text(text2)
            if _validate_section(text2, min_hangul=min_h, need_h=need_h):
                text, source, llm_calls = text2, "llm", llm_calls + 2
            else:
                text, source = _fallback_section(title, ctx, digests), "fallback"
                llm_calls += 1
        else:
            llm_calls += 1

        sections.append((title, text, source))

    return sections, llm_calls, runtime


def stage_assemble(facts_block: str, sections: list[tuple[str, str, SourceKind]]) -> str:
    analysis = "\n\n".join(f"## {title}\n{body}" for title, body, _ in sections)
    disclaimer = "\n\n## 면책 조항\n**본 메모는 교육 목적이며 투자 권유가 아닙니다.**"
    return f"{facts_block}## 애널리스트 분석\n\n{analysis}{disclaimer}"


def run_investment_memo_pipeline(
    ctx: QuantContext,
    user_message: str,
    generate_fn: GenerateFn,
) -> MemoPipelineResult:
    records: list[StageRecord] = []
    total_llm = 0
    runtime: Any = None

    facts = stage_render_facts(ctx, user_message)
    records.append(StageRecord("2_facts", "code", f"{len(facts)} chars"))

    digests, n_h, runtime = stage_digest_headlines(ctx, generate_fn, user_message=user_message)
    total_llm += n_h
    records.append(StageRecord("3_headline_digest", "llm", f"{len(digests)} headlines, {n_h} llm"))

    fact_digest = build_compact_fact_digest(ctx)
    sections, n_s, runtime = stage_analyze_sections(
        ctx, user_message, fact_digest, digests, generate_fn
    )
    total_llm += n_s
    llm_sec = sum(1 for _, _, s in sections if s == "llm")
    records.append(StageRecord("4_sections", "llm", f"{llm_sec}/{len(sections)} llm"))

    markdown = stage_assemble(facts, sections)
    records.append(StageRecord("5_assemble", "code"))

    return MemoPipelineResult(
        markdown=markdown,
        stages=records,
        llm_calls=total_llm,
        runtime=runtime,
    )
