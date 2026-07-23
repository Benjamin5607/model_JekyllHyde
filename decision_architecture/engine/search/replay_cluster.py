"""Replay clustering — group similar attacks; keep cluster diversity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from decision_architecture.engine.search.attack_dna import AttackDNA


@dataclass
class ReplayCluster:
    cluster_id: str
    genome: str
    members: list[tuple[str, ...]] = field(default_factory=list)
    best_reward: float = 0.0
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "genome": self.genome,
            "count": self.count,
            "best_reward": self.best_reward,
            "sample": list(self.members[0]) if self.members else [],
        }


@dataclass
class ReplayClusterer:
    """Cluster by Attack DNA genome (exact) + soft merge by distance."""

    merge_distance: float = 0.2
    clusters: dict[str, ReplayCluster] = field(default_factory=dict)

    def assign(self, sequence: Sequence[str], *, reward: float = 0.0) -> ReplayCluster:
        dna = AttackDNA.from_sequence(sequence)
        # soft merge into nearest existing genome
        best_id, best_d = None, 1.0
        for cid, cl in self.clusters.items():
            d = dna.distance(AttackDNA(genome=cl.genome))
            if d < best_d:
                best_d, best_id = d, cid
        if best_id is not None and best_d <= self.merge_distance:
            cl = self.clusters[best_id]
        else:
            cid = dna.genome or "Z"
            # unique id if collision with different soft cluster
            n = sum(1 for c in self.clusters if c.startswith(cid))
            key = cid if n == 0 else f"{cid}_{n}"
            cl = ReplayCluster(cluster_id=key, genome=dna.genome)
            self.clusters[key] = cl
        cl.members.append(tuple(sequence))
        cl.count += 1
        cl.best_reward = max(cl.best_reward, reward)
        return cl

    def is_redundant(self, sequence: Sequence[str], *, max_per_cluster: int = 8) -> bool:
        dna = AttackDNA.from_sequence(sequence)
        for cl in self.clusters.values():
            if dna.distance(AttackDNA(genome=cl.genome)) <= self.merge_distance:
                return cl.count >= max_per_cluster
        return False

    def diversity_score(self) -> float:
        return float(len(self.clusters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_clusters": len(self.clusters),
            "clusters": [c.to_dict() for c in list(self.clusters.values())[:40]],
        }
