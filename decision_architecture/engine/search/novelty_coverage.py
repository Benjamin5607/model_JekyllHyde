"""Novelty + Coverage + Attack Graph — Search Architecture primitives."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from decision_architecture.engine.metrics.trace import novelty_score
from decision_architecture.engine.search.attack_dna import AttackDNA


@dataclass
class NoveltyArchive:
    """Reject near-duplicates; prefer structurally new DNA / sequences."""

    threshold: float = 0.25  # below this distance → duplicate
    genomes: list[AttackDNA] = field(default_factory=list)
    sequences: list[tuple[str, ...]] = field(default_factory=list)

    def score(self, sequence: Sequence[str]) -> float:
        dna = AttackDNA.from_sequence(sequence)
        if not self.genomes:
            return 1.0
        # novelty = min distance to archive (1 = fully novel)
        min_d = min(dna.distance(g) for g in self.genomes)
        # also jaccard on raw tokens
        jac = max(
            (novelty_score(sequence, s) for s in self.sequences),
            default=1.0,
        )
        return 0.6 * min_d + 0.4 * jac

    def is_novel(self, sequence: Sequence[str]) -> bool:
        return self.score(sequence) >= self.threshold

    def add(self, sequence: Sequence[str]) -> AttackDNA:
        dna = AttackDNA.from_sequence(sequence)
        self.genomes.append(dna)
        self.sequences.append(tuple(sequence))
        return dna

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold": self.threshold,
            "size": len(self.genomes),
            "genomes": [g.genome for g in self.genomes[-50:]],
        }


@dataclass
class CoverageMap:
    """Coverage-guided search — under-visited tools / predicates / transitions first."""

    tools: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    predicates: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    transitions: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    genomes: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def observe(
        self,
        sequence: Sequence[str],
        *,
        predicates: Iterable[str] | None = None,
        tools: Iterable[str] | None = None,
    ) -> None:
        dna = AttackDNA.from_sequence(sequence)
        self.genomes[dna.genome] += 1
        toks = list(tools) if tools is not None else list(sequence)
        for t in toks:
            self.tools[str(t)] += 1
        for a, b in zip(toks, toks[1:]):
            self.transitions[f"{a}→{b}"] += 1
        for p in predicates or []:
            self.predicates[str(p)] += 1

    def under_visited_tools(self, candidates: Sequence[str], *, limit: int = 8) -> list[str]:
        ranked = sorted(candidates, key=lambda t: self.tools.get(t, 0))
        return ranked[:limit]

    def transition_bonus(self, a: str, b: str) -> float:
        key = f"{a}→{b}"
        return 1.0 / (1.0 + self.transitions.get(key, 0))

    def tool_bonus(self, tool: str) -> float:
        return 1.0 / (1.0 + self.tools.get(tool, 0))

    def heatmap(self) -> dict[str, int]:
        return dict(self.tools)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tools": dict(self.tools),
            "predicates": dict(self.predicates),
            "transitions": dict(list(self.transitions.items())[:100]),
            "genomes": dict(self.genomes),
        }


@dataclass
class AttackGraph:
    """
    Directed attack graph:

        Email → Memory → Tool → HTTP → Leak

    Explorer prioritizes unseen edges.
    """

    nodes: set[str] = field(default_factory=set)
    edges: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    edge_payloads: dict[tuple[str, str], list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def add_path(self, sequence: Sequence[str]) -> list[tuple[str, str]]:
        dna = AttackDNA.from_sequence(sequence)
        codes = list(dna.genome) or ["Z"]
        new_edges: list[tuple[str, str]] = []
        for c in codes:
            self.nodes.add(c)
        for a, b in zip(codes, codes[1:]):
            key = (a, b)
            if self.edges[key] == 0:
                new_edges.append(key)
            self.edges[key] += 1
            if len(self.edge_payloads[key]) < 5:
                self.edge_payloads[key].append("→".join(sequence[:6]))
        return new_edges

    def unseen_edge_bonus(self, sequence: Sequence[str]) -> float:
        dna = AttackDNA.from_sequence(sequence)
        codes = list(dna.genome)
        if len(codes) < 2:
            return 0.5
        bonuses = []
        for a, b in zip(codes, codes[1:]):
            bonuses.append(1.0 / (1.0 + self.edges.get((a, b), 0)))
        return sum(bonuses) / len(bonuses)

    def prioritize_extensions(self, from_code: str, candidates: Sequence[str]) -> list[str]:
        """Prefer candidate tokens that create new outgoing edges."""

        def score(tok: str) -> float:
            code = AttackDNA.from_sequence([tok]).genome[:1] or "Z"
            return 1.0 / (1.0 + self.edges.get((from_code, code), 0))

        return sorted(candidates, key=score, reverse=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": sorted(self.nodes),
            "edges": [{"from": a, "to": b, "count": c} for (a, b), c in self.edges.items()],
            "n_edges": len(self.edges),
            "n_nodes": len(self.nodes),
        }
