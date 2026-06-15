"""APAC language support for Jekyll & Hyde."""

from __future__ import annotations

import re

APAC_LANGUAGES: dict[str, str] = {
    "ko": "Korean (한국어)",
    "ja": "Japanese (日本語)",
    "zh": "Chinese (中文)",
    "zh-TW": "Chinese Traditional (繁體中文)",
    "th": "Thai (ไทย)",
    "vi": "Vietnamese (Tiếng Việt)",
    "id": "Indonesian (Bahasa Indonesia)",
    "ms": "Malay (Bahasa Melayu)",
    "tl": "Tagalog (Filipino)",
    "hi": "Hindi (हिन्दी)",
    "bn": "Bengali (বাংলা)",
    "ta": "Tamil (தமிழ்)",
    "my": "Burmese (မြန်မာ)",
    "km": "Khmer (ខ្មែរ)",
    "lo": "Lao (ລາວ)",
    "mn": "Mongolian (Монгол)",
    "ne": "Nepali (नेपाली)",
    "si": "Sinhala (සිංහල)",
    "uz": "Uzbek (Oʻzbek)",
    "kk": "Kazakh (Қазақ)",
}

APAC_LANGUAGE_POLICY = """\
LANGUAGE POLICY:
- Reply in the SAME language as the user's latest message (English, Korean, Japanese, etc.).
- Do NOT default to Korean or any other language when the user wrote in English.
- Do NOT switch languages unless the user explicitly asks for translation.
- App/UI language settings do NOT override this rule — only the user's message matters.
- You may read English market data or guidelines, but still answer in the user's language.
- APAC languages in the registry are fully supported when the user writes in them.
"""

APAC_LANGUAGE_LIST = ", ".join(f"{code}={name}" for code, name in APAC_LANGUAGES.items())


def detect_apac_language(text: str) -> str | None:
    """Lightweight script-based language hint (not ML)."""
    if not text.strip():
        return None

    ranges = [
        ("ko", (0xAC00, 0xD7A3)),
        ("ja", (0x3040, 0x309F)),
        ("ja", (0x30A0, 0x30FF)),
        ("zh", (0x4E00, 0x9FFF)),
        ("th", (0x0E00, 0x0E7F)),
        ("my", (0x1000, 0x109F)),
        ("km", (0x1780, 0x17FF)),
        ("lo", (0x0E80, 0x0EFF)),
        ("ta", (0x0B80, 0x0BFF)),
        ("bn", (0x0980, 0x09FF)),
        ("hi", (0x0900, 0x097F)),
        ("mn", (0x1800, 0x18AF)),
    ]
    for char in text:
        code = ord(char)
        for lang, (start, end) in ranges:
            if start <= code <= end:
                return lang

    lower = text.lower()
    vietnamese_marks = ("ă", "â", "đ", "ê", "ô", "ơ", "ư")
    if any(m in lower for m in vietnamese_marks):
        return "vi"
    if any(w in lower for w in ("yang", "dan", "tidak", "dengan", "untuk")):
        return "id"
    if any(w in lower for w in ("dan", "tidak", "yang", "adalah")):
        return "ms"

    return None


_REPLY_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    **APAC_LANGUAGES,
}


def detect_user_language(text: str) -> str:
    """Detect reply language from user text. Returns ISO-ish code including 'en'."""
    if not text.strip():
        return "en"
    apac = detect_apac_language(text)
    if apac:
        return apac
    return "en"


def reply_language_name(code: str) -> str:
    return _REPLY_LANGUAGE_NAMES.get(code, code)


def language_generation_reminder(user_text: str) -> str:
    """Short, high-salience reminder placed at end of user turn (recency bias)."""
    lang = detect_user_language(user_text)
    reminders: dict[str, str] = {
        "ko": (
            "⚠️ 필수: 이 답변 전체를 한국어로 작성하세요. "
            "제목·소제목·표 헤더·본문·면책조항까지 모두 한국어. "
            "영어 뉴스/데이터는 한국어로 설명하세요. 영어로 답하지 마세요."
        ),
        "ja": "⚠️ 必須: 回答はすべて日本語で書いてください。見出し・表・本文も日本語のみ。",
        "zh": "⚠️ 必须：请用中文撰写全部回答，包括标题、表格和正文。",
        "en": "Reply entirely in English (headings, tables, body).",
    }
    return reminders.get(lang, f"Write your entire reply in {reply_language_name(lang)} only.")


def apac_system_suffix(user_text: str = "") -> str:
    lang = detect_user_language(user_text)
    name = reply_language_name(lang)
    base = (
        f"\nMANDATORY REPLY LANGUAGE: {name}\n"
        f"- The user's latest message is in {name}. Write your entire reply in {name} only.\n"
        "- Do not reply in a different language unless they explicitly request translation.\n"
        f"\n{APAC_LANGUAGE_POLICY}\nSupported APAC: {APAC_LANGUAGE_LIST}\n"
    )
    if lang == "en":
        base += (
            "- User wrote in English: keep English even if the topic is Korea/APAC or data is mixed.\n"
        )
    elif lang == "ko":
        base += (
            "- User wrote in Korean: the FULL reply must be in Korean (한국어). "
            "Even for stock memos, market analysis, and English source data — explain in Korean.\n"
        )
    return base
