"""Structured reports for lab / GitHub portfolio surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DecisionReport:
    title: str
    domain: str
    summary: str
    decision: dict[str, Any]
    belief: dict[str, Any] = field(default_factory=dict)
    reward: float = 0.0
    coverage: int = 0
    created_at: str = field(default_factory=_now)

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title}",
            "",
            f"- domain: `{self.domain}`",
            f"- reward: **{self.reward:.3f}**",
            f"- coverage: {self.coverage}",
            f"- created: {self.created_at}",
            "",
            "## Summary",
            self.summary,
            "",
            "## Decision",
            f"```json\n{self.decision}\n```",
            "",
            "## Belief",
            f"```json\n{self.belief}\n```",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "domain": self.domain,
            "summary": self.summary,
            "decision": self.decision,
            "belief": self.belief,
            "reward": self.reward,
            "coverage": self.coverage,
            "created_at": self.created_at,
        }


@dataclass
class RedTeamReport:
    title: str
    attacks_tried: int
    novel_cells: int
    bypasses: int
    catch_rate: float
    highlights: list[str] = field(default_factory=list)
    traces: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def to_markdown(self) -> str:
        hl = "\n".join(f"- {h}" for h in self.highlights) or "- (none)"
        return "\n".join(
            [
                f"# {self.title}",
                "",
                f"- attacks_tried: {self.attacks_tried}",
                f"- novel_cells: {self.novel_cells}",
                f"- bypasses: {self.bypasses}",
                f"- catch_rate: **{self.catch_rate:.1%}**",
                f"- created: {self.created_at}",
                "",
                "## Highlights",
                hl,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "attacks_tried": self.attacks_tried,
            "novel_cells": self.novel_cells,
            "bypasses": self.bypasses,
            "catch_rate": self.catch_rate,
            "highlights": self.highlights,
            "traces": self.traces,
            "created_at": self.created_at,
        }
