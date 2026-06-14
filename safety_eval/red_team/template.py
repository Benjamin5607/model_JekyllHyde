"""Template + mutation red team generator."""

from __future__ import annotations

import itertools
import random
from pathlib import Path

import yaml

from safety_eval.models import Severity
from safety_eval.red_team.base import BaseRedTeam, RedTeamPrompt
from safety_eval.red_team.mutations import MUTATIONS, apply_mutation

DEFAULT_SEEDS = Path(__file__).resolve().parent.parent.parent / "data" / "red_team_seeds.yaml"


class TemplateRedTeam(BaseRedTeam):
    """Expand seed templates and apply evasion mutations."""

    name = "template"

    def __init__(
        self,
        seeds_path: str | Path | None = None,
        techniques: list[str] | None = None,
        seed: int | None = None,
    ):
        self.seeds_path = Path(seeds_path or DEFAULT_SEEDS)
        self.techniques = techniques or list(MUTATIONS.keys())
        self.rng = random.Random(seed)
        self._seeds = self._load_seeds()

    def _load_seeds(self) -> list[dict]:
        with self.seeds_path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return list(data.get("seeds", []))

    def _expand_seed(self, seed: dict) -> list[tuple[str, str]]:
        template = seed["template"]
        variables: dict[str, list[str]] = seed.get("variables", {})
        if not variables:
            return [(seed["id"], template)]

        keys = list(variables.keys())
        value_lists = [variables[k] for k in keys]
        expanded: list[tuple[str, str]] = []
        for combo in itertools.product(*value_lists):
            text = template
            suffix = "-".join(str(v)[:8].replace(" ", "") for v in combo)
            for key, value in zip(keys, combo):
                text = text.replace("{" + key + "}", str(value))
            expanded.append((f"{seed['id']}:{suffix}", text))
        return expanded

    def generate(
        self,
        *,
        categories: list[str] | None = None,
        count: int = 10,
        attack_modes: list[str] | None = None,
        memory=None,
    ) -> list[RedTeamPrompt]:
        _ = attack_modes, memory
        allowed = set(categories) if categories else None
        candidates: list[RedTeamPrompt] = []

        for seed in self._seeds:
            category = seed["category"]
            if allowed and category not in allowed:
                continue

            severity = Severity(str(seed.get("severity", "medium")).lower())
            for base_id, base_text in self._expand_seed(seed):
                for technique in self.techniques:
                    prompt = apply_mutation(base_text, technique, self.rng)
                    candidates.append(
                        RedTeamPrompt(
                            id=f"{base_id}:{technique}",
                            prompt=prompt,
                            category=category,
                            technique=technique,
                            severity=severity,
                            seed_id=seed["id"],
                            metadata={"base_text": base_text},
                        )
                    )

        if not candidates:
            raise ValueError("No red team prompts matched filters.")

        self.rng.shuffle(candidates)
        return candidates[:count]
