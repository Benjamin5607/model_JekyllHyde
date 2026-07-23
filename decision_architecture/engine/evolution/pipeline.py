"""Evolution loop — Match → Log → Curate → Train → Deploy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EvolutionRecord:
    match_id: str
    domain: str
    log: dict[str, Any]
    reward: float
    curated: bool = False
    trained: bool = False
    deployed: bool = False
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "domain": self.domain,
            "log": self.log,
            "reward": self.reward,
            "curated": self.curated,
            "trained": self.trained,
            "deployed": self.deployed,
            "timestamp": self.timestamp,
        }


@dataclass
class EvolutionReport:
    records: list[EvolutionRecord] = field(default_factory=list)
    curated_count: int = 0
    mean_reward: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": [r.to_dict() for r in self.records],
            "curated_count": self.curated_count,
            "mean_reward": self.mean_reward,
        }


class EvolutionPipeline:
    """
    Self-learning skeleton shared by PTCG / Security / ZeroAI.

    Train/deploy hooks are injectable so vendor LoRA trainers (model_JekyllHyde)
    can be plugged without coupling this package to GPU stacks.
    """

    def __init__(
        self,
        *,
        reward_threshold: float = 0.55,
        train_fn: Callable[[list[EvolutionRecord]], dict[str, Any]] | None = None,
        deploy_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.reward_threshold = reward_threshold
        self.train_fn = train_fn
        self.deploy_fn = deploy_fn
        self.records: list[EvolutionRecord] = []

    def log_match(self, match_id: str, domain: str, log: dict[str, Any], reward: float) -> EvolutionRecord:
        rec = EvolutionRecord(match_id=match_id, domain=domain, log=log, reward=reward)
        self.records.append(rec)
        return rec

    def curate(self) -> list[EvolutionRecord]:
        curated = []
        for rec in self.records:
            if not rec.curated and rec.reward >= self.reward_threshold:
                rec.curated = True
                curated.append(rec)
        return curated

    def train(self) -> dict[str, Any]:
        curated = [r for r in self.records if r.curated and not r.trained]
        artifact: dict[str, Any]
        if self.train_fn:
            artifact = self.train_fn(curated)
        else:
            artifact = {
                "status": "stub",
                "n": len(curated),
                "note": "Plug vendor/model_JekyllHyde learning pipeline here",
            }
        for rec in curated:
            rec.trained = True
        return artifact

    def deploy(self, artifact: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any]
        if self.deploy_fn:
            result = self.deploy_fn(artifact)
        else:
            result = {"status": "stub_deployed", "artifact": artifact}
        for rec in self.records:
            if rec.trained:
                rec.deployed = True
        return result

    def run_cycle(self) -> EvolutionReport:
        curated = self.curate()
        artifact = self.train()
        self.deploy(artifact)
        mean_r = (
            sum(r.reward for r in self.records) / len(self.records) if self.records else 0.0
        )
        return EvolutionReport(
            records=list(self.records),
            curated_count=len(curated),
            mean_reward=mean_r,
        )
