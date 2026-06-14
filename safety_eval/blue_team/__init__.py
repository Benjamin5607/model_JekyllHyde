"""Blue team moderation backends."""

from pathlib import Path

from safety_eval.blue_team.llm import LlmBlueTeam
from safety_eval.classifiers import build_classifier
from safety_eval.classifiers.base import BaseClassifier
from safety_eval.guidelines import load_guidelines

__all__ = ["LlmBlueTeam", "build_blue_team"]


def build_blue_team(name: str, guidelines_path: str | Path | None = None, **kwargs) -> BaseClassifier:
    guidelines_text = None
    if guidelines_path:
        guidelines_text = load_guidelines(guidelines_path).text

    name = name.lower()
    if name == "llm":
        if guidelines_text:
            kwargs["guidelines_text"] = guidelines_text
        return LlmBlueTeam(**kwargs)
    return build_classifier(name, **kwargs)
