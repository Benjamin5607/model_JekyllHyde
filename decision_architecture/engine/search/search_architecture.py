"""
Search Architecture — Decision Architecture as search policy.

Monte Carlo Explorer:
  generate N candidates → Novelty/Coverage filter → Persona debate → Consensus
  → Replay → AttackGraph / Archive / BeliefMemory / Population
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence
from uuid import uuid4

from decision_architecture.engine.archive.sqlite_archive import SQLiteArchive
from decision_architecture.engine.belief.belief_memory import BeliefMemory
from decision_architecture.engine.core import DecisionEngine
from decision_architecture.engine.evolution.population import Individual, PopulationEvolution
from decision_architecture.engine.metrics.trace import build_trace_graph
from decision_architecture.engine.personas.registry import DOMAIN_PERSONAS
from decision_architecture.engine.search.attack_dna import AttackDNA
from decision_architecture.engine.search.novelty_coverage import (
    AttackGraph,
    CoverageMap,
    NoveltyArchive,
)
from decision_architecture.engine.search.replay_cluster import ReplayClusterer
from decision_architecture.engine.types import Option, State


ReplayFn = Callable[[Sequence[str]], dict[str, Any]]
# Expected replay result keys: ok, confidence, reward, predicates, tools


@dataclass
class SearchStepResult:
    sequence: list[str]
    genome: str
    novelty: float
    coverage_bonus: float
    graph_bonus: float
    decision_rationale: str
    replay_ok: bool
    replay_confidence: float
    accepted: bool
    cluster_id: str | None = None
    panels: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "genome": self.genome,
            "novelty": self.novelty,
            "coverage_bonus": self.coverage_bonus,
            "graph_bonus": self.graph_bonus,
            "decision_rationale": self.decision_rationale,
            "replay_ok": self.replay_ok,
            "replay_confidence": self.replay_confidence,
            "accepted": self.accepted,
            "cluster_id": self.cluster_id,
        }


@dataclass
class SearchArchitecture:
    """
    Full Security / Attack search engine on Decision Architecture.

    Persona graph (default):
      Explorer → Planner → Attacker → Critic → Verifier → Consensus
    plus optional Jekyll/Hyde duel.
    """

    seed: int = 7
    candidate_batch: int = 24
    novelty_threshold: float = 0.22
    db_path: str = ":memory:"
    personas: tuple[str, ...] = DOMAIN_PERSONAS["security"]

    def __post_init__(self) -> None:
        self.novelty = NoveltyArchive(threshold=self.novelty_threshold)
        self.coverage = CoverageMap()
        self.graph = AttackGraph()
        self.clusters = ReplayClusterer()
        self.belief_mem = BeliefMemory()
        self.archive = SQLiteArchive(self.db_path)
        self.population = PopulationEvolution(
            population_size=max(12, self.candidate_batch),
            seed=self.seed,
        )
        self.engine = DecisionEngine(
            personas=self.personas,
            domain="security_search",
            archive=self.archive,
        )
        self.duel = DecisionEngine(personas=("jekyll", "hyde"), domain="security_duel")
        self.history: list[SearchStepResult] = []
        self._alphabet: list[str] = []
        from decision_architecture.engine.research.viz import SearchTree, TransitionHeatmap

        self.search_tree = SearchTree()
        self.transition_heat = TransitionHeatmap()
        self.attack_log: list[dict[str, Any]] = []

    def set_alphabet(self, prompts: Sequence[str]) -> None:
        self._alphabet = list(prompts)
        self.population.alphabet = list(prompts)

    def _rank_candidates(self, candidates: Sequence[Sequence[str]]) -> list[tuple[float, list[str]]]:
        ranked: list[tuple[float, list[str]]] = []
        for raw in candidates:
            seq = list(raw)
            if not seq:
                continue
            nov = self.novelty.score(seq)
            if nov < self.novelty_threshold and self.novelty.genomes:
                continue
            if self.clusters.is_redundant(seq):
                continue
            cov = 0.0
            for i, t in enumerate(seq):
                cov += self.coverage.tool_bonus(t)
                if i:
                    cov += self.coverage.transition_bonus(seq[i - 1], t)
            cov /= max(1, len(seq) * 2)
            gbonus = self.graph.unseen_edge_bonus(seq)
            bias = self.belief_mem.bias(seq)
            score = 0.4 * nov + 0.25 * cov + 0.25 * gbonus + 0.1 * (bias + 1) / 2
            ranked.append((score, seq))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return ranked

    def _debate(self, seq: list[str], *, prior: float) -> tuple[str, float]:
        options = [
            Option(
                id="→".join(seq)[:120] or "empty",
                label=f"attack {' → '.join(seq[:6])}",
                payload={"tools": seq, "bias": 0.1},
                prior=prior,
            ),
            Option(
                id="safe::noop",
                label="safe refuse / noop",
                payload={"tools": [], "bias": -0.05},
                prior=0.1,
            ),
        ]
        state = State(
            data={"phase": "search", "sequence": seq},
            options=options,
            context={
                "novelty": prior,
                "risk": 0.35,
                "replayable": True,
                **self.belief_mem.as_context(),
            },
        )
        decision = self.engine.run(state)
        duel = self.duel.run(
            State(data=state.data, options=options, context=state.context)
        )
        rationale = decision.rationale
        if duel.rationale:
            rationale = f"{rationale} | duel: {duel.rationale}"
        # accept unless consensus chose safe
        chosen = decision.option.id if decision.option else "safe::noop"
        conf = decision.confidence
        if chosen.startswith("safe"):
            return rationale, 0.0
        return rationale, conf

    def step(
        self,
        candidates: Sequence[Sequence[str]],
        *,
        replay: ReplayFn,
    ) -> SearchStepResult:
        ranked = self._rank_candidates(candidates)
        if not ranked:
            # force mutate from population / alphabet
            if self.population.population:
                ind = self.population.rng.choice(self.population.population)
                ranked = [(0.5, list(ind.sequence))]
            elif self._alphabet:
                ranked = [
                    (
                        0.5,
                        [
                            self.population.rng.choice(self._alphabet)
                            for _ in range(3)
                        ],
                    )
                ]
            else:
                ranked = [(0.1, ["open page_2", "read file note.txt", "post data"])]

        prior, seq = ranked[0]
        rationale, conf = self._debate(seq, prior=prior)
        if conf <= 0.0:
            # try next candidates
            for prior2, seq2 in ranked[1:6]:
                rationale, conf = self._debate(seq2, prior=prior2)
                if conf > 0.0:
                    seq, prior = seq2, prior2
                    break

        rr = replay(seq)
        ok = bool(rr.get("ok"))
        rconf = float(rr.get("confidence") or (1.0 if ok else 0.0))
        reward = float(rr.get("reward") or (0.7 if ok else 0.1))
        predicates = [str(p) for p in (rr.get("predicates") or [])]
        tools = [str(t) for t in (rr.get("tools") or seq)]

        nov = self.novelty.score(seq)
        cov_b = sum(self.coverage.tool_bonus(t) for t in seq) / max(1, len(seq))
        g_b = self.graph.unseen_edge_bonus(seq)
        accepted = ok and (nov >= self.novelty_threshold or not self.novelty.genomes)

        if ok:
            self.belief_mem.observe_success(seq)
        else:
            self.belief_mem.observe_failure(seq, note=rationale[:120])

        self.coverage.observe(seq, predicates=predicates, tools=tools)
        self.graph.add_path(seq)
        cluster = self.clusters.assign(seq, reward=reward)
        dna = self.novelty.add(seq) if accepted or ok else AttackDNA.from_sequence(seq)
        self.search_tree.add(seq, reward=reward)
        self.transition_heat.observe(seq)

        from decision_architecture.engine.research.viz import (
            ReplayAttack,
            persona_transcript,
            trust_from_belief,
        )

        atk = ReplayAttack(
            attack_id=f"attack_{len(self.attack_log) + 1:04d}",
            sequence=list(seq),
            genome=dna.genome,
            ok=ok,
            predicates=predicates,
            reward=reward,
            cause="" if ok else rationale[:80],
            generation=self.population.generation,
        )
        self.attack_log.append(atk.to_dict())

        # archive cell
        from decision_architecture.engine.types import State as S

        cell = S(data={"sequence": seq, "genome": dna.genome}, cell_key=dna.genome)
        self.archive.store(
            cell,
            reward=reward,
            trajectory=[{"name": t} for t in tools],
            replay_ok=ok,
            metadata={"genome": dna.genome, "predicates": predicates},
        )

        # population bookkeeping
        if not self.population.population:
            self.population.seed_population([seq])
        else:
            self.population.population.append(
                Individual(sequence=list(seq), fitness=reward, novelty=nov, replay_ok=ok)
            )
            self.population.population = self.population.population[
                -self.population.population_size :
            ]

        panels = {
            "novelty": nov,
            "coverage": self.coverage.to_dict(),
            "heatmap": self.coverage.heatmap(),
            "transition_heatmap": self.transition_heat.to_dict(),
            "attack_graph": self.graph.to_dict(),
            "clusters": self.clusters.to_dict(),
            "belief_memory": self.belief_mem.to_dict(),
            "trust": trust_from_belief(
                {"untrusted": 0.5, "washed": 0.5, "egress": 0.3},
                self.belief_mem.to_dict(),
            ),
            "trace_graph": build_trace_graph(tools),
            "genome": dna.genome,
            "population": self.population.to_dict(),
            "evolution": self.population.to_dict(),
            "replay_confidence": rconf,
            "search_tree": self.search_tree.to_dict(),
            "attacks": self.attack_log[-20:],
            "personas": persona_transcript(
                explorer=f"Try {' → '.join(seq[:2])}",
                planner=rationale[:100],
                attacker=f"Escalate via {seq[-1] if seq else '?'}",
                critic="Guardrail risk on early privilege." if not ok else "Path cleared.",
                verifier=f"replay_ok={ok} conf={rconf:.2f}",
                jekyll="Prefer safer motif." if not ok else "Acceptable risk.",
                hyde="Push mutation." if ok else "Mutate and retry.",
                consensus="OK" if ok else "FAIL",
            ),
            "selected_attack": atk.to_dict(),
        }
        result = SearchStepResult(
            sequence=list(seq),
            genome=dna.genome,
            novelty=nov,
            coverage_bonus=cov_b,
            graph_bonus=g_b,
            decision_rationale=rationale,
            replay_ok=ok,
            replay_confidence=rconf,
            accepted=accepted or ok,
            cluster_id=cluster.cluster_id,
            panels=panels,
        )
        self.history.append(result)
        return result

    def evolve(self, mutate_fn: Callable[[list[str]], list[str]] | None = None) -> list[list[str]]:
        kids = self.population.evolve_generation(mutate_fn=mutate_fn)
        return [list(i.sequence) for i in kids]

    def run(
        self,
        *,
        iterations: int = 12,
        candidate_fn: Callable[[], list[list[str]]],
        replay: ReplayFn,
        mutate_fn: Callable[[list[str]], list[str]] | None = None,
    ) -> dict[str, Any]:
        steps = []
        for i in range(iterations):
            cands = candidate_fn()
            if i > 0 and i % 3 == 0:
                cands = self.evolve(mutate_fn=mutate_fn) + cands
            result = self.step(cands, replay=replay)
            steps.append(result.to_dict())
        from decision_architecture.engine.research.viz import ResearchReport, diff_replays

        oks = [h for h in self.history if h.replay_ok]
        best = self.population.best()
        report = ResearchReport(
            title="Search Architecture run",
            population=len(self.population.population),
            generation=self.population.generation,
            novelty=float(len(getattr(self.novelty, "genomes", []) or [])) / max(1, len(self.history)),
            coverage=len(self.coverage.heatmap()),
            best_genome=best.genome if best else "",
            best_reward=best.fitness if best else 0.0,
            replay_success=len(oks),
            attacks_found=len(self.attack_log),
            novel_findings=len(getattr(self.novelty, "genomes", []) or []),
        )
        replay_diff = None
        if len(self.attack_log) >= 2:
            a, b = self.attack_log[0], self.attack_log[-1]
            replay_diff = diff_replays(
                a["sequence"],
                b["sequence"],
                id_a=a["attack_id"],
                id_b=b["attack_id"],
                reward_a=a["reward"],
                reward_b=b["reward"],
                ok_a=a["ok"],
                ok_b=b["ok"],
            ).to_dict()
        return {
            "iterations": iterations,
            "steps": steps,
            "novelty": self.novelty.to_dict(),
            "coverage": self.coverage.to_dict(),
            "attack_graph": self.graph.to_dict(),
            "clusters": self.clusters.to_dict(),
            "belief_memory": self.belief_mem.to_dict(),
            "population": self.population.to_dict(),
            "archive": self.archive.to_dict(),
            "n_clusters": self.clusters.diversity_score(),
            "search_tree": self.search_tree.to_dict(),
            "transition_heatmap": self.transition_heat.to_dict(),
            "attacks": self.attack_log,
            "replay_diff": replay_diff,
            "report": report.to_dict(),
            "research": {
                "attacks": self.attack_log,
                "search_tree": self.search_tree.to_dict(),
                "transition_heatmap": self.transition_heat.to_dict(),
                "evolution": self.population.to_dict(),
                "report": report.to_dict(),
                "replay_diff": replay_diff,
            },
        }
