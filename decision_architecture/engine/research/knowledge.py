"""Search Knowledge — experience table, mutation rates, research score."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


FAIL_TYPES = (
    "Guardrail",
    "Secret",
    "Authority",
    "Taint",
    "Replay mismatch",
    "Timeout",
    "No predicate",
)

MUTATIONS = (
    "+2 wash",
    "Change privilege",
    "Replace tool",
    "Delay action",
    "Change intake",
)


@dataclass
class Experience:
    dna: str
    fail_type: str
    mutation: str
    next_result: str  # PASS | FAIL
    next_fail_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dna": self.dna,
            "fail_type": self.fail_type,
            "mutation": self.mutation,
            "next_result": self.next_result,
            "next_fail_type": self.next_fail_type,
        }


@dataclass
class SearchKnowledge:
    """FAIL → Root Cause → Mutation → Result → Knowledge."""

    experiences: list[Experience] = field(default_factory=list)
    genome_children: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    genome_visits: Counter[str] = field(default_factory=Counter)
    feed: list[dict[str, Any]] = field(default_factory=list)
    runs: int = 0
    oks: int = 0
    novel: set[str] = field(default_factory=set)

    def observe_trial(self, genome: str, *, ok: bool, fail_type: str = "") -> None:
        self.runs += 1
        if ok:
            self.oks += 1
        self.novel.add(genome)
        self.genome_visits[genome] += 1
        self.feed.append(
            {
                "kind": "success" if ok else "fail",
                "genome": genome,
                "fail_type": fail_type,
            }
        )
        self.feed = self.feed[-80:]

    def observe_mutation(
        self,
        *,
        dna: str,
        fail_type: str,
        mutation: str,
        child_genome: str,
        ok: bool,
        next_fail_type: str = "",
    ) -> None:
        row = Experience(
            dna=dna,
            fail_type=fail_type,
            mutation=mutation,
            next_result="PASS" if ok else "FAIL",
            next_fail_type=next_fail_type,
        )
        self.experiences.append(row)
        if child_genome not in self.genome_children[dna]:
            self.genome_children[dna].append(child_genome)
        self.genome_visits[child_genome] += 1
        self.novel.add(child_genome)
        self.feed.append(
            {
                "kind": "mutation",
                "mutation": mutation,
                "from": fail_type,
                "result": row.next_result,
            }
        )

    def mutation_rates(self, fail_type: str | None = None) -> list[dict[str, Any]]:
        rows = [
            e
            for e in self.experiences
            if fail_type is None or e.fail_type == fail_type
        ]
        out = []
        for m in MUTATIONS:
            subset = [e for e in rows if e.mutation == m]
            trials = len(subset)
            passes = sum(1 for e in subset if e.next_result == "PASS")
            rate = passes / trials if trials else 0.0
            stars = 1 if not trials else 5 if rate >= 0.7 else 4 if rate >= 0.5 else 3 if rate >= 0.3 else 2 if rate >= 0.15 else 1
            out.append(
                {"mutation": m, "trials": trials, "passes": passes, "rate": rate, "stars": stars}
            )
        out.sort(key=lambda x: (x["rate"], x["trials"]), reverse=True)
        return out

    def recommend(self, fail_type: str) -> list[str]:
        rates = self.mutation_rates(fail_type)
        with_data = [r for r in rates if r["trials"] > 0]
        if len(with_data) >= 2:
            return [r["mutation"] for r in with_data]
        priors = {
            "Taint": ["+2 wash", "Delay action", "Change privilege"],
            "Guardrail": ["+2 wash", "Change intake", "Change privilege"],
            "Secret": ["Change privilege", "Change intake", "+2 wash"],
            "Authority": ["Change privilege", "Delay action", "+2 wash"],
            "No predicate": ["Change intake", "+2 wash", "Replace tool"],
        }
        return list(priors.get(fail_type, MUTATIONS))

    def fail_distribution(self) -> list[dict[str, Any]]:
        c: Counter[str] = Counter(e.fail_type for e in self.experiences)
        total = sum(c.values()) or 1
        return [
            {"type": t, "count": c[t], "pct": round(100.0 * c[t] / total, 1)}
            for t in FAIL_TYPES
        ]

    def genome_tree_ascii(self, root: str | None = None) -> str:
        if not self.genome_visits:
            return "(no genomes yet)"
        r = root or max(self.genome_visits, key=self.genome_visits.get)
        lines = [r]
        kids = self.genome_children.get(r, [])
        for i, c in enumerate(kids):
            last = i == len(kids) - 1
            lines.append(f"{'└──' if last else '├──'} {c}")
            for j, g in enumerate(self.genome_children.get(c, [])[:4]):
                glast = j == min(3, len(self.genome_children.get(c, [])) - 1)
                pad = "    " if last else "│   "
                lines.append(f"{pad}{'└──' if glast else '├──'} {g}")
        return "\n".join(lines)

    def research_score(self) -> dict[str, Any]:
        passes = sum(1 for e in self.experiences if e.next_result == "PASS")
        mut_success = passes / len(self.experiences) if self.experiences else 0.0
        novel_cells = len(self.novel)
        coverage_pct = min(100, int(100 * novel_cells / 24))
        replay_rate = self.oks / self.runs if self.runs else 0.0
        novelty = min(1.0, novel_cells / 40)
        knowledge_gain = min(40, passes * 2 + novel_cells)
        score = int(
            min(
                100,
                novelty * 25
                + (coverage_pct / 100) * 20
                + replay_rate * 20
                + mut_success * 20
                + (knowledge_gain / 40) * 15,
            )
        )
        return {
            "novelty": round(novelty, 2),
            "coverage_pct": coverage_pct,
            "novel_cells": novel_cells,
            "replay_rate": round(replay_rate, 2),
            "mutation_success": round(mut_success, 2),
            "knowledge_gain": knowledge_gain,
            "score": score,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiences": [e.to_dict() for e in self.experiences[-40:]],
            "mutation_rates": self.mutation_rates(),
            "fail_distribution": self.fail_distribution(),
            "genome_tree": self.genome_tree_ascii(),
            "research_score": self.research_score(),
            "feed": self.feed[-20:],
        }
