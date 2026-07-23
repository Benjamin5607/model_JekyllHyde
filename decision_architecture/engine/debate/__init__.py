"""Debate package."""

from decision_architecture.engine.debate.debate_engine import DebateEngine, DebateResult, DebateTurn

# Legacy import path
from decision_architecture.engine.debate.debate_engine import DebateEngine as _E

__all__ = ["DebateEngine", "DebateResult", "DebateTurn"]
