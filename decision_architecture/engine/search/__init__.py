"""Search package — Strategy Zoo + Search Architecture + Attack Corpus."""

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
from decision_architecture.engine.search.attack_corpus import AttackCorpus, AttackRecord
from decision_architecture.engine.search.attack_dna import AttackDNA
from decision_architecture.engine.search.config import SearchConfig
from decision_architecture.engine.search.novelty_coverage import (
    AttackGraph,
    CoverageMap,
    NoveltyArchive,
)
from decision_architecture.engine.search.novelty_metric import MultiNovelty, NoveltyBreakdown
from decision_architecture.engine.search.replay_cluster import ReplayCluster, ReplayClusterer
from decision_architecture.engine.search.search_base import (
    ExpandFn,
    RewardFn,
    SearchAlgorithm,
    SearchResult,
    SearchStrategy,
)
from decision_architecture.engine.search.zoo import (
    ALGORITHMS,
    STRATEGY_ZOO,
    AStarSearch,
    CoverageSearch,
    HybridSearch,
    ThompsonBandit,
    UCBBandit,
    get_search,
)

__all__ = [
    "ALGORITHMS",
    "STRATEGY_ZOO",
    "AStarSearch",
    "AdaptiveExplorer",
    "AttackCorpus",
    "AttackDNA",
    "AttackGraph",
    "AttackRecord",
    "BFSSearch",
    "BeamSearch",
    "CoverageMap",
    "CoverageSearch",
    "DFSSearch",
    "EvolutionarySearch",
    "ExpandFn",
    "GoExploreSearch",
    "HybridSearch",
    "MCTSSearch",
    "MultiNovelty",
    "NoveltyArchive",
    "NoveltyBreakdown",
    "NoveltySearch",
    "RandomSearch",
    "ReplayCluster",
    "ReplayClusterer",
    "RewardFn",
    "SearchAlgorithm",
    "SearchArchitecture",
    "SearchConfig",
    "SearchResult",
    "SearchStepResult",
    "SearchStrategy",
    "ThompsonBandit",
    "UCBBandit",
    "get_search",
]


def __getattr__(name: str):
    if name in ("SearchArchitecture", "SearchStepResult"):
        from decision_architecture.engine.search.search_architecture import (
            SearchArchitecture,
            SearchStepResult,
        )

        return SearchArchitecture if name == "SearchArchitecture" else SearchStepResult
    if name == "AdaptiveExplorer":
        from decision_architecture.engine.search.adaptive_explorer import AdaptiveExplorer

        return AdaptiveExplorer
    raise AttributeError(name)
