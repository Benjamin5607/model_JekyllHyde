"""Persona plug-ins."""

from decision_architecture.engine.personas.base import Persona
from decision_architecture.engine.personas.registry import DOMAIN_PERSONAS, PersonaRegistry
from decision_architecture.engine.types import ScoreVector

# Compat
PersonaOpinion = ScoreVector

__all__ = ["DOMAIN_PERSONAS", "Persona", "PersonaOpinion", "PersonaRegistry", "ScoreVector"]
