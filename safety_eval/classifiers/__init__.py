"""Classifier adapters for moderation backends."""

from safety_eval.classifiers.base import BaseClassifier
from safety_eval.classifiers.http import HttpClassifier
from safety_eval.classifiers.keyword import KeywordClassifier
from safety_eval.classifiers.mock import MockClassifier

__all__ = [
    "BaseClassifier",
    "HttpClassifier",
    "KeywordClassifier",
    "MockClassifier",
    "build_classifier",
]


def build_classifier(name: str, **kwargs) -> BaseClassifier:
    name = name.lower()
    if name == "mock":
        return MockClassifier(**kwargs)
    if name == "keyword":
        return KeywordClassifier(**kwargs)
    if name == "http":
        return HttpClassifier(**kwargs)
    raise ValueError(f"Unknown classifier: {name}. Use mock, keyword, or http.")
