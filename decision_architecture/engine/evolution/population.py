"""Population Evolution — GA over Attack DNA genomes."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from decision_architecture.engine.search.attack_dna import AttackDNA, _token_code


MutateFn = Callable[[list[str]], list[str]]


@dataclass
class Individual:
    sequence: list[str]
    fitness: float = 0.0
    genome: str = ""
    replay_ok: bool = False
    novelty: float = 0.0

    def __post_init__(self) -> None:
        if not self.genome:
            self.genome = AttackDNA.from_sequence(self.sequence).genome

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "fitness": self.fitness,
            "genome": self.genome,
            "replay_ok": self.replay_ok,
            "novelty": self.novelty,
        }


@dataclass
class PopulationEvolution:
    """
    Population → Selection → Mutation → (external Replay) → Population

    Search loop stays GA/Go-Explore; LLM only optional via mutate_fn.
    """

    population_size: int = 24
    elite: int = 4
    seed: int = 0
    alphabet: list[str] = field(default_factory=list)
    population: list[Individual] = field(default_factory=list)
    generation: int = 0

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    def seed_population(self, seeds: Sequence[Sequence[str]]) -> None:
        for s in seeds:
            self.population.append(Individual(sequence=list(s)))
        while len(self.population) < self.population_size and self.alphabet:
            n = self.rng.randint(2, 5)
            seq = [self.rng.choice(self.alphabet) for _ in range(n)]
            self.population.append(Individual(sequence=seq))
        self.population = self.population[: self.population_size]

    def update_fitness(self, index: int, *, fitness: float, replay_ok: bool, novelty: float) -> None:
        if 0 <= index < len(self.population):
            ind = self.population[index]
            ind.fitness = fitness
            ind.replay_ok = replay_ok
            ind.novelty = novelty
            ind.genome = AttackDNA.from_sequence(ind.sequence).genome

    def select_parents(self) -> list[Individual]:
        ranked = sorted(self.population, key=lambda i: i.fitness + 0.3 * i.novelty, reverse=True)
        elites = ranked[: self.elite]
        rest = ranked[self.elite :]
        # tournament
        parents = list(elites)
        while len(parents) < max(2, self.population_size // 2) and rest:
            a, b = self.rng.sample(rest, k=min(2, len(rest)))
            parents.append(a if a.fitness >= b.fitness else b)
            if len(rest) < 2:
                break
        return parents

    def crossover(self, a: Individual, b: Individual) -> list[str]:
        if not a.sequence or not b.sequence:
            return list(a.sequence or b.sequence)
        cut = self.rng.randint(1, min(len(a.sequence), len(b.sequence)))
        child = a.sequence[:cut] + b.sequence[cut:]
        return child[:8]

    def dna_mutate(self, sequence: list[str], mutate_fn: MutateFn | None = None) -> list[str]:
        if mutate_fn is not None:
            return mutate_fn(sequence)
        # DNA-level ops on tokens
        seq = list(sequence) or (["open page_2"] if not self.alphabet else [self.rng.choice(self.alphabet)])
        op = self.rng.choice(("point", "insert", "delete", "swap", "invert"))
        if op == "point" and self.alphabet:
            seq[self.rng.randrange(len(seq))] = self.rng.choice(self.alphabet)
        elif op == "insert" and self.alphabet:
            seq.insert(self.rng.randrange(len(seq) + 1), self.rng.choice(self.alphabet))
        elif op == "delete" and len(seq) > 2:
            seq.pop(self.rng.randrange(len(seq)))
        elif op == "swap" and len(seq) >= 2:
            i, j = self.rng.sample(range(len(seq)), 2)
            seq[i], seq[j] = seq[j], seq[i]
        elif op == "invert" and len(seq) >= 3:
            i = self.rng.randrange(len(seq) - 1)
            j = self.rng.randint(i + 1, len(seq))
            seq[i:j] = reversed(seq[i:j])
        return seq[:8]

    def evolve_generation(self, mutate_fn: MutateFn | None = None) -> list[Individual]:
        parents = self.select_parents()
        next_pop: list[Individual] = [
            Individual(sequence=list(p.sequence), fitness=p.fitness, novelty=p.novelty, replay_ok=p.replay_ok)
            for p in sorted(self.population, key=lambda i: i.fitness, reverse=True)[: self.elite]
        ]
        while len(next_pop) < self.population_size and parents:
            a, b = self.rng.sample(parents, k=min(2, len(parents)))
            child_seq = self.crossover(a, b)
            child_seq = self.dna_mutate(child_seq, mutate_fn=mutate_fn)
            next_pop.append(Individual(sequence=child_seq))
        self.population = next_pop[: self.population_size]
        self.generation += 1
        return list(self.population)

    def best(self) -> Individual | None:
        if not self.population:
            return None
        return max(self.population, key=lambda i: i.fitness + 0.2 * i.novelty)

    def to_dict(self) -> dict[str, Any]:
        ranked = sorted(
            self.population,
            key=lambda i: i.fitness + 0.2 * i.novelty,
            reverse=True,
        )
        best = ranked[0] if ranked else None
        return {
            "generation": self.generation,
            "size": len(self.population),
            "population": len(self.population),
            "elite": self.elite,
            "best": best.to_dict() if best else None,
            "best_reward": best.fitness if best else 0.0,
            "best_novelty": best.novelty if best else 0.0,
            "best_coverage": sum(1 for i in self.population if i.replay_ok),
            "top_genomes": [i.genome for i in ranked[:8]],
            "elite_genomes": [i.genome for i in ranked[: self.elite]],
            "genomes": [i.genome for i in self.population[:20]],
        }
