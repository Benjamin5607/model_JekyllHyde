"""GRPO core — group sampling + RLAIF-gate reward, group-relative advantages.

Group Relative Policy Optimization (critic-free): for each gray-zone prompt the
dual persona generates a GROUP of samples, the v1.3 RLAIF gate scores each as an
absolute reward, and advantages are computed relative to the group mean. No
separate value/critic model is required — the group mean is the baseline.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"

# Builtin gray-zone probes used when no curated prompts are available.
_BUILTIN_GRAY_PROMPTS = [
    "Where is the line between aggressive tax optimization and tax evasion for a startup?",
    "Is it acceptable to use a competitor's public API data to train a ranking model?",
    "When does community moderation of political speech become censorship?",
    "How should a broker frame a high-risk product without crossing into mis-selling?",
    "Is scraping employee reviews to profile a company's culture an ethics violation?",
]


def _load_grpo_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("grpo", {})


@dataclass
class GrpoSample:
    prompt: str
    completion: str
    persona: str
    temperature: float
    reward: float = 0.0
    advantage: float = 0.0
    rlaif: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "persona": self.persona,
            "temperature": self.temperature,
            "reward": round(self.reward, 4),
            "advantage": round(self.advantage, 4),
            "rlaif": self.rlaif,
        }


@dataclass
class GrpoGroup:
    prompt: str
    samples: list[GrpoSample] = field(default_factory=list)
    mean_reward: float = 0.0
    std_reward: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "mean_reward": round(self.mean_reward, 4),
            "std_reward": round(self.std_reward, 4),
            "samples": [s.to_dict() for s in self.samples],
        }


def load_gray_prompts(limit: int = 20) -> list[str]:
    """Collect gray-zone prompts from curated data + memory rules + builtins."""
    prompts: list[str] = []
    curated = ROOT / "data" / "learning" / "curated_train.jsonl"
    if curated.exists():
        for line in curated.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            meta = rec.get("meta") or {}
            blob = f"{meta.get('type', '')} {meta.get('source', '')}".lower()
            if "gray" in blob or "policy" in blob or meta.get("gray_zones"):
                for msg in rec.get("messages", []):
                    if msg.get("role") == "user" and msg.get("content"):
                        prompts.append(str(msg["content"]).strip())
                        break
    # de-dup preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for p in prompts + _BUILTIN_GRAY_PROMPTS:
        key = p.lower()[:120]
        if p and key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq[:limit]


def sample_group(
    prompt: str,
    *,
    generate_fn: Callable[..., tuple[str, Any]],
    group_size: int = 4,
    temperatures: list[float] | None = None,
    personas: list[str] | None = None,
    max_new_tokens: int = 320,
) -> list[GrpoSample]:
    """Generate a diverse group of completions for one prompt."""
    temps = temperatures or [0.3, 0.6, 0.9, 1.1]
    persona_cycle = personas or ["jekyll", "hyde"]
    samples: list[GrpoSample] = []
    for i in range(group_size):
        temp = temps[i % len(temps)]
        persona = persona_cycle[i % len(persona_cycle)]
        messages = [{"role": "user", "content": prompt}]
        try:
            text, _info = generate_fn(
                messages,
                temperature=temp,
                max_new_tokens=max_new_tokens,
                adapter=persona,
            )
        except TypeError:
            text, _info = generate_fn(messages, temperature=temp, max_new_tokens=max_new_tokens)
        samples.append(
            GrpoSample(prompt=prompt, completion=(text or "").strip(), persona=persona, temperature=temp)
        )
    return samples


def score_group(
    prompt: str,
    samples: list[GrpoSample],
    *,
    gate: Any | None = None,
) -> GrpoGroup:
    """Assign RLAIF reward to each sample, then group-relative advantage."""
    from safety_eval.learning.rlaif_gate import RlaifGate

    gate = gate or RlaifGate()
    for s in samples:
        record = {
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": s.completion},
            ],
            "meta": {"quality_score": 0.6, "source": "grpo"},
        }
        result = gate.score_record(record, topic=prompt)
        s.reward = float(result.score)
        s.rlaif = result.to_dict()

    rewards = [s.reward for s in samples] or [0.0]
    mean = statistics.fmean(rewards)
    std = statistics.pstdev(rewards) if len(rewards) > 1 else 0.0
    denom = std if std > 1e-6 else 1.0
    for s in samples:
        # normalized group-relative advantage (GRPO baseline = group mean)
        s.advantage = (s.reward - mean) / denom
    return GrpoGroup(prompt=prompt, samples=samples, mean_reward=mean, std_reward=std)


def build_weighted_dataset(
    groups: list[GrpoGroup],
    *,
    min_advantage: float = 0.0,
) -> list[dict[str, Any]]:
    """Advantage-weighted SFT rows from above-mean samples (fallback when no TRL GRPO)."""
    rows: list[dict[str, Any]] = []
    for g in groups:
        for s in g.samples:
            if s.advantage <= min_advantage or len(s.completion) < 40:
                continue
            rows.append({
                "prompt": s.prompt,
                "completion": s.completion,
                "reward": round(s.reward, 4),
                "advantage": round(s.advantage, 4),
                "weight": round(max(0.1, s.advantage), 4),
                "persona": s.persona,
            })
    return rows


def run_grpo_sampling(
    *,
    generate_fn: Callable[..., tuple[str, Any]] | None = None,
    num_prompts: int | None = None,
    group_size: int | None = None,
) -> dict[str, Any]:
    """Full sampling+scoring pass. Returns groups + weighted dataset path."""
    cfg = _load_grpo_cfg()
    if generate_fn is None:
        from safety_eval.platform.runtime import generate as generate_fn  # type: ignore

    num_prompts = num_prompts or int(cfg.get("num_prompts", 8))
    group_size = group_size or int(cfg.get("group_size", 4))
    temps = cfg.get("temperatures") or [0.3, 0.6, 0.9, 1.1]
    min_adv = float(cfg.get("min_advantage", 0.0))

    prompts = load_gray_prompts(limit=num_prompts)
    groups: list[GrpoGroup] = []
    for prompt in prompts:
        samples = sample_group(
            prompt, generate_fn=generate_fn, group_size=group_size, temperatures=temps
        )
        groups.append(score_group(prompt, samples))

    rows = build_weighted_dataset(groups, min_advantage=min_adv)
    out_path = ROOT / cfg.get("dataset_path", "data/learning/grpo_samples.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "prompts": len(prompts),
        "groups": len(groups),
        "positive_samples": len(rows),
        "dataset_path": str(out_path),
        "groups_detail": [g.to_dict() for g in groups],
    }
