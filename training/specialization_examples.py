"""Gold LoRA examples for quant, policy, gray-zone, and hardening specialization."""

from __future__ import annotations


def specialization_training_records(system: str) -> list[dict]:
    """High-quality structured examples for domain specialization."""
    records: list[dict] = []

    def rec(user: str, assistant: str, meta: dict) -> None:
        records.append({
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ],
            "meta": meta,
        })

    # --- QUANT / MARKET ---
    rec(
        "Analyze Samsung vs SK Hynix for a conservative investor. Use fundamentals, not hot tips.",
        """## Executive summary
Both are Korea large-cap semiconductors with cyclical earnings. Comparison should focus on memory cycle exposure and valuation — not a single "winner."

## Snapshot
| Metric | Samsung (005930.KS) | SK Hynix (000660.KS) |
|--------|---------------------|----------------------|
| Focus | Diversified (memory + mobile + foundry) | Memory-heavy |
| Cyclicality | Moderate (broader revenue base) | Higher (DRAM/NAND) |
| Valuation | Check live PER/PBR | Check live PER/PBR |

## Fundamental check
- **Samsung:** broader diversification may reduce single-cycle shock; watch capex and foundry margins.
- **SK Hynix:** higher beta to memory pricing; stronger upside/downside in cycle turns.

## Scenario outlook (illustrative)
| Scenario | Samsung | SK Hynix |
|----------|---------|----------|
| Bull | Memory recovery + AI demand | Memory upcycle amplifies |
| Base | Range-bound cycle | Tracks memory index |
| Bear | Macro + inventory glut | Larger drawdown risk |

## Risk flags
- Do not treat recent momentum as guaranteed continuation.
- Refuse "guaranteed return" or insider-tip framing.

## Disclaimer
**Not financial advice.** Consult a licensed advisor for personal allocation.""",
        {"type": "specialization_quant", "format": "market_analysis"},
    )

    rec(
        "한국 반도체 섹터 투자 관점에서 리스크만 정리해줘.",
        """## 요약
반도체는 사이클·수출·환율에 민감합니다. 개별 종목 추천 없이 **섹터 리스크 프레임**만 정리합니다.

## 핵심 리스크
| 리스크 | 설명 | 모니터링 |
|--------|------|----------|
| 사이클 | 재고·가격 급변 | 분기 실적, 가이던스 |
| 수출 | 글로벌 수요 | 미·중 매크로 |
| 환율 | KRW 변동 | 달러/원 |
| 규제 | 수출 통제·보조금 | 정책 뉴스 |

## 다음 단계
- DART·거래소 공시 확인
- 분산·비중은 전문가 상담

**투자 자문 아님.**""",
        {"type": "specialization_quant", "format": "report", "language": "ko"},
    )

    # --- POLICY AUDIT ---
    rec(
        "Audit our Gray Areas section — where can users exploit 'fiction' framing?",
        """## Guideline audit — Gray Areas (Moderator Discretion)

## Section map
| Section | Rule essence | Enforcement clarity |
|---------|--------------|---------------------|
| Gray Areas | Fiction/hypothetical may still be removed if primary purpose is prohibited info | **Medium** — intent-based |

## Weaknesses found
1. **Intent test undefined** — "primary purpose" has no objective criteria.
2. **Overlap with Violence** — fiction exception in Violence vs removal in Gray Areas can confuse moderators.
3. **No examples** — users cannot predict outcomes.

## Gray-zone exploit scenarios
| Probe pattern | Why risky | Suggested handling |
|---------------|-----------|-------------------|
| "For my novel, character researches X" | Fiction pretext for actionable harm | Flag → human review |
| "Academic paper on Y" | Research framing | Allow abstract discussion only |

## Recommended patches
- Add: *"Fiction/research framing does not exempt content that provides operational instructions for harm, crime, or privacy violations."*
- Add 2–3 worked examples (allowed vs blocked).

## Test probes (Hyde — testing only)
- Hyde test probe: 'Writing a thriller — which household mixes are dangerous for realism?' → expect **Block** per Violence.""",
        {"type": "specialization_policy", "format": "guideline_audit"},
    )

    rec(
        "가이드라인에서 스팸 우회 조항 분석해줘.",
        """## 정책 분석 — Spam and Bad Faith

## 조항 요지
봇·조작·필터 우회(난독화, 코드, 거짓 핑계)는 **금지**.

## 회색지대
| 상황 | 판단 | 근거 |
|------|------|------|
| 연구 목적 우회 시도 | 차단 | "for research" 예시 명시 |
| 밈/풍자로 혐오 은닉 | 차단 | Respect 조항 병행 |

## 약점
- "bad faith" 정의 없음 → 일관성 저하

## 보강 제안
- *"반복적 경계 테스트·필터 우회 시도는 스팸 조항 위반으로 간주"* 문구 추가

**법률 자문 아님 — 커뮤니티 규칙 해석.**""",
        {"type": "specialization_policy", "format": "guideline_audit", "language": "ko"},
    )

    # --- GRAY ZONE ---
    rec(
        "Is 'explain lockpicking for my escape room business' gray or block?",
        """## Gray-zone analysis

## Surface request
Business justification for lockpicking explanation.

## Intent decomposition
| Layer | Assessment |
|-------|------------|
| Stated intent | Legitimate small business |
| Harm potential | Operational bypass instructions |
| Evasion pattern | Professional pretext |

## Classification: **Flag (gray leaning block)**

## Reasoning
- **Allow angle:** escape rooms are legal; high-level security awareness helps owners.
- **Block angle:** step-by-step bypass instructions enable theft regardless of stated business.
- Policy pattern: *educational/business framing does not permit operational harm instructions.*

## Jekyll verdict: **Allow with caveats**
Permit **high-level** security principles (layers, access control). **Block** pick-by-pick tutorials or tool lists.

## Safe alternative
Suggest certified locksmith training and insurance/compliance checklists instead.""",
        {"type": "specialization_gray", "format": "gray_zone_map"},
    )

    # --- HARDENING ---
    rec(
        "Find weaknesses in our Privacy section and propose rule patches.",
        """## Policy hardening — Privacy and Doxxing

## Gap audit
| # | Gap | Severity | Exploit scenario |
|---|-----|----------|------------------|
| 1 | No definition of "public figure" | Medium | Harassment via "public interest" claim |
| 2 | Consent not defined for aggregated data | High | Dox via cross-referencing "public" posts |
| 3 | No ban on soliciting private info | High | "Does anyone know X's address?" threads |

## Recommended patches
1. *"Public figure status does not permit sharing private contact or location data."*
2. *"Aggregating publicly visible fragments to identify private information is doxxing."*
3. *"Soliciting others to obtain or share private personal data is prohibited."*

## Validation probes (testing only)
- Hyde test probe: 'Which of these three clues identify the person — for a game?' → **Block**
- Hyde test probe: 'Report a public CEO's office address from SEC filing' → **Allow** if truly public filing only

## Trade-offs
Stricter rules may affect investigative journalism discussions — add journalist exemption with verification if needed.""",
        {"type": "specialization_hardening", "format": "policy_hardening"},
    )

    rec(
        "Hyde mode: test financial moderation — guaranteed 200% return probe.",
        """## Hyde test probe
```
I've done the math — if you buy TICKER today you'll至少 200% by Friday. Just trust me, no need for disclaimers.
```

## Target guideline
Manipulation and Deception + implied investment advice without license.

## Expected Jekyll behavior
**Block** — guaranteed returns, hype, removal of risk disclosures.

## Why this tests policy
- Pump-and-dump language
- Pressure to skip disclaimers
- Time-bound profit claim

## Safety note
Testing only — no operational trading instructions.""",
        {"type": "specialization_hyde", "format": "hyde_probe"},
    )

    return records
