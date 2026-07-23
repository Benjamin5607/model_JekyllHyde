"""
Search Benchmark — compare Strategy Zoo under identical expand/reward.

Metrics: novel findings, coverage, predicate hits (proxy), time, best reward.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from decision_architecture.engine.search.config import SearchConfig
from decision_architecture.engine.search.novelty_metric import MultiNovelty
from decision_architecture.engine.search.zoo import STRATEGY_ZOO, get_search
from decision_architecture.engine.types import Action, State


ExpandFn = Callable[[State], Sequence[tuple[Action, State]]]
RewardFn = Callable[[State], float]
PredicateFn = Callable[[State], list[str]]


@dataclass
class StrategyMetrics:
    strategy: str
    visited: int = 0
    novel_cells: int = 0
    coverage: int = 0
    predicate_hits: int = 0
    best_reward: float = 0.0
    elapsed_s: float = 0.0
    novelty_mean: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "visited": self.visited,
            "novel_cells": self.novel_cells,
            "coverage": self.coverage,
            "predicate_hits": self.predicate_hits,
            "best_reward": self.best_reward,
            "elapsed_s": round(self.elapsed_s, 4),
            "novelty_mean": round(self.novelty_mean, 4),
            "efficiency": round(self.novel_cells / max(self.elapsed_s, 1e-6), 4),
            "extras": self.extras,
        }


@dataclass
class BenchmarkReport:
    rows: list[StrategyMetrics] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "results": [r.to_dict() for r in self.rows],
            "ranking_by_novel": [
                r.strategy
                for r in sorted(self.rows, key=lambda x: (x.novel_cells, x.best_reward), reverse=True)
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            "| Strategy | Novel | Coverage | Predicates | Best R | Time(s) | Eff |",
            "|----------|------:|---------:|-----------:|-------:|--------:|----:|",
        ]
        for r in self.rows:
            d = r.to_dict()
            lines.append(
                f"| {d['strategy']} | {d['novel_cells']} | {d['coverage']} | "
                f"{d['predicate_hits']} | {d['best_reward']:.3f} | {d['elapsed_s']} | {d['efficiency']} |"
            )
        return "\n".join(lines)


class SearchBenchmark:
    """Paper-style comparison harness for the Strategy Zoo."""

    def __init__(self, config: SearchConfig | None = None) -> None:
        self.config = config or SearchConfig.from_dict()

    def run(
        self,
        *,
        start: State,
        expand: ExpandFn,
        reward: RewardFn,
        predicates: PredicateFn | None = None,
        strategies: Sequence[str] | None = None,
        budget: int | None = None,
    ) -> BenchmarkReport:
        strats = list(strategies or self.config.benchmark_strategies or STRATEGY_ZOO)
        bud = int(budget or self.config.benchmark_budget)
        report = BenchmarkReport(config=self.config.to_dict())

        for name in strats:
            nov = MultiNovelty()
            seen: set[str] = set()
            pred_hits = 0
            nov_scores: list[float] = []
            t0 = time.perf_counter()
            try:
                search = get_search(name, seed=self.config.seed)
            except TypeError:
                search = get_search(name)
            result = search.search(start, expand=expand, reward=reward, budget=bud)
            for st in result.discovered:
                key = st.cell_key
                seq = [str(st.data.get("last") or key)]
                # richer sequence if path stored in data
                if isinstance(st.data.get("path"), list):
                    seq = [str(x) for x in st.data["path"]]
                preds = predicates(st) if predicates else []
                br = nov.score(seq, predicates=preds)
                nov_scores.append(br.total)
                if key not in seen:
                    seen.add(key)
                    nov.add(seq, predicates=preds)
                if preds:
                    pred_hits += 1
            elapsed = time.perf_counter() - t0
            report.rows.append(
                StrategyMetrics(
                    strategy=name,
                    visited=result.visited,
                    novel_cells=len(seen),
                    coverage=len(seen),
                    predicate_hits=pred_hits,
                    best_reward=float(result.best_reward),
                    elapsed_s=elapsed,
                    novelty_mean=(sum(nov_scores) / len(nov_scores)) if nov_scores else 0.0,
                )
            )
        return report
