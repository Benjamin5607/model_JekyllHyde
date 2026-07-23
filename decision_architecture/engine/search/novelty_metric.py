"""Multi-metric novelty for Attack Search / clustering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from decision_architecture.engine.search.attack_dna import AttackDNA
from decision_architecture.engine.metrics.trace import novelty_score


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    return novelty_score(a, b)


def _pred_distance(a: Sequence[str], b: Sequence[str]) -> float:
    return _jaccard([p.lower() for p in a], [p.lower() for p in b])


def _embed_bag(tokens: Sequence[str], dim: int = 32) -> list[float]:
    """Cheap hash embedding (no ML deps) — stable bag-of-token vector."""
    vec = [0.0] * dim
    if not tokens:
        return vec
    for t in tokens:
        h = hash(t.lower())
        vec[h % dim] += 1.0
        vec[(h // dim) % dim] += 0.5
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]


def _cosine_distance(u: Sequence[float], v: Sequence[float]) -> float:
    return 1.0 - sum(a * b for a, b in zip(u, v))


@dataclass
class NoveltyBreakdown:
    tool: float
    predicate: float
    graph: float
    embedding: float
    total: float

    def to_dict(self) -> dict[str, float]:
        return {
            "tool": self.tool,
            "predicate": self.predicate,
            "graph": self.graph,
            "embedding": self.embedding,
            "total": self.total,
        }


@dataclass
class MultiNovelty:
    """
    Novelty = w_tool * ToolDistance
            + w_pred * PredicateDistance
            + w_graph * GraphDistance
            + w_emb * EmbeddingDistance
    """

    w_tool: float = 0.3
    w_pred: float = 0.25
    w_graph: float = 0.25
    w_emb: float = 0.2
    archive_seqs: list[tuple[str, ...]] = field(default_factory=list)
    archive_preds: list[tuple[str, ...]] = field(default_factory=list)
    archive_genomes: list[str] = field(default_factory=list)

    def score(
        self,
        sequence: Sequence[str],
        *,
        predicates: Sequence[str] | None = None,
    ) -> NoveltyBreakdown:
        preds = list(predicates or [])
        if not self.archive_seqs:
            return NoveltyBreakdown(1.0, 1.0, 1.0, 1.0, 1.0)

        tool = min(_jaccard(sequence, s) for s in self.archive_seqs)
        if self.archive_preds and preds:
            pred = min(_pred_distance(preds, p) for p in self.archive_preds)
        elif preds:
            pred = 1.0
        else:
            pred = tool

        dna = AttackDNA.from_sequence(sequence)
        graph = min(
            (dna.distance(AttackDNA(genome=g)) for g in self.archive_genomes),
            default=1.0,
        )

        emb_u = _embed_bag(sequence)
        emb = min(
            (_cosine_distance(emb_u, _embed_bag(s)) for s in self.archive_seqs),
            default=1.0,
        )

        total = (
            self.w_tool * tool
            + self.w_pred * pred
            + self.w_graph * graph
            + self.w_emb * emb
        )
        return NoveltyBreakdown(tool, pred, graph, emb, total)

    def add(self, sequence: Sequence[str], *, predicates: Sequence[str] | None = None) -> None:
        self.archive_seqs.append(tuple(sequence))
        self.archive_preds.append(tuple(predicates or []))
        self.archive_genomes.append(AttackDNA.from_sequence(sequence).genome)
