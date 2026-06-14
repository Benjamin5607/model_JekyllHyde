"""Base classifier interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from safety_eval.models import ClassificationResult


class BaseClassifier(ABC):
    name: str = "base"

    @abstractmethod
    def classify(self, text: str) -> ClassificationResult:
        """Return moderation decision for the given text."""
