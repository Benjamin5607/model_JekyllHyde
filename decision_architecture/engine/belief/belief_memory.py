"""Belief Memory — remember which motifs fail / succeed for search bias."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from decision_architecture.engine.search.attack_dna import AttackDNA


@dataclass
class BeliefMemory:
    """
    Soft evidence bag for search policy (not just decision-time BeliefState).

    Example: motif 'SPH' failed → explorer down-ranks Summary→Plan→HTTP chains.
    """

    motif_fail: dict[str, float] = field(default_factory=dict)
    motif_success: dict[str, float] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

    def observe_failure(self, sequence: Sequence[str], *, strength: float = 0.3, note: str = "") -> None:
        dna = AttackDNA.from_sequence(sequence)
        g = dna.genome
        self.motif_fail[g] = min(1.0, self.motif_fail.get(g, 0.0) + strength)
        # also mark bigrams
        for i in range(len(g) - 1):
            bi = g[i : i + 2]
            self.motif_fail[bi] = min(1.0, self.motif_fail.get(bi, 0.0) + strength * 0.5)
        if note:
            self.notes[g] = note

    def observe_success(self, sequence: Sequence[str], *, strength: float = 0.4) -> None:
        dna = AttackDNA.from_sequence(sequence)
        g = dna.genome
        self.motif_success[g] = min(1.0, self.motif_success.get(g, 0.0) + strength)
        for i in range(len(g) - 1):
            bi = g[i : i + 2]
            self.motif_success[bi] = min(1.0, self.motif_success.get(bi, 0.0) + strength * 0.5)

    def bias(self, sequence: Sequence[str]) -> float:
        """Positive → prefer; negative → avoid. Range roughly [-1, 1]."""
        dna = AttackDNA.from_sequence(sequence)
        g = dna.genome
        s = self.motif_success.get(g, 0.0)
        f = self.motif_fail.get(g, 0.0)
        for i in range(len(g) - 1):
            bi = g[i : i + 2]
            s += 0.25 * self.motif_success.get(bi, 0.0)
            f += 0.25 * self.motif_fail.get(bi, 0.0)
        return max(-1.0, min(1.0, s - f))

    def as_context(self) -> dict[str, Any]:
        return {
            "belief_memory": {
                "fail": dict(list(self.motif_fail.items())[:30]),
                "success": dict(list(self.motif_success.items())[:30]),
                "notes": dict(self.notes),
            }
        }

    def to_dict(self) -> dict[str, Any]:
        return self.as_context()["belief_memory"]
