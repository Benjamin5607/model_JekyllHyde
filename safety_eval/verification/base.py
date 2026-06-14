"""Verification finding from a provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Support = Literal["jekyll", "hyde", "neutral", "both", "unknown"]


@dataclass
class VerificationFinding:
    provider: str
    query: str
    finding: str
    support: Support = "neutral"
    confidence: float = 0.5
    ok: bool = True
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "query": self.query,
            "finding": self.finding,
            "support": self.support,
            "confidence": self.confidence,
            "ok": self.ok,
            "error": self.error,
            "meta": self.meta,
        }


@dataclass
class VerificationReport:
    query: str
    findings: list[VerificationFinding]
    context_block: str
    providers_ok: int
    providers_failed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "findings": [f.to_dict() for f in self.findings],
            "context_block": self.context_block,
            "providers_ok": self.providers_ok,
            "providers_failed": self.providers_failed,
        }
