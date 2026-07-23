"""Weighted consensus — merge ScoreVectors into one Decision draft."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from decision_architecture.engine.debate.debate_engine import DebateResult
from decision_architecture.engine.types import Option


@dataclass
class ConsensusResult:
    option: Option | None
    score: float
    confidence: float
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


class WeightedConsensus:
    DEFAULT_WEIGHTS: dict[str, float] = {
        "jekyll": 1.1,
        "hyde": 1.0,
        "explorer": 0.9,
        "attacker": 1.0,
        "critic": 1.05,
        "verifier": 1.15,
        "planner": 1.0,
        "researcher": 0.95,
        "reviewer": 1.1,
        "executor": 0.9,
        "defender": 1.2,
    }

    def __init__(self, weights: Mapping[str, float] | None = None) -> None:
        self.weights = dict(self.DEFAULT_WEIGHTS)
        if weights:
            self.weights.update(weights)

    def merge(
        self,
        debate: DebateResult,
        *,
        options: Sequence[Option],
        context: Mapping[str, Any] | None = None,
    ) -> ConsensusResult:
        tallies: dict[str, float] = defaultdict(float)
        conf_sum: dict[str, float] = defaultdict(float)
        by_id = {o.id: o for o in options}

        for vector in debate.vectors:
            w = self.weights.get(vector.persona, 1.0)
            for opt_id, score in vector.scores.items():
                tallies[opt_id] += w * score * vector.confidence
                conf_sum[opt_id] += w * vector.confidence
            if vector.preferred_id and vector.preferred_id not in vector.scores:
                tallies[vector.preferred_id] += w * vector.confidence
                conf_sum[vector.preferred_id] += w * vector.confidence

        if not tallies:
            return ConsensusResult(
                option=None,
                score=0.0,
                confidence=0.0,
                rationale="합의 실패 — 후보 없음.",
                metadata={"context_keys": list((context or {}).keys())},
            )

        winner_id = max(tallies, key=lambda k: tallies[k])
        winner = by_id.get(winner_id)
        score = tallies[winner_id] / max(conf_sum[winner_id], 1e-6)
        confidence = min(0.99, conf_sum[winner_id] / max(len(debate.vectors), 1))
        dissent = [
            v.persona
            for v in debate.vectors
            if v.preferred_id and v.preferred_id != winner_id and v.confidence >= 0.6
        ]
        bits = [v.rationale for v in debate.vectors if v.preferred_id == winner_id]
        rationale = " / ".join(bits[:3]) or "가중 투표 합의."
        if dissent:
            rationale += f" (dissent: {', '.join(sorted(set(dissent)))})"
        # Narrative: if Jekyll low + Hyde high → "Replay해보자"
        j = next((v for v in debate.vectors if v.persona == "jekyll"), None)
        h = next((v for v in debate.vectors if v.persona == "hyde"), None)
        if j and h and j.get(winner_id, 0) < 0.55 and h.get(winner_id, 0) >= 0.55:
            rationale = "Replay해보자. " + rationale

        return ConsensusResult(
            option=winner,
            score=float(max(0.0, min(1.0, score))),
            confidence=float(confidence),
            rationale=rationale,
            metadata={"tallies": dict(tallies), "dissent": dissent},
        )


# Alias
ConsensusEngine = WeightedConsensus
