"""Search package — SearchStrategy.next_state + Search Architecture."""

from decision_architecture.engine.search.algorithms import ALGORITHMS, get_search
from decision_architecture.engine.search.algorithms import (
    BFSSearch,
    BeamSearch,
    DFSSearch,
    EvolutionarySearch,
    GoExploreSearch,
    MCTSSearch,
    NoveltySearch,
    RandomSearch,
)
from decision_architecture.engine.search.attack_dna import AttackDNA
from decision_architecture.engine.search.novelty_coverage import (
    AttackGraph,
    CoverageMap,
    NoveltyArchive,
)
from decision_architecture.engine.search.replay_cluster import ReplayCluster, ReplayClusterer
from decision_architecture.engine.search.search_base import (
    ExpandFn,
    RewardFn,
    SearchAlgorithm,
    SearchResult,
    SearchStrategy,
)

__all__ = [
    "ALGORITHMS",
    "AttackDNA",
    "AttackGraph",
    "BFSSearch",
    "BeamSearch",
    "CoverageMap",
    "DFSSearch",
    "EvolutionarySearch",
    "ExpandFn",
    "GoExploreSearch",
    "MCTSSearch",
    "NoveltyArchive",
    "NoveltySearch",
    "RandomSearch",
    "ReplayCluster",
    "ReplayClusterer",
    "RewardFn",
    "SearchAlgorithm",
    "SearchArchitecture",
    "SearchResult",
    "SearchStepResult",
    "SearchStrategy",
    "get_search",
]


def __getattr__(name: str):
    if name in ("SearchArchitecture", "SearchStepResult"):
        from decision_architecture.engine.search.search_architecture import (
            SearchArchitecture,
            SearchStepResult,
        )

        return SearchArchitecture if name == "SearchArchitecture" else SearchStepResult
    raise AttributeError(name)
