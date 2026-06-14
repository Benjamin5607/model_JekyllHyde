"""Match topic to active guideline sections."""

from __future__ import annotations

import re

from safety_eval.verification.base import VerificationFinding


def verify(
    *,
    query: str,
    text: str,
    topic: str,
    guidelines_text: str,
    guidelines_title: str,
    prior_turns: list,
    **_,
) -> VerificationFinding:
    if not guidelines_text.strip():
        return VerificationFinding(
            provider="local_guidelines",
            query=query,
            finding="No active guidelines loaded.",
            support="neutral",
            confidence=0.3,
            ok=True,
        )

    sections: list[tuple[str, str]] = []
    current = "General"
    buf: list[str] = []
    for line in guidelines_text.splitlines():
        if line.startswith("#"):
            if buf:
                sections.append((current, "\n".join(buf)))
                buf = []
            current = line.lstrip("#").strip()
        else:
            buf.append(line)
    if buf:
        sections.append((current, "\n".join(buf)))

    combined = f"{topic} {query} {text}".lower()
    best = ("General", "", 0)
    for title, body in sections:
        score = sum(1 for w in re.findall(r"[a-z]{4,}", title.lower()) if w in combined)
        score += sum(1 for w in re.findall(r"[a-z]{4,}", body.lower())[:50] if w in combined)
        if score > best[2]:
            best = (title, body[:300], score)

    title, snippet, score = best
    support = "jekyll" if score > 0 else "neutral"
    return VerificationFinding(
        provider="local_guidelines",
        query=query,
        finding=f"Relevant section: '{title}'. Snippet: {snippet[:200]}...",
        support=support,
        confidence=min(0.95, 0.4 + score * 0.1),
        ok=True,
        meta={"section": title, "score": score},
    )
