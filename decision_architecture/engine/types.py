"""Canonical Decision Architecture types — shared by PTCG / Security / ZeroAI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import uuid4
import hashlib
import json

from decision_architecture.engine.belief.belief_state import BeliefState


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ScoreVector:
    """Persona output — one vector per think() call."""

    persona: str
    scores: dict[str, float] = field(default_factory=dict)  # option_id -> [0,1]
    preferred_id: str | None = None
    confidence: float = 0.5
    stance: str = "neutral"
    rationale: str = ""
    risks: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, option_id: str, default: float = 0.0) -> float:
        return float(self.scores.get(option_id, default))

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "scores": dict(self.scores),
            "preferred_id": self.preferred_id,
            "confidence": self.confidence,
            "stance": self.stance,
            "rationale": self.rationale,
            "risks": self.risks,
            "metadata": self.metadata,
        }


@dataclass
class Option:
    id: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)
    prior: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "payload": self.payload, "prior": self.prior}


@dataclass
class Action:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    actor: str = "agent"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "args": self.args, "actor": self.actor}


@dataclass
class State:
    """Domain-agnostic decision state."""

    data: dict[str, Any] = field(default_factory=dict)
    options: list[Option] = field(default_factory=list)
    belief: BeliefState = field(default_factory=BeliefState)
    cell_key: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cell_key:
            self.cell_key = self.compute_hash()

    def compute_hash(self) -> str:
        blob = json.dumps(
            {"data": self.data, "options": [o.id for o in self.options]},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]

    def with_updates(self, **updates: Any) -> "State":
        data = {**self.data, **updates}
        return State(
            data=data,
            options=list(self.options),
            belief=self.belief.copy(),
            context=dict(self.context),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "options": [o.to_dict() for o in self.options],
            "belief": self.belief.to_dict(),
            "cell_key": self.cell_key,
            "context": self.context,
        }


@dataclass
class Snapshot:
    state: State
    action: Action | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "state": self.state.to_dict(),
            "action": self.action.to_dict() if self.action else None,
            "metadata": self.metadata,
        }


@dataclass
class Trace:
    steps: list[dict[str, Any]] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex[:12])

    def add(self, kind: str, **payload: Any) -> None:
        self.steps.append({"kind": kind, "at": _now(), **payload})

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "steps": self.steps}


@dataclass
class Decision:
    """engine.run(state) output."""

    state: State
    option: Option | None
    score: float
    confidence: float
    rationale: str
    vectors: list[ScoreVector] = field(default_factory=list)
    belief: BeliefState = field(default_factory=BeliefState)
    reward: float = 0.0
    novelty: float = 0.0
    replay_confidence: float = 0.0
    trace: Trace = field(default_factory=Trace)
    metadata: dict[str, Any] = field(default_factory=dict)
    debate: Any = None  # DebateResult | None

    @property
    def opinions(self) -> list[ScoreVector]:
        """Alias — older demos/tests read decision.opinions."""
        return self.vectors

    def to_dict(self) -> dict[str, Any]:
        return {
            "option": self.option.to_dict() if self.option else None,
            "score": self.score,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "vectors": [v.to_dict() for v in self.vectors],
            "belief": self.belief.to_dict(),
            "reward": self.reward,
            "novelty": self.novelty,
            "replay_confidence": self.replay_confidence,
            "trace": self.trace.to_dict(),
            "metadata": self.metadata,
            "state": self.state.to_dict(),
            "debate": self.debate.to_dict() if self.debate is not None else None,
        }


# Backward-compat alias used by older modules
PersonaOpinion = ScoreVector
