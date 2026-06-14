"""Jekyll & Hyde co-evolution session."""

from __future__ import annotations

from dataclasses import dataclass, field

from safety_eval.arena import ArenaReport, run_arena
from safety_eval.classifiers.base import BaseClassifier
from safety_eval.classifiers.keyword import KeywordClassifier
from safety_eval.memory import HydeMemory, JekyllMemory
from safety_eval.red_team.base import BaseRedTeam


@dataclass
class EvolutionRound:
    round_number: int
    report: ArenaReport
    hyde_generation: int
    jekyll_generation: int
    new_escapes: int
    new_learnings: int


@dataclass
class EvolutionSession:
    guidelines: str
    hyde_backend: str
    jekyll_backend: str
    rounds: list[EvolutionRound] = field(default_factory=list)
    hyde_memory: HydeMemory = field(default_factory=HydeMemory)
    jekyll_memory: JekyllMemory = field(default_factory=JekyllMemory)

    @property
    def final_catch_rate(self) -> float:
        if not self.rounds:
            return 0.0
        return self.rounds[-1].report.catch_rate

    def catch_rate_trend(self) -> list[float]:
        return [r.report.catch_rate for r in self.rounds]


def _apply_jekyll_learning(jekyll: BaseClassifier, memory: JekyllMemory) -> int:
    added = 0
    if isinstance(jekyll, KeywordClassifier):
        for pattern in memory.learned_patterns:
            bucket = jekyll.rules.setdefault("jekyll_learned", [])
            if pattern not in bucket:
                bucket.append(pattern)
                added += 1
    elif hasattr(jekyll, "learned_notes"):
        jekyll.learned_notes = memory.llm_defense_notes()
        added = len(memory.missed)
    return added


def _bind_hyde_memory(hyde: BaseRedTeam, memory: HydeMemory) -> None:
    if hasattr(hyde, "hyde_memory"):
        hyde.hyde_memory = memory


def run_evolution(
    hyde: BaseRedTeam,
    jekyll: BaseClassifier,
    *,
    guidelines_title: str = "",
    rounds: int = 3,
    count_per_round: int = 15,
    categories: list[str] | None = None,
    attack_modes: list[str] | None = None,
) -> EvolutionSession:
    session = EvolutionSession(
        guidelines=guidelines_title,
        hyde_backend=hyde.name,
        jekyll_backend=jekyll.name,
    )

    for round_num in range(1, rounds + 1):
        session.hyde_memory.generation = round_num - 1
        session.jekyll_memory.generation = round_num - 1
        _bind_hyde_memory(hyde, session.hyde_memory)
        _apply_jekyll_learning(jekyll, session.jekyll_memory)

        report = run_arena(
            hyde,
            jekyll,
            categories=categories,
            count=count_per_round,
            attack_modes=attack_modes,
            hyde_label="Hyde",
            jekyll_label="Jekyll",
        )

        new_escapes = 0
        for duel in report.bypasses():
            session.hyde_memory.record_escape(duel.attack)
            session.jekyll_memory.record_miss(duel.attack)
            new_escapes += 1

        new_learnings = _apply_jekyll_learning(jekyll, session.jekyll_memory)

        session.rounds.append(
            EvolutionRound(
                round_number=round_num,
                report=report,
                hyde_generation=round_num - 1,
                jekyll_generation=round_num - 1,
                new_escapes=new_escapes,
                new_learnings=new_learnings,
            )
        )

        session.hyde_memory.generation = round_num
        session.jekyll_memory.generation = round_num

    return session
