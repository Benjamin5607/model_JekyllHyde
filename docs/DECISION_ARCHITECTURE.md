# Decision Architecture → Search Architecture (JekyllHyde Engine)

```text
model_JekyllHyde
│
├── Research 1 — Pokémon TCG          ✓ Decision Architecture verified
├── Research 2 — AI Agent Security    ← Search Architecture (Attack Search)
├── Research 3 — ZeroAI Multi-Agent
└── Research 4 — Autonomous Decision Engine
```

Paper framing: **Search Architecture for Tool-Using AI Agents**
(Decision / Security / Evolution engines hang under Search.)

## Canonical entry

```python
decision = engine.run(state)  # Persona.think → Debate → Consensus → Decision
```

Search Architecture (Security):

```text
Explorer (UCB/Thompson) → Attack Corpus → Candidates
  → Planner → Attacker → Critic/Inspector → Verifier → Consensus
  → Replay → Attack Graph → Genome Mutate/Crossover → Explorer
```

LLM is for **Mutation only** — never the search loop.

## Strategy Zoo (`configs/search.yaml`)

```yaml
strategy: hybrid   # random | bfs | dfs | beam | astar | go_explore
                   # novelty | coverage | evolutionary | mcts | hybrid
```

Benchmark:

```bash
python -m decision_architecture.engine.benchmark.cli_search --budget 40
# or: search-bench --config configs/search.yaml
```

## Surfaces

| Module | Role |
|--------|------|
| `SearchStrategy` / Zoo | 11 swappable algorithms |
| `AttackCorpus` | Thousands of seed attack cells |
| `AttackDNA` | Genome + crossover + point_mutate |
| `MultiNovelty` | Tool + Predicate + Graph + Embedding |
| `ReplayInspector` | Fail → cause → hypothesis → mutation plan |
| `AdaptiveExplorer` | Corpus + Bandit + Inspector |
| `SearchBenchmark` | Paper-style strategy comparison |
| `SearchArchitecture` | Monte Carlo loop + GA archive |
| `BeliefMemory` / `PopulationEvolution` | Bias + DNA evolution |

## Domain persona graphs

| Domain | Personas |
|--------|----------|
| PTCG | Jekyll, Hyde |
| Security / Search | Explorer, Planner, Attacker, Critic, Verifier (+ Jekyll/Hyde duel) |
| ZeroAI | Planner, Researcher, Reviewer, Executor |

## Sync

```powershell
.\scripts\sync_vendor.ps1 -Target jekyll_hyde
cd vendor\model_JekyllHyde
git status
```

Kaggle `attack.py` stays self-contained for submission.
