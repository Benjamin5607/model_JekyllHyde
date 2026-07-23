"""Persona registry and domain graphs."""

from __future__ import annotations

from typing import Callable

from decision_architecture.engine.personas.base import Persona
from decision_architecture.engine.personas.hyde import HydePersona
from decision_architecture.engine.personas.jekyll import JekyllPersona
from decision_architecture.engine.personas.security import (
    AttackerPersona,
    CriticPersona,
    DefenderPersona,
    ExplorerPersona,
    VerifierPersona,
)
from decision_architecture.engine.personas.zeroai import (
    ExecutorPersona,
    PlannerPersona,
    ResearcherPersona,
    ReviewerPersona,
)

PersonaFactory = Callable[[], Persona]

DOMAIN_PERSONAS: dict[str, tuple[str, ...]] = {
    "ptcg": ("jekyll", "hyde"),
    "security": ("explorer", "attacker", "critic", "verifier"),
    "security_duel": ("jekyll", "hyde"),
    "zeroai": ("planner", "researcher", "reviewer", "executor"),
    "duel": ("jekyll", "hyde"),
}


class PersonaRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, PersonaFactory] = {
            "jekyll": JekyllPersona,
            "hyde": HydePersona,
            "explorer": ExplorerPersona,
            "critic": CriticPersona,
            "verifier": VerifierPersona,
            "planner": PlannerPersona,
            "attacker": AttackerPersona,
            "defender": DefenderPersona,
            "researcher": ResearcherPersona,
            "reviewer": ReviewerPersona,
            "executor": ExecutorPersona,
        }
        self._cache: dict[str, Persona] = {}

    def register(self, name: str, factory: PersonaFactory) -> None:
        self._factories[name.lower()] = factory
        self._cache.pop(name.lower(), None)

    def get(self, name: str) -> Persona:
        key = name.lower()
        if key not in self._cache:
            if key not in self._factories:
                raise KeyError(f"Unknown persona: {name}. Known: {sorted(self._factories)}")
            self._cache[key] = self._factories[key]()
        return self._cache[key]

    def list(self) -> list[str]:
        return sorted(self._factories)

    def for_domain(self, domain: str) -> list[Persona]:
        names = DOMAIN_PERSONAS.get(domain.lower())
        if not names:
            raise KeyError(f"Unknown domain: {domain}. Known: {sorted(DOMAIN_PERSONAS)}")
        return [self.get(n) for n in names]
