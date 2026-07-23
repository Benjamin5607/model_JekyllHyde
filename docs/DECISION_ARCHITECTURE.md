# Decision Architecture (JekyllHyde Engine)

Generalized multi-persona decision engine. Pokemon TCG was demo #1;
**AI Agent Security (Kaggle)** is demo #2; ZeroAI multi-agent is the product.

Canonical entry:

```python
decision = engine.run(state)  # Persona.think → Debate → Consensus → Decision
```

```text
state → Personas → Debate → Consensus → Reward → Belief → Archive / Search / Replay
```

## Domain persona graphs

| Domain | Personas |
|--------|----------|
| PTCG | Jekyll, Hyde |
| Security | Explorer, Attacker, Critic, Verifier (+ Jekyll/Hyde duel) |
| ZeroAI | Planner, Researcher, Reviewer, Executor |

## Core surfaces

- `Persona.think(state) -> ScoreVector`
- `SearchStrategy.next_state(...)` (Random → BFS → Go-Explore → MCTS …)
- `ReplayEngine` + `SQLiteArchive` (hash / coverage / replay_ok / novelty)
- Mutation helpers (`RuleMutator` / optional `LLMMutator`) — **LLM mutates, does not search**

## Sync rule

Durable engine modules under `decision_architecture/` in the lab should be
committed to **Benjamin5607/model_JekyllHyde**. Lab may prototype first, then:

```powershell
.\scripts\sync_vendor.ps1 -Target jekyll_hyde
cd vendor\model_JekyllHyde
git status
```

Kaggle `attack.py` stays competition-owned (self-contained) unless explicitly
promoted into this package API.
