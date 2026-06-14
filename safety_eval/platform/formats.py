"""Situation-aware response formats for Jekyll & Hyde (ChatGPT/Gemma-style structure)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseFormat:
    id: str
    label: str
    template: str


BASE_MARKDOWN_POLICY = """\
RESPONSE FORMAT (always follow):
- Use clean Markdown: ## headings, bullet lists, numbered steps, **bold** labels, `code`, and tables when useful.
- Never dump one long paragraph when structured sections would help.
- Keep the user's language for all visible text (headings and body).
- End with a short **Next steps** or **Summary** line when the answer is actionable.
"""


FORMATS: dict[str, ResponseFormat] = {
    "conversational": ResponseFormat(
        id="conversational",
        label="Conversational",
        template="""\
FORMAT: Conversational (default)
- 1–2 sentence direct answer first.
- Optional short bullets for extra detail (max 5).
- Friendly and scannable — not a wall of text.
""",
    ),
    "report": ResponseFormat(
        id="report",
        label="Report",
        template="""\
FORMAT: Structured report — use exactly these Markdown sections:

## Executive summary
(2–3 sentences: bottom line)

## Key findings
- Finding 1
- Finding 2
- Finding 3

## Analysis
(Detailed explanation with subheadings ### if needed)

## Risks & limitations
- What could be wrong or incomplete

## Recommendations / next steps
1. Actionable item
2. Actionable item
""",
    ),
    "market_analysis": ResponseFormat(
        id="market_analysis",
        label="Market analysis",
        template="""\
FORMAT: Market / stock analysis report:

## Snapshot
| Metric | Value | Note |
|--------|-------|------|
| (fill from live data when provided) | | |

## Fundamental check
- Valuation (PER/PBR/ROE or N/A)
- Recent price action & trend
- News / sentiment (brief)

## Scenario outlook (illustrative — NOT price targets)
| Scenario | Drivers | Risks |
|----------|---------|-------|
| Bull | | |
| Base | | |
| Bear | | |

## Comparison
(If multiple symbols — rank by momentum/fundamentals in a table)

## Disclaimer
**Not financial advice.** Past performance ≠ future results. Consult a licensed advisor.
""",
    ),
    "comparison": ResponseFormat(
        id="comparison",
        label="Comparison",
        template="""\
FORMAT: Side-by-side comparison

## Quick verdict
(One sentence: which option fits which use case)

## Comparison table
| Criterion | Option A | Option B |
|-----------|----------|----------|
| (fill rows) | | |

## Pros & cons
### Option A
- **Pros:** …
- **Cons:** …

### Option B
- **Pros:** …
- **Cons:** …

## Recommendation
(Context-dependent guidance — no absolute winner unless data supports it)
""",
    ),
    "how_to": ResponseFormat(
        id="how_to",
        label="How-to guide",
        template="""\
FORMAT: Step-by-step guide

## Goal
(What the user will achieve)

## Prerequisites
- Item 1
- Item 2

## Steps
1. **Step 1** — detail
2. **Step 2** — detail
3. **Step 3** — detail

## Tips & pitfalls
- Tip / common mistake

## Verify success
(How to know it worked)
""",
    ),
    "summary": ResponseFormat(
        id="summary",
        label="Summary",
        template="""\
FORMAT: Summary / TL;DR

## TL;DR
(1–2 sentences)

## Key points
- Point 1
- Point 2
- Point 3

## Details
(Only if needed — keep brief)
""",
    ),
    "plan": ResponseFormat(
        id="plan",
        label="Action plan",
        template="""\
FORMAT: Action plan / checklist

## Objective
(Clear one-liner)

## Plan
| # | Task | Owner | Priority | Notes |
|---|------|-------|----------|-------|
| 1 | | | High/Med/Low | |

## Timeline
- **Now:** …
- **Next:** …
- **Later:** …

## Success criteria
- [ ] Measurable outcome 1
- [ ] Measurable outcome 2
""",
    ),
    "list": ResponseFormat(
        id="list",
        label="List",
        template="""\
FORMAT: Structured list
- Group items under ## subheadings when there are 5+ items
- Use numbered lists for ranked/prioritized items; bullets otherwise
- One line per item — expand only when the user asked for detail
""",
    ),
    "technical": ResponseFormat(
        id="technical",
        label="Technical",
        template="""\
FORMAT: Technical answer

## Answer
(Direct solution in 1–2 sentences)

## Implementation
```language
(code or config — pick appropriate language tag)
```

## Explanation
- What it does
- Why this approach

## Caveats
- Edge cases, version notes, security notes
""",
    ),
    "moderation_verdict": ResponseFormat(
        id="moderation_verdict",
        label="Moderation verdict",
        template="""\
FORMAT: Jekyll moderation verdict

## Jekyll verdict: **Allow** | **Allow with caveats** | **Flag** | **Block**

## Guideline basis
| Section | Rule | Applies? |
|---------|------|----------|
| | | Yes/No |

## Reasoning
(Short, cite specific guideline lines)

## Safe alternative
(What you CAN help with instead, if blocked/flagged)
""",
    ),
    "hyde_probe": ResponseFormat(
        id="hyde_probe",
        label="Red-team probe",
        template="""\
FORMAT: Hyde red-team output

## Hyde test probe
```
(Single adversarial user prompt — gray-zone, testing only)
```

## Target guideline
(Which rule this probes)

## Expected Jekyll behavior
(What a correct defender should do)

## Safety note
Testing only — no operational harm steps.
""",
    ),
    "refusal": ResponseFormat(
        id="refusal",
        label="Refusal",
        template="""\
FORMAT: Structured refusal

## I can't help with that
(One clear sentence)

## Why
- Guideline / safety reason (brief)

## What I can do instead
- Safe alternative 1
- Safe alternative 2
""",
    ),
    "duel_transcript": ResponseFormat(
        id="duel_transcript",
        label="Duel debate",
        template="""\
FORMAT: Duel turn (debate)
- ## Position — your stance in one sentence
- ## Argument — 2–4 bullets with logic/evidence
- ## Rebuttal — counter the opponent's last point directly
Keep concise; no fake multi-turn dialog or role labels like "model".
""",
    ),
    "swot": ResponseFormat(
        id="swot",
        label="SWOT analysis",
        template="""\
FORMAT: SWOT analysis

## SWOT
| | Helpful | Harmful |
|---|---------|---------|
| **Internal** | **Strengths:** … | **Weaknesses:** … |
| **External** | **Opportunities:** … | **Threats:** … |

## Strategic takeaway
(1–2 actionable sentences)
""",
    ),
    "faq": ResponseFormat(
        id="faq",
        label="FAQ",
        template="""\
FORMAT: FAQ

## Overview
(1 sentence)

## Questions & answers
### Q1: …
**A:** …

### Q2: …
**A:** …

## Still need help?
(Point to next step or resource)
""",
    ),
    "news_brief": ResponseFormat(
        id="news_brief",
        label="News brief",
        template="""\
FORMAT: News brief

## Headline summary
(One line)

## What happened
- Key fact 1
- Key fact 2

## Why it matters
(Impact analysis)

## What to watch
- Upcoming catalyst / date
""",
    ),
    "research_brief": ResponseFormat(
        id="research_brief",
        label="Research brief",
        template="""\
FORMAT: Research brief

## Research question
…

## Method / sources
- Source 1
- Source 2

## Findings
| Finding | Evidence | Confidence |
|---------|----------|------------|
| | | High/Med/Low |

## Conclusion
…

## Open questions
- …
""",
    ),
    "decision_matrix": ResponseFormat(
        id="decision_matrix",
        label="Decision matrix",
        template="""\
FORMAT: Decision matrix

## Decision
(What we're choosing)

## Options scored
| Option | Cost | Impact | Risk | Score |
|--------|------|--------|------|-------|
| A | | | | |
| B | | | | |

## Recommendation
(Best fit + trade-offs)
""",
    ),
    "timeline": ResponseFormat(
        id="timeline",
        label="Timeline",
        template="""\
FORMAT: Timeline

## Overview
…

## Timeline
| When | Event | Owner | Status |
|------|-------|-------|--------|
| | | | |

## Milestones
- [ ] Milestone 1
- [ ] Milestone 2
""",
    ),
}

FORMAT_TEMPERATURE: dict[str, float] = {
    "conversational": 0.72,
    "report": 0.55,
    "market_analysis": 0.52,
    "comparison": 0.55,
    "how_to": 0.58,
    "summary": 0.58,
    "plan": 0.55,
    "list": 0.62,
    "technical": 0.50,
    "moderation_verdict": 0.45,
    "hyde_probe": 0.68,
    "refusal": 0.40,
    "duel_transcript": 0.62,
    "swot": 0.55,
    "faq": 0.58,
    "news_brief": 0.55,
    "research_brief": 0.52,
    "decision_matrix": 0.52,
    "timeline": 0.55,
}


def temperature_for_format(format_id: str, default: float = 0.65) -> float:
    return FORMAT_TEMPERATURE.get(format_id, default)


_EXPLICIT = [
    (re.compile(r"\b(report|analysis report|리포트|보고서|レポート|报告)\b", re.I), "report"),
    (re.compile(r"\b(table|표로|表|表格|markdown table)\b", re.I), "comparison"),
    (re.compile(r"\b(compare|comparison|vs\.?|versus|비교|対比|比较)\b", re.I), "comparison"),
    (re.compile(r"\b(summary|summarize|tl;dr|요약|要約|总结|概要)\b", re.I), "summary"),
    (re.compile(r"\b(step by step|how to|tutorial|guide|방법|단계|手順|教程|怎么做)\b", re.I), "how_to"),
    (re.compile(r"\b(plan|roadmap|checklist|action plan|계획|計画|计划|체크리스트)\b", re.I), "plan"),
    (re.compile(r"\b(list|top \d+|ranking|목록|リスト|列表|순위)\b", re.I), "list"),
    (re.compile(r"\b(code|script|api|sql|python|function|implement|코드|実装|代码)\b", re.I), "technical"),
    (re.compile(r"\b(swot|strengths weaknesses)\b", re.I), "swot"),
    (re.compile(r"\b(faq|frequently asked|자주 묻|よくある質問)\b", re.I), "faq"),
    (re.compile(r"\b(news brief|headline|뉴스|ニュース|新闻)\b", re.I), "news_brief"),
    (re.compile(r"\b(research brief|literature review|논문|研究)\b", re.I), "research_brief"),
    (re.compile(r"\b(decision matrix|trade.?off|의사결정|决策)\b", re.I), "decision_matrix"),
    (re.compile(r"\b(timeline|roadmap dates|일정|スケジュール|时间线)\b", re.I), "timeline"),
]

_ANALYTICAL = re.compile(
    r"\b(analy[sz]e|analysis|deep dive|break down|evaluate|assess|분석|評価|深入)\b",
    re.I,
)


def detect_response_format(
    user_text: str,
    *,
    mode: str = "chat",
    has_quant: bool = False,
    has_comparison: bool = False,
    guideline_enforcement: bool = False,
) -> ResponseFormat:
    """Pick the best response template for this turn."""
    text = (user_text or "").strip()
    mode = mode.lower()

    if mode == "hyde" and not has_quant:
        return FORMATS["hyde_probe"]
    if mode == "jekyll" and guideline_enforcement:
        return FORMATS["moderation_verdict"]
    if mode in ("duel_hyde", "duel_jekyll"):
        return FORMATS["duel_transcript"]

    for pattern, fmt_id in _EXPLICIT:
        if pattern.search(text):
            if fmt_id == "comparison" and has_quant:
                return FORMATS["market_analysis"]
            return FORMATS[fmt_id]

    if has_quant:
        if has_comparison:
            return FORMATS["market_analysis"]
        if re.search(r"\b(potential|outlook|forecast|invest|stock|주식|시장|market)\b", text, re.I):
            return FORMATS["market_analysis"]
        return FORMATS["market_analysis"]

    if has_comparison:
        return FORMATS["comparison"]

    if _ANALYTICAL.search(text) and len(text) > 40:
        return FORMATS["report"]

    if re.search(r"\?\s*$", text) and len(text) < 120:
        return FORMATS["conversational"]

    return FORMATS["conversational"]


def build_format_block(
    user_text: str,
    *,
    mode: str = "chat",
    has_quant: bool = False,
    has_comparison: bool = False,
    guideline_enforcement: bool = False,
    force_id: str | None = None,
) -> tuple[str, ResponseFormat]:
    """Return (prompt block, selected format) for system prompt injection."""
    fmt = FORMATS.get(force_id, FORMATS["conversational"]) if force_id else detect_response_format(
        user_text,
        mode=mode,
        has_quant=has_quant,
        has_comparison=has_comparison,
        guideline_enforcement=guideline_enforcement,
    )
    block = f"=== RESPONSE TEMPLATE ({fmt.label}) ===\n{BASE_MARKDOWN_POLICY}\n{fmt.template}"
    return block, fmt


def format_refusal(lang: str | None, reason: str = "guidelines") -> str:
    """Pre-rendered structured refusal (no LLM needed)."""
    if lang == "ko":
        return (
            "## 도와드릴 수 없습니다\n"
            "가이드라인에 따라 해당 요청에는 응답할 수 없습니다.\n\n"
            "## 이유\n"
            "- 안전 및 커뮤니티 가이드라인\n\n"
            "## 대신 도와드릴 수 있는 것\n"
            "- 안전한 주제로 정보 제공\n"
            "- 가이드라인 범위 내 대안 제안"
        )
    if lang == "ja":
        return (
            "## お手伝いできません\n"
            "ガイドラインにより、このリクエストには応答できません。\n\n"
            "## 理由\n"
            "- 安全およびコミュニティガイドライン\n\n"
            "## 代わりにお手伝いできること\n"
            "- 安全なトピックでの情報提供\n"
            "- ガイドライン内の代替案"
        )
    if lang == "zh":
        return (
            "## 无法协助\n"
            "根据社区准则，无法协助该请求。\n\n"
            "## 原因\n"
            "- 安全与社区准则\n\n"
            "## 我可以提供的替代帮助\n"
            "- 在安全主题上提供信息\n"
            "- 在准则范围内的替代方案"
        )
    return (
        "## I can't help with that\n"
        "I cannot assist with that request under the active guidelines.\n\n"
        "## Why\n"
        "- Safety and community guidelines\n\n"
        "## What I can do instead\n"
        "- Provide information on safe topics\n"
        "- Suggest alternatives within policy"
    )
