"""Benchmark metrics for Decision Architecture runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class BenchmarkMetrics:
    coverage: int = 0
    novelty_mean: float = 0.0
    reward_mean: float = 0.0
    reward_max: float = 0.0
    decisions: int = 0
    consensus_confidence_mean: float = 0.0
    replay_ok_rate: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage": self.coverage,
            "novelty_mean": self.novelty_mean,
            "reward_mean": self.reward_mean,
            "reward_max": self.reward_max,
            "decisions": self.decisions,
            "consensus_confidence_mean": self.consensus_confidence_mean,
            "replay_ok_rate": self.replay_ok_rate,
            "extras": self.extras,
        }


class BenchmarkRunner:
    def summarize(
        self,
        *,
        rewards: Sequence[float],
        confidences: Sequence[float],
        novelty_scores: Sequence[float],
        coverage: int,
        replay_oks: Sequence[bool] | None = None,
        extras: dict[str, Any] | None = None,
    ) -> BenchmarkMetrics:
        def mean(xs: Sequence[float]) -> float:
            return sum(xs) / len(xs) if xs else 0.0

        replay_ok_rate = 0.0
        if replay_oks:
            replay_ok_rate = sum(1 for x in replay_oks if x) / len(replay_oks)

        return BenchmarkMetrics(
            coverage=coverage,
            novelty_mean=mean(list(novelty_scores)),
            reward_mean=mean(list(rewards)),
            reward_max=max(rewards) if rewards else 0.0,
            decisions=len(rewards),
            consensus_confidence_mean=mean(list(confidences)),
            replay_ok_rate=replay_ok_rate,
            extras=dict(extras or {}),
        )
