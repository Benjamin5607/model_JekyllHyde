"""Search Strategy Zoo — swappable strategies for paper/benchmark comparisons."""

from __future__ import annotations

import heapq
import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from decision_architecture.engine.search.algorithms import (
    ALGORITHMS as _BASE,
    BFSSearch,
    BeamSearch,
    DFSSearch,
    EvolutionarySearch,
    GoExploreSearch,
    MCTSSearch,
    NoveltySearch,
    RandomSearch,
)
from decision_architecture.engine.search.search_base import ExpandFn, RewardFn, SearchStrategy
from decision_architecture.engine.types import Action, State


class AStarSearch(SearchStrategy):
    """Best-first with f = -reward (greedy A* over expand graph)."""

    name = "astar"

    def __init__(self) -> None:
        self._heap: list[tuple[float, int, Action, State]] = []
        self._seen: set[str] = set()
        self._seq = 0
        self._seeded = False

    def next_state(self, state, *, expand, reward):
        if not self._seeded:
            self._seen.add(state.cell_key)
            for action, nxt in expand(state):
                self._seq += 1
                heapq.heappush(self._heap, (-reward(nxt), self._seq, action, nxt))
            self._seeded = True
        while self._heap:
            _f, _s, action, nxt = heapq.heappop(self._heap)
            if nxt.cell_key in self._seen:
                continue
            self._seen.add(nxt.cell_key)
            for a2, n2 in expand(nxt):
                if n2.cell_key in self._seen:
                    continue
                self._seq += 1
                heapq.heappush(self._heap, (-reward(n2), self._seq, a2, n2))
            return action, nxt
        return None


class CoverageSearch(SearchStrategy):
    """Prefer children whose cell_key / action name is under-visited."""

    name = "coverage"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self._visits: dict[str, int] = {}

    def next_state(self, state, *, expand, reward):
        self._visits[state.cell_key] = self._visits.get(state.cell_key, 0) + 1
        children = list(expand(state))
        if not children:
            return None

        def score(item: tuple[Action, State]) -> float:
            a, s = item
            return 1.0 / (1.0 + self._visits.get(s.cell_key, 0) + self._visits.get(a.name, 0))

        children.sort(key=score, reverse=True)
        # soft random among top-3
        top = children[: max(1, min(3, len(children)))]
        action, nxt = self.rng.choice(top)
        self._visits[action.name] = self._visits.get(action.name, 0) + 1
        return action, nxt


class HybridSearch(SearchStrategy):
    """
    Round-robin / weighted mix of Go-Explore, Novelty, MCTS, Coverage.

    strategy: hybrid
    """

    name = "hybrid"

    def __init__(self, seed: int = 0, weights: dict[str, float] | None = None) -> None:
        self.rng = random.Random(seed)
        self._go = GoExploreSearch(seed=seed)
        self._nov = NoveltySearch(seed=seed)
        self._mcts = MCTSSearch(seed=seed)
        self._cov = CoverageSearch(seed=seed)
        self.weights = weights or {
            "go_explore": 0.35,
            "novelty": 0.25,
            "mcts": 0.2,
            "coverage": 0.2,
        }
        self._arms = list(self.weights.keys())
        self._inner = {
            "go_explore": self._go,
            "novelty": self._nov,
            "mcts": self._mcts,
            "coverage": self._cov,
        }
        self.last_arm: str = "go_explore"

    def _pick_arm(self) -> str:
        r = self.rng.random()
        acc = 0.0
        total = sum(self.weights.values()) or 1.0
        for name in self._arms:
            acc += self.weights[name] / total
            if r <= acc:
                return name
        return self._arms[-1]

    def next_state(self, state, *, expand, reward):
        arm = self._pick_arm()
        self.last_arm = arm
        return self._inner[arm].next_state(state, expand=expand, reward=reward)


# --- Bandit-guided frontier pick (used by Adaptive Explorer) ---


@dataclass
class BanditArm:
    name: str
    pulls: int = 0
    reward_sum: float = 0.0

    @property
    def mean(self) -> float:
        return self.reward_sum / self.pulls if self.pulls else 0.0


class UCBBandit:
    def __init__(self, arms: list[str], *, c: float = 1.4, seed: int = 0) -> None:
        self.arms = {a: BanditArm(name=a) for a in arms}
        self.c = c
        self.t = 0
        self.rng = random.Random(seed)

    def select(self) -> str:
        self.t += 1
        for arm in self.arms.values():
            if arm.pulls == 0:
                return arm.name
        best, best_s = None, -1e9
        for arm in self.arms.values():
            bonus = self.c * math.sqrt(math.log(self.t + 1) / arm.pulls)
            s = arm.mean + bonus
            if s > best_s:
                best_s, best = s, arm.name
        return best or next(iter(self.arms))

    def update(self, name: str, reward: float) -> None:
        arm = self.arms.setdefault(name, BanditArm(name=name))
        arm.pulls += 1
        arm.reward_sum += reward

    def to_dict(self) -> dict[str, Any]:
        return {
            a: {"pulls": x.pulls, "mean": x.mean} for a, x in self.arms.items()
        }


class ThompsonBandit:
    """Beta-Bernoulli Thompson sampling (reward clamped to [0,1])."""

    def __init__(self, arms: list[str], *, seed: int = 0) -> None:
        self.alpha = {a: 1.0 for a in arms}
        self.beta = {a: 1.0 for a in arms}
        self.rng = random.Random(seed)

    def select(self) -> str:
        best, best_s = None, -1.0
        for a in self.alpha:
            sample = self.rng.betavariate(self.alpha[a], self.beta[a])
            if sample > best_s:
                best_s, best = sample, a
        return best or next(iter(self.alpha))

    def update(self, name: str, reward: float) -> None:
        r = max(0.0, min(1.0, reward))
        self.alpha[name] = self.alpha.get(name, 1.0) + r
        self.beta[name] = self.beta.get(name, 1.0) + (1.0 - r)

    def to_dict(self) -> dict[str, Any]:
        return {
            a: {
                "alpha": self.alpha[a],
                "beta": self.beta[a],
                "mean": self.alpha[a] / (self.alpha[a] + self.beta[a]),
            }
            for a in self.alpha
        }


ALGORITHMS: dict[str, type[SearchStrategy]] = {
    **_BASE,
    "astar": AStarSearch,
    "a*": AStarSearch,
    "coverage": CoverageSearch,
    "hybrid": HybridSearch,
}

STRATEGY_ZOO: tuple[str, ...] = (
    "random",
    "bfs",
    "dfs",
    "beam",
    "astar",
    "go_explore",
    "novelty",
    "coverage",
    "evolutionary",
    "mcts",
    "hybrid",
)


def get_search(name: str, **kwargs: Any) -> SearchStrategy:
    key = name.lower().strip()
    if key not in ALGORITHMS:
        raise KeyError(f"Unknown search: {name}. Zoo: {list(STRATEGY_ZOO)}")
    cls = ALGORITHMS[key]
    # filter kwargs for constructors that don't take them
    try:
        return cls(**kwargs)
    except TypeError:
        return cls()
