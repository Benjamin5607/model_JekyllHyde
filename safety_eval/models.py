"""Data models for safety evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExpectedAction(str, Enum):
    BLOCK = "block"
    ALLOW = "allow"
    FLAG = "flag"


@dataclass(frozen=True)
class TestCase:
    id: str
    prompt: str
    category: str
    expected: ExpectedAction
    severity: Severity = Severity.MEDIUM
    tags: tuple[str, ...] = ()
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationResult:
    blocked: bool
    flagged: bool = False
    categories: list[str] = field(default_factory=list)
    score: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseResult:
    case: TestCase
    classification: ClassificationResult
    passed: bool
    failure_reason: str | None = None


@dataclass
class EvaluationReport:
    results: list[CaseResult]
    classifier_name: str
    dataset_path: str

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    def failures(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]

    def by_category(self) -> dict[str, list[CaseResult]]:
        grouped: dict[str, list[CaseResult]] = {}
        for result in self.results:
            grouped.setdefault(result.case.category, []).append(result)
        return grouped
