"""Debate engine — State → Persona.think → ScoreVectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from decision_architecture.engine.personas.base import Persona
from decision_architecture.engine.types import ScoreVector, State


@dataclass
class DebateTurn:
    persona: str
    round_num: int
    content: str
    vector: ScoreVector

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "round": self.round_num,
            "content": self.content,
            "vector": self.vector.to_dict(),
        }


@dataclass
class DebateResult:
    turns: list[DebateTurn] = field(default_factory=list)
    vectors: list[ScoreVector] = field(default_factory=list)
    rounds: int = 0

    @property
    def opinions(self) -> list[ScoreVector]:
        """Alias for older callers."""
        return self.vectors

    def to_dict(self) -> dict[str, Any]:
        return {
            "turns": [t.to_dict() for t in self.turns],
            "vectors": [v.to_dict() for v in self.vectors],
            "rounds": self.rounds,
        }


class DebateEngine:
    def run(self, state: State, personas: Sequence[Persona], *, rounds: int = 1) -> DebateResult:
        result = DebateResult(rounds=rounds)
        prior: list[ScoreVector] = []
        for round_num in range(1, max(1, rounds) + 1):
            for persona in personas:
                # Pass prior Jekyll score into context for Hyde narrative
                ctx_state = state
                if prior:
                    j = next((v for v in prior if v.persona == "jekyll"), None)
                    if j and j.preferred_id:
                        ctx_state = State(
                            data=state.data,
                            options=state.options,
                            belief=state.belief,
                            cell_key=state.cell_key,
                            context={
                                **state.context,
                                "jekyll_score": j.get(j.preferred_id, j.confidence),
                            },
                        )
                vector = persona.think(ctx_state)
                content = (
                    f"[{persona.name.upper()} R{round_num}] "
                    f"stance={vector.stance} pref={vector.preferred_id} "
                    f"conf={vector.confidence:.2f} → {vector.rationale}"
                )
                result.turns.append(
                    DebateTurn(
                        persona=persona.name,
                        round_num=round_num,
                        content=content,
                        vector=vector,
                    )
                )
                result.vectors.append(vector)
                prior.append(vector)
        return result


# Backward-compat name
DebateEngineCompat = DebateEngine
