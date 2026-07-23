"""Search algorithms implementing SearchStrategy.next_state."""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from decision_architecture.engine.search.search_base import (
    ExpandFn,
    RewardFn,
    SearchResult,
    SearchStrategy,
)
from decision_architecture.engine.types import Action, State


class RandomSearch(SearchStrategy):
    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    def next_state(self, state, *, expand, reward):
        children = list(expand(state))
        if not children:
            return None
        return self.rng.choice(children)


class BFSSearch(SearchStrategy):
    name = "bfs"

    def __init__(self) -> None:
        self._q: deque[tuple[State, list[Action]]] = deque()
        self._seen: set[str] = set()
        self._seeded = False
        self._pending: list[tuple[Action, State]] = []

    def next_state(self, state, *, expand, reward):
        if not self._seeded:
            self._q.append((state, []))
            self._seen.add(state.cell_key)
            self._seeded = True
        if self._pending:
            return self._pending.pop(0)
        if not self._q:
            return None
        cur, _path = self._q.popleft()
        for action, nxt in expand(cur):
            if nxt.cell_key in self._seen:
                continue
            self._seen.add(nxt.cell_key)
            self._q.append((nxt, _path + [action]))
            self._pending.append((action, nxt))
        return self._pending.pop(0) if self._pending else None


class DFSSearch(SearchStrategy):
    name = "dfs"

    def __init__(self) -> None:
        self._stack: list[tuple[State, list[Action]]] = []
        self._seen: set[str] = set()
        self._seeded = False

    def next_state(self, state, *, expand, reward):
        if not self._seeded:
            self._stack.append((state, []))
            self._seen.add(state.cell_key)
            self._seeded = True
        if not self._stack:
            return None
        cur, path = self._stack.pop()
        children = list(expand(cur))
        picked = None
        for action, nxt in reversed(children):
            if nxt.cell_key in self._seen:
                continue
            self._seen.add(nxt.cell_key)
            self._stack.append((nxt, path + [action]))
            picked = (action, nxt)
        return picked


class BeamSearch(SearchStrategy):
    name = "beam"

    def __init__(self, beam_width: int = 4, seed: int = 0) -> None:
        self.beam_width = beam_width
        self.rng = random.Random(seed)
        self._beam: list[tuple[float, State]] = []
        self._seeded = False

    def next_state(self, state, *, expand, reward):
        if not self._seeded:
            self._beam = [(reward(state), state)]
            self._seeded = True
        if not self._beam:
            return None
        self._beam.sort(key=lambda t: t[0], reverse=True)
        _, cur = self._beam[0]
        children = list(expand(cur))
        if not children:
            self._beam.pop(0)
            return None
        scored = [(reward(n), a, n) for a, n in children]
        scored.sort(key=lambda t: t[0], reverse=True)
        self._beam = [(s, n) for s, _, n in scored[: self.beam_width]]
        s, a, n = scored[0]
        return a, n


@dataclass
class _MCTSNode:
    state: State
    action: Action | None = None
    parent: "_MCTSNode | None" = None
    children: list["_MCTSNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0

    def ucb(self, c: float = 1.4) -> float:
        if self.visits == 0:
            return float("inf")
        parent_visits = self.parent.visits if self.parent else 1
        return self.value / self.visits + c * math.sqrt(math.log(parent_visits + 1) / self.visits)


class MCTSSearch(SearchStrategy):
    name = "mcts"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self._root: _MCTSNode | None = None

    def next_state(self, state, *, expand, reward):
        if self._root is None or self._root.state.cell_key != state.cell_key:
            self._root = _MCTSNode(state=state)
        node = self._root
        while node.children:
            node = max(node.children, key=lambda n: n.ucb())
        children = list(expand(node.state))
        if not children:
            return None
        action, nxt = self.rng.choice(children)
        child = _MCTSNode(state=nxt, action=action, parent=node)
        node.children.append(child)
        r = reward(nxt)
        cur: _MCTSNode | None = child
        while cur:
            cur.visits += 1
            cur.value += r
            cur = cur.parent
        return action, nxt


class GoExploreSearch(SearchStrategy):
    name = "go_explore"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self._archive: dict[str, State] = {}
        self._visits: dict[str, int] = {}

    def next_state(self, state, *, expand, reward):
        self._archive.setdefault(state.cell_key, state)
        self._visits[state.cell_key] = self._visits.get(state.cell_key, 0) + 1
        # Prefer under-visited archive cell
        seed_key = min(self._visits, key=self._visits.get)
        seed = self._archive[seed_key]
        children = list(expand(seed))
        if not children:
            children = list(expand(state))
        if not children:
            return None
        action, nxt = self.rng.choice(children)
        self._archive[nxt.cell_key] = nxt
        self._visits.setdefault(nxt.cell_key, 0)
        return action, nxt


class NoveltySearch(SearchStrategy):
    name = "novelty"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self._seen: dict[str, int] = {}

    def next_state(self, state, *, expand, reward):
        self._seen[state.cell_key] = self._seen.get(state.cell_key, 0) + 1
        children = list(expand(state))
        if not children:
            return None

        def novelty(s: State) -> float:
            return 1.0 / (1.0 + self._seen.get(s.cell_key, 0))

        children.sort(key=lambda t: novelty(t[1]), reverse=True)
        action, nxt = children[0]
        self._seen[nxt.cell_key] = self._seen.get(nxt.cell_key, 0)
        return action, nxt


class EvolutionarySearch(SearchStrategy):
    name = "evolutionary"

    def __init__(self, seed: int = 0, mutation_rate: float = 0.5) -> None:
        self.rng = random.Random(seed)
        self.mutation_rate = mutation_rate

    def next_state(self, state, *, expand, reward):
        children = list(expand(state))
        if not children:
            return None
        if self.rng.random() < self.mutation_rate:
            return self.rng.choice(children)
        children.sort(key=lambda t: reward(t[1]), reverse=True)
        return children[0]


ALGORITHMS: dict[str, type[SearchStrategy]] = {
    "random": RandomSearch,
    "bfs": BFSSearch,
    "dfs": DFSSearch,
    "beam": BeamSearch,
    "mcts": MCTSSearch,
    "go_explore": GoExploreSearch,
    "evolutionary": EvolutionarySearch,
    "novelty": NoveltySearch,
}


def get_search(name: str, **kwargs: Any) -> SearchStrategy:
    key = name.lower()
    if key not in ALGORITHMS:
        raise KeyError(f"Unknown search: {name}. Known: {sorted(ALGORITHMS)}")
    return ALGORITHMS[key](**kwargs)
