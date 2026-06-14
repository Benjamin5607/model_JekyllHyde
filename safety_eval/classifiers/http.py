"""HTTP adapter for external moderation APIs."""

from __future__ import annotations

from typing import Any

import httpx

from safety_eval.classifiers.base import BaseClassifier
from safety_eval.models import ClassificationResult


class HttpClassifier(BaseClassifier):
    """
    POST text to a moderation endpoint.

    Expected JSON response shape (configurable via field mapping):
      { "blocked": true, "categories": ["violence"], "score": 0.92 }
    """

    name = "http"

    def __init__(
        self,
        url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        blocked_field: str = "blocked",
        categories_field: str = "categories",
        score_field: str = "score",
        text_field: str = "text",
    ):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        self.blocked_field = blocked_field
        self.categories_field = categories_field
        self.score_field = score_field
        self.text_field = text_field

    def classify(self, text: str) -> ClassificationResult:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {self.text_field: text}

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        blocked = bool(data.get(self.blocked_field, False))
        categories_raw = data.get(self.categories_field, [])
        categories = [str(c) for c in categories_raw] if categories_raw else []
        score_raw = data.get(self.score_field)
        score = float(score_raw) if score_raw is not None else None

        return ClassificationResult(
            blocked=blocked,
            flagged=blocked or bool(categories),
            categories=categories,
            score=score,
            raw=data,
        )
