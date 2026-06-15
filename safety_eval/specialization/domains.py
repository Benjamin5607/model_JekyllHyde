"""Detect analysis domain and inject expert specialization prompts."""

from __future__ import annotations

import re

QUANT_PATTERNS = re.compile(
    r"(주식|stock|share|ticker|투자|invest|portfolio|실적|earnings|"
    r"PER|PBR|ROE|EPS|배당|dividend|코스피|kosdaq|nasdaq|s&p|"
    r"market|시장|sector|섹터|fundamental|valuation|급등|급락|"
    r"삼성|samsung|nvidia|apple|sk\s*hynix|etf|채권|bond)",
    re.I,
)

POLICY_PATTERNS = re.compile(
    r"(guideline|가이드라인|community\s*rule|policy|규칙|規約|准则|"
    r"moderation|모더레이션|terms\s*of\s*service|tos|"
    r"compliance|준수|법|law|legal|regulation|규정|"
    r"section\s*\d|clause|article|조항)",
    re.I,
)

GRAY_ZONE_PATTERNS = re.compile(
    r"(gray\s*zone|grey\s*zone|회색\s*지대|曖昧|边缘|"
    r"ambiguous|edge\s*case|loophole|우회|evasion|"
    r"hypothetical|fiction|satire|for\s*research|"
    r"의도|intent|borderline|애매)",
    re.I,
)

HARDENING_PATTERNS = re.compile(
    r"(weakness|약점|gap|취약|보강|strengthen|harden|"
    r"improve\s*(the\s*)?rule|patch|fix\s*guideline|"
    r"red\s*team|stress\s*test|audit|점검|"
    r"coverage|blind\s*spot|누락|missing\s*rule)",
    re.I,
)

_ANALYTICAL_POLICY = re.compile(
    r"(analy[sz]e|audit|review|evaluate|분석|검토|評価)",
    re.I,
)


def detect_domains(
    user_text: str,
    *,
    has_quant: bool = False,
    has_guidelines: bool = False,
    mode: str = "chat",
) -> list[str]:
    text = (user_text or "").strip()
    domains: list[str] = []

    if has_quant or QUANT_PATTERNS.search(text):
        domains.append("quant")
    if has_guidelines or POLICY_PATTERNS.search(text) or mode in ("jekyll", "hyde", "duel_hyde", "duel_jekyll"):
        if mode != "chat" or POLICY_PATTERNS.search(text) or has_guidelines:
            domains.append("policy")
    if GRAY_ZONE_PATTERNS.search(text):
        domains.append("gray_zone")
    if HARDENING_PATTERNS.search(text) or mode == "hyde":
        domains.append("hardening")

    if not domains and _ANALYTICAL_POLICY.search(text) and has_guidelines:
        domains.append("policy")

    seen: set[str] = set()
    out: list[str] = []
    for d in domains:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def primary_domain(domains: list[str], *, has_quant: bool = False) -> str | None:
    if not domains:
        return "quant" if has_quant else None
    for p in ("hardening", "gray_zone", "policy", "quant"):
        if p in domains:
            return p
    return domains[0]


_DOMAIN_BLOCKS: dict[str, str] = {
    "quant": """\
DOMAIN EXPERTISE — EQUITY & MARKET ANALYSIS (Jekyll-safe):
- Use ONLY the LIVE MARKET DATA block (Yahoo/FDR) attached to the user message — never invent prices, quarters, or years.
- DATA AS OF and CURRENT QUARTER in the block are authoritative; if user asks "this quarter", use that quarter — not 2023 or other stale periods.
- Structure: snapshot → fundamentals → catalysts → risks → bull/base/bear scenarios (illustrative).
- Compare peers in tables when multiple tickers are in scope.
- If a metric is N/A in live data, say "data unavailable" — do not guess from memory.
- Flag manipulation patterns (pump language, guaranteed returns, insider-tip framing) and refuse those angles.
- Always end with **Not financial advice** — recommend licensed advisors for personal allocation.
- Never output buy/sell/hold directives; frame as educational scenario analysis only.
""",
    "policy": """\
DOMAIN EXPERTISE — GUIDELINES / RULES / LAW-STYLE POLICY:
- Map every claim to a **specific section** of ACTIVE GUIDELINES (or stated rules).
- Identify conflicts between sections, missing definitions, and enforcement ambiguity.
- Distinguish: prohibited vs allowed vs moderator-discretion (gray header sections).
- Cite exact rule language when blocking or flagging; propose clearer wording if asked.
- For legal questions: explain policy alignment, not personal legal advice.
""",
    "gray_zone": """\
DOMAIN EXPERTISE — GRAY-ZONE & INTENT ANALYSIS:
- Decompose: surface request → likely user intent → evasion technique (if any) → harm potential.
- Classify: **Clear allow** | **Clear block** | **Gray — needs human review**.
- List evasion patterns: fiction framing, hypothetical, research pretext, satire, translation, coded language.
- For gray cases: explain BOTH why someone might allow AND why safety says flag/block.
- Hyde may describe test probes; Jekyll must defend with consistent logic.
""",
    "hardening": """\
DOMAIN EXPERTISE — WEAKNESS AUDIT & POLICY HARDENING:
- Find gaps: rules that are undefined, overlapping, unenforceable, or easily bypassed.
- Output: **Gap** → **Exploit scenario** → **Recommended patch** (exact suggested rule text).
- Prioritize by severity: safety-critical > legal > spam > cosmetic ambiguity.
- Suggest 1–3 Hyde-style test probes per gap to validate the patch (testing only).
- Track consistency: would the new rule break legitimate use cases? Note trade-offs.
""",
}


def build_specialization_block(
    user_text: str,
    *,
    mode: str = "chat",
    has_quant: bool = False,
    has_guidelines: bool = False,
) -> tuple[str, list[str]]:
    domains = detect_domains(
        user_text,
        has_quant=has_quant,
        has_guidelines=has_guidelines,
        mode=mode,
    )
    if not domains:
        return "", []

    parts = [
        "=== JEKYLL & HYDE SPECIALIZATION (primary focus for this turn) ===",
        "Optimized for: stock/market analysis, guideline & policy analysis, gray-zone classification, policy hardening.",
    ]
    for d in domains:
        block = _DOMAIN_BLOCKS.get(d)
        if block:
            parts.append(block)

    if mode == "hyde":
        parts.append("HYDE THIS TURN: prioritize evasion probes and gap-finding that stress-test the rules.")
    elif mode == "jekyll":
        parts.append("JEKYLL THIS TURN: prioritize consistent enforcement, citations, and safe alternatives.")

    return "\n\n".join(parts), domains
