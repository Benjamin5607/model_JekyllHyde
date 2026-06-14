"""Classifier adapters for moderation backends."""

from safety_eval.red_team.base import AttackMode, BaseRedTeam, RedTeamPrompt
from safety_eval.red_team.guideline import GuidelineRedTeam
from safety_eval.red_team.template import TemplateRedTeam
from safety_eval.red_team.llm import LlmRedTeam

__all__ = [
    "AttackMode",
    "BaseRedTeam",
    "RedTeamPrompt",
    "GuidelineRedTeam",
    "TemplateRedTeam",
    "LlmRedTeam",
    "build_red_team",
]


def build_red_team(name: str, **kwargs):
    name = name.lower()
    if name == "template":
        return TemplateRedTeam(**kwargs)
    if name == "llm":
        return LlmRedTeam(**kwargs)
    if name == "guideline":
        return GuidelineRedTeam(**kwargs)
    raise ValueError(f"Unknown red team: {name}. Use template, llm, or guideline.")
