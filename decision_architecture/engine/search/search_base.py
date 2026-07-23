"""SearchStrategy interface — algorithms are swappable."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from decision_architecture.engine.types import Action, State

ExpandFn = Callable[[State], Sequence[tuple[Action, State]]]
RewardFn = Callable[[State], float]


@dataclass
class SearchResult:
    algorithm: str
    visited: int
    best_state: State | None = None
    best_reward: float = 0.0
    path: list[Action] = field(default_factory=list)
    discovered: list[State] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "visited": self.visited,
            "best_reward": self.best_reward,
            "best_state": self.best_state.to_dict() if self.best_state else None,
            "path": [a.to_dict() for a in self.path],
            "discovered": len(self.discovered),
            "metadata": self.metadata,
        }


class SearchStrategy(ABC):
    """Unified search interface — swap Random / BFS / Go-Explore / MCTS freely."""

    name: str = "base"

    @abstractmethod
    def next_state(
        self,
        state: State,
        *,
        expand: ExpandFn,
        reward: RewardFn,
    ) -> tuple[Action, State] | None:
        """Pick one next (action, state) from the current frontier/policy."""
        raise NotImplementedError

    def search(
        self,
        start: State,
        *,
        expand: ExpandFn,
        reward: RewardFn,
        budget: int = 50,
        archive: Any = None,
    ) -> SearchResult:
        """Default outer loop using next_state()."""
        state = start
        path: list[Action] = []
        best_state, best_r = start, reward(start)
        discovered = [start]
        visited = 0
        for _ in range(budget):
            step = self.next_state(state, expand=expand, reward=reward)
            visited += 1
            if step is None:
                break
            action, nxt = step
            path.append(action)
            state = nxt
            discovered.append(state)
            bonus = 0.0
            if archive is not None and hasattr(archive, "novelty_bonus"):
                bonus = float(archive.novelty_bonus(state.cell_key))
                archive.store(state, reward=reward(state) + bonus)
            r = reward(state) + bonus
            if r >= best_r:
                best_r, best_state = r, state
        return SearchResult(self.name, visited, best_state, best_r, path, discovered)


# Alias
SearchAlgorithm = SearchStrategy
