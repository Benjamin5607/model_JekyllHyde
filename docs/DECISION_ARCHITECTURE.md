# Decision Architecture → Search Architecture (JekyllHyde Engine)

```text
model_JekyllHyde
│
├── Research 1 — Pokémon TCG          ✓ Decision Architecture verified
├── Research 2 — AI Agent Security    ← current focus (Search Architecture)
├── Research 3 — ZeroAI Multi-Agent
└── Research 4 — Autonomous Decision Engine
```

PTCG is a completed reference case ("Decision Architecture works in a real game").
Capital now goes into **Agent Attack Search** on the same engine.

## Canonical entry

```python
decision = engine.run(state)  # Persona.think → Debate → Consensus → Decision
```

Search Architecture (Security):

```text
Explorer → Novelty + Coverage → Candidates
  → Planner → Attacker → Critic → Verifier → Consensus (+ Jekyll/Hyde)
  → Replay → Attack Graph → Population / DNA Mutation → Explorer
```

LLM is for **Mutation only** — never the search loop.

## Surfaces

| Module | Role |
|--------|------|
| `Persona.think` | ScoreVector plug-in |
| `SearchStrategy` | Random → BFS → Go-Explore → MCTS |
| `SearchArchitecture` | Monte Carlo + Novelty + Coverage + Graph + GA |
| `AttackDNA` | Genome for clustering / mutation (`ERPH` …) |
| `ReplayEngine` + `SQLiteArchive` | Replay confidence + cells |
| `BeliefMemory` | Motif fail/success search bias |
| `PopulationEvolution` | Selection → crossover → DNA mutate |

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
