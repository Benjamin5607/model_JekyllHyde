"""Detect template leaks and sanitize chat output for simple turns."""

from __future__ import annotations

import re

_GREETING = re.compile(
    r"^(?:hi|hello|hey|yo|hiya|howdy|good\s+(?:morning|afternoon|evening)|"
    r"안녕(?:하세요|히)?|こんにちは|你好|嗨|สวัสดี|xin\s*chào)[!.?\s]*$",
    re.I,
)

_TEMPLATE_LEAK = re.compile(
    r"(?:"
    r"RESPONSE\s+TEMPLATE|KEY\s+CONCEPT|Example\s+Response\s+Template|"
    r"SAMPLE\s+ANSWER|USER\s+QUERY:|Policy\s+Analyst\s+Role|Dual-Nature\s+Mode|"
    r"OUTPUT\s+LANGUAGE:|===\s*RESPONSE\s+TEMPLATE"
    r")",
    re.I,
)


def is_simple_greeting(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 48:
        return False
    return bool(_GREETING.match(t))


def looks_like_template_leak(text: str) -> bool:
    return bool(_TEMPLATE_LEAK.search(text or ""))


def greeting_reply(lang: str | None) -> str:
    replies = {
        "ko": (
            "안녕하세요! Jekyll & Hyde입니다 — Gemma가 아닌 독립 듀얼 페르소나 모델이에요. "
            "주식·가이드라인·정책 분석이나 일반 대화 모두 도와드릴 수 있습니다. 무엇을 도와드릴까요?"
        ),
        "ja": (
            "こんにちは。Jekyll & Hydeです — Gemmaではない独立したデュアルペルソナモデルです。"
            "株式・ガイドライン・政策分析や一般の会話もお手伝いできます。何をお手伝いしましょうか？"
        ),
        "zh": (
            "你好！我是 Jekyll & Hyde — 独立的 Jekyll/Hyde 双人格模型，不是 Gemma。"
            "我可以协助股票/准则/政策分析或日常对话。需要什么帮助？"
        ),
    }
    return replies.get(lang or "en", (
        "Hello! I'm Jekyll & Hyde — an independent dual-persona model, not base Gemma. "
        "I can help with stocks, guidelines, policy analysis, or everyday chat. What would you like to explore?"
    ))


def sanitize_chat_output(content: str, *, user_text: str, lang: str | None) -> str:
    """Replace template-regurgitation with a safe reply on simple turns."""
    if not content:
        return content
    if looks_like_template_leak(content):
        if is_simple_greeting(user_text):
            return greeting_reply(lang)
        # Strip obvious meta blocks for other queries too
        lines = []
        for line in content.splitlines():
            if _TEMPLATE_LEAK.search(line):
                break
            lines.append(line)
        trimmed = "\n".join(lines).strip()
        if trimmed and not looks_like_template_leak(trimmed):
            return trimmed
    if is_simple_greeting(user_text) and len(content) > 400 and "##" in content:
        return greeting_reply(lang)
    return content
