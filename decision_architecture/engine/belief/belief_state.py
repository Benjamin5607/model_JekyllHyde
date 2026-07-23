"""Generalized belief state — Boss odds, injection risk, budget risk: same shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class BeliefState:
    """
    Domain-agnostic probabilistic / soft-evidence bag.

    Examples
    --------
    PTCG:      boss, judge, rare_candy
    Security:  prompt_injection, credential, email, tool
    Business:  budget, approval, risk, deadline
    """

    priors: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, float] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: float = 0.5) -> float:
        if key in self.evidence:
            return self._clamp(self.evidence[key])
        if key in self.priors:
            return self._clamp(self.priors[key])
        return default

    def set_prior(self, key: str, value: float, note: str = "") -> None:
        self.priors[key] = self._clamp(value)
        if note:
            self.notes[key] = note

    def observe(self, key: str, strength: float = 0.1) -> float:
        """Soft update toward observed strength in [0, 1]."""
        current = self.get(key)
        strength = self._clamp(abs(strength))
        target = self._clamp(strength)
        updated = current + (target - current) * min(1.0, strength + 0.05)
        self.evidence[key] = self._clamp(updated)
        return self.evidence[key]

    def update_many(self, observations: Mapping[str, float]) -> None:
        for key, value in observations.items():
            self.observe(key, value)

    def most_uncertain(self, keys: list[str] | None = None) -> str | None:
        pool = keys or list({*self.priors, *self.evidence})
        if not pool:
            return None
        return max(pool, key=lambda k: abs(0.5 - self.get(k)))

    def copy(self) -> "BeliefState":
        return BeliefState(
            priors=dict(self.priors),
            evidence=dict(self.evidence),
            notes=dict(self.notes),
        )

    def to_dict(self) -> dict[str, Any]:
        keys = sorted({*self.priors, *self.evidence})
        return {
            "priors": dict(self.priors),
            "evidence": dict(self.evidence),
            "notes": dict(self.notes),
            "posterior": {k: self.get(k) for k in keys},
        }

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))


def ptcg_belief(*, boss: float = 0.5, judge: float = 0.3, rare_candy: float = 0.4) -> BeliefState:
    b = BeliefState()
    b.set_prior("boss", boss)
    b.set_prior("judge", judge)
    b.set_prior("rare_candy", rare_candy)
    return b


def security_belief(
    *,
    prompt_injection: float = 0.4,
    credential: float = 0.3,
    email: float = 0.2,
    tool: float = 0.35,
) -> BeliefState:
    b = BeliefState()
    b.set_prior("prompt_injection", prompt_injection)
    b.set_prior("credential", credential)
    b.set_prior("email", email)
    b.set_prior("tool", tool)
    return b


def business_belief(
    *,
    budget: float = 0.5,
    approval: float = 0.4,
    risk: float = 0.5,
    deadline: float = 0.6,
) -> BeliefState:
    b = BeliefState()
    b.set_prior("budget", budget)
    b.set_prior("approval", approval)
    b.set_prior("risk", risk)
    b.set_prior("deadline", deadline)
    return b
