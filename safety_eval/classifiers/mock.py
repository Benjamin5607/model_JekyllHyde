"""Deterministic mock classifier for dry runs."""

from __future__ import annotations

from safety_eval.classifiers.base import BaseClassifier
from safety_eval.models import ClassificationResult


class MockClassifier(BaseClassifier):
    """Blocks prompts containing obvious violation markers."""

    name = "mock"

    BLOCK_MARKERS = (
        "how to make",
        "how do i hack",
        "steal credit",
        "kill myself",
        "child porn",
        "racial slur",
        "bypass filter",
    )

    def classify(self, text: str) -> ClassificationResult:
        lowered = text.lower()
        matched = [m for m in self.BLOCK_MARKERS if m in lowered]
        blocked = bool(matched)
        return ClassificationResult(
            blocked=blocked,
            flagged=blocked,
            categories=["mock_violation"] if blocked else [],
            score=0.95 if blocked else 0.05,
            raw={"matched_markers": matched},
        )
