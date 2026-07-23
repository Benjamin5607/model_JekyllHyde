"""Research package — paper-facing Search Architecture visualizations."""

from decision_architecture.engine.research.viz import (
    ReplayAttack,
    ReplayDiff,
    ResearchReport,
    SearchTree,
    TransitionHeatmap,
    dag_ascii,
    demo_research_bundle,
    diff_replays,
    persona_transcript,
    sequence_to_dag,
    trust_from_belief,
)
from decision_architecture.engine.research.knowledge import SearchKnowledge

__all__ = [
    "ReplayAttack",
    "ReplayDiff",
    "ResearchReport",
    "SearchKnowledge",
    "SearchTree",
    "TransitionHeatmap",
    "dag_ascii",
    "demo_research_bundle",
    "diff_replays",
    "persona_transcript",
    "sequence_to_dag",
    "trust_from_belief",
]
