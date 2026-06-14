"""Gold-standard structured response examples for LoRA training."""

from __future__ import annotations


def format_training_records(system: str) -> list[dict]:
    """Structured Markdown examples — language-matched, format-rich."""
    pairs = [
        (
            "Korean market highest potential — give a structured market view.",
            """## Executive summary
Among major indices, relative momentum varies by sector; no market has guaranteed upside.

## Market snapshot
| Index | Context |
|-------|---------|
| KOSPI | Korea large-cap benchmark |
| NASDAQ | US growth / tech tilt |
| S&P 500 | Broad US equities |

## Key drivers (Korea)
- Export cycle and semiconductor demand
- FX (KRW) and global rates
- Domestic policy and earnings season

## Scenario outlook (illustrative)
| Scenario | View | Risk |
|----------|------|------|
| Bull | Earnings beat + risk-on | Overheating |
| Base | Range-bound with sector rotation | Macro surprise |
| Bear | External shock / weak exports | Volatility spike |

## Disclaimer
**Not financial advice.** Consult a licensed advisor before investing.""",
            "market_analysis",
            "en",
        ),
        (
            "한국 시장 전망을 리포트 형식으로 정리해줘.",
            """## 요약
한국 시장은 업종·실적·글로벌 금리에 따라 변동성이 큽니다. 단정적 예측은 불가합니다.

## 핵심 포인트
- 반도체·2차전지 등 섹터별 차별화
- 환율·수출 지표 모니터링 필요
- 실적 시즌 이벤트 리스크

## 분석
거시 환경과 기업 실적이 동시에 작용합니다. 특정 종목 추천 없이 **섹터·리스크 프레임**으로 접근하세요.

## 리스크
- 지정학·금리 변동
- 실적 미스

## 다음 단계
- 공시(DART)·지수 추이 확인
- 필요 시 전문가 상담

**투자 자문 아님.**""",
            "report",
            "ko",
        ),
        (
            "Compare Samsung vs Apple on fundamentals — table format.",
            """## Quick verdict
Both are large-cap leaders; compare by valuation, growth, and ecosystem — not hype.

## Comparison table
| Criterion | Samsung | Apple |
|-----------|---------|-------|
| Focus | Semiconductors, devices | Ecosystem, services |
| Valuation | Check live PER/PBR | Check live PER/PBR |
| Risk | Cyclical chip demand | Regulatory / product cycle |

## Pros & cons
### Samsung
- **Pros:** Diversified hardware + memory leadership
- **Cons:** Cyclical earnings

### Apple
- **Pros:** Services margin, brand lock-in
- **Cons:** Hardware concentration risk

## Recommendation
Match choice to your horizon and risk tolerance — no universal winner.

**Not financial advice.**""",
            "comparison",
            "en",
        ),
        (
            "Summarize the pros and cons of remote work.",
            """## TL;DR
Remote work boosts flexibility but can reduce collaboration unless managed deliberately.

## Key points
- **Pros:** commute savings, focus time, wider hiring pool
- **Cons:** isolation, culture drift, onboarding friction

## Details
Hybrid models often balance productivity and team cohesion.""",
            "summary",
            "en",
        ),
        (
            "How to set up a Python venv step by step",
            """## Goal
Create an isolated Python environment for a project.

## Prerequisites
- Python 3.10+ installed
- Terminal access

## Steps
1. **Create folder** — `mkdir myproject && cd myproject`
2. **Create venv** — `python -m venv .venv`
3. **Activate** — Windows: `.venv\\Scripts\\activate`
4. **Install deps** — `pip install -r requirements.txt`

## Verify success
`which python` (or `where python`) points inside `.venv`.""",
            "how_to",
            "en",
        ),
        (
            "SWOT analysis for launching a small AI chat app",
            """## SWOT

| | Helpful | Harmful |
|---|---------|---------|
| **Internal** | **Strengths:** fast iteration, niche UX | **Weaknesses:** limited GPU budget |
| **External** | **Opportunities:** APAC multilingual gap | **Threats:** API cost, compliance |

## Strategic takeaway
Focus on a narrow vertical with strong safety guidelines before scaling.""",
            "swot",
            "en",
        ),
    ]

    records: list[dict] = []
    for user, assistant, fmt, lang in pairs:
        records.append({
            "messages": [
                {"role": "system", "content": system + f"\n\nUse structured Markdown ({fmt}). Reply in user's language."},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "meta": {"type": "format_gold", "format": fmt, "language": lang},
        })
    return records
