"""DecisionEngine — engine.run(state) facade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from decision_architecture.engine.archive.sqlite_archive import SQLiteArchive
from decision_architecture.engine.belief.belief_state import BeliefState
from decision_architecture.engine.consensus.weighted_consensus import WeightedConsensus
from decision_architecture.engine.debate.debate_engine import DebateEngine
from decision_architecture.engine.personas.base import Persona
from decision_architecture.engine.personas.registry import PersonaRegistry
from decision_architecture.engine.replay.replay_engine import ReplayEngine
from decision_architecture.engine.reward.scorer import RewardScorer
from decision_architecture.engine.types import Decision, Option, State, Trace

# Re-exports for package surface
from decision_architecture.engine.types import Action, Snapshot  # noqa: F401

__all__ = [
    "Action",
    "BeliefState",
    "Decision",
    "DecisionEngine",
    "Option",
    "Snapshot",
    "State",
    "Trace",
]


@dataclass
class DecisionEngine:
    """
    Common engine for PTCG / Security / ZeroAI:

        state → personas.think → consensus → decision
    """

    personas: Sequence[str] = field(default_factory=lambda: ("jekyll", "hyde"))
    registry: PersonaRegistry = field(default_factory=PersonaRegistry)
    debate_engine: DebateEngine = field(default_factory=DebateEngine)
    consensus: WeightedConsensus = field(default_factory=WeightedConsensus)
    reward: RewardScorer = field(default_factory=RewardScorer)
    replay: ReplayEngine = field(default_factory=ReplayEngine)
    archive: SQLiteArchive = field(default_factory=SQLiteArchive)
    domain: str = "generic"
    rounds: int = 1

    def resolve_personas(self, names: Iterable[str] | None = None) -> list[Persona]:
        return [self.registry.get(n) for n in (names or self.personas)]

    def run(self, state: State, *, persona_names: Sequence[str] | None = None) -> Decision:
        """One-line entry: engine.run(state) → Decision."""
        personas = self.resolve_personas(persona_names)
        trace = Trace()
        trace.add("state", cell=state.cell_key, options=[o.id for o in state.options])
        trace.add("personas", names=[p.name for p in personas])

        # Inject archive novelty into context for Hyde/Explorer
        novelty = self.archive.novelty_bonus(state.cell_key)
        state.context = {
            **state.context,
            "novelty": novelty,
            "coverage": self.archive.coverage(),
            "replayable": True,
        }

        debate = self.debate_engine.run(state, personas, rounds=self.rounds)
        for turn in debate.turns:
            trace.add(
                "debate_turn",
                speaker=turn.persona,
                round=turn.round_num,
                content=turn.content[:500],
            )

        merged = self.consensus.merge(debate, options=state.options, context=state.context)
        score = self.reward.score(merged, context=state.context, state=state)
        belief = state.belief.copy()
        if merged.option is not None:
            belief.observe(f"chose:{merged.option.id}", strength=merged.confidence)

        decision = Decision(
            state=state,
            option=merged.option,
            score=merged.score,
            confidence=merged.confidence,
            rationale=merged.rationale,
            vectors=debate.vectors,
            belief=belief,
            reward=score,
            novelty=novelty,
            replay_confidence=float(state.context.get("replay_confidence", 0.0) or 0.0),
            trace=trace,
            metadata={"domain": self.domain, **merged.metadata},
            debate=debate,
        )
        trace.add(
            "decision",
            option=decision.option.id if decision.option else None,
            reward=decision.reward,
            novelty=decision.novelty,
        )
        return decision

    # Backward-compatible decide() used by older demos
    def decide(
        self,
        options: Sequence[Option],
        *,
        context: dict[str, Any] | None = None,
        state: State | None = None,
        persona_names: Sequence[str] | None = None,
        rounds: int = 1,
    ) -> Decision:
        st = state or State(options=list(options), context=dict(context or {}))
        if options and not st.options:
            st.options = list(options)
        if context:
            st.context.update(context)
        old_rounds = self.rounds
        self.rounds = rounds
        try:
            return self.run(st, persona_names=persona_names)
        finally:
            self.rounds = old_rounds

    def decide_and_archive(self, options: Sequence[Option], *, state: State, **kwargs: Any) -> Decision:
        decision = self.decide(options, state=state, **kwargs)
        self.archive.store(
            state,
            reward=decision.reward,
            metadata={"decision": decision.to_dict()},
            replay_ok=decision.replay_confidence >= 0.5,
        )
        return decision
