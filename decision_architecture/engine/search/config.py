"""Search config — YAML/JSON strategy selection for zoo + benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "strategy": "hybrid",
    "budget": 50,
    "seed": 0,
    "bandit": "ucb",  # ucb | thompson | none
    "novelty_threshold": 0.22,
    "corpus_prefer_tags": ["wash", "marker"],
    "benchmark": {
        "strategies": [
            "random",
            "bfs",
            "beam",
            "astar",
            "go_explore",
            "novelty",
            "coverage",
            "evolutionary",
            "mcts",
            "hybrid",
        ],
        "budget": 40,
        "repeats": 1,
    },
}


@dataclass
class SearchConfig:
    strategy: str = "hybrid"
    budget: int = 50
    seed: int = 0
    bandit: str = "ucb"
    novelty_threshold: float = 0.22
    corpus_prefer_tags: list[str] = field(default_factory=lambda: ["wash", "marker"])
    benchmark_strategies: list[str] = field(default_factory=list)
    benchmark_budget: int = 40
    benchmark_repeats: int = 1
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None = None) -> "SearchConfig":
        d = {**DEFAULT_CONFIG, **(data or {})}
        bench = dict(DEFAULT_CONFIG["benchmark"])
        bench.update(d.get("benchmark") or {})
        return cls(
            strategy=str(d.get("strategy") or "hybrid"),
            budget=int(d.get("budget") or 50),
            seed=int(d.get("seed") or 0),
            bandit=str(d.get("bandit") or "ucb"),
            novelty_threshold=float(d.get("novelty_threshold") or 0.22),
            corpus_prefer_tags=list(d.get("corpus_prefer_tags") or ["wash", "marker"]),
            benchmark_strategies=list(bench.get("strategies") or []),
            benchmark_budget=int(bench.get("budget") or 40),
            benchmark_repeats=int(bench.get("repeats") or 1),
            raw=d,
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SearchConfig":
        if path is None:
            return cls.from_dict()
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        data: dict[str, Any]
        if p.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore

                data = yaml.safe_load(text) or {}
            except Exception:
                data = _parse_simple_yaml(text)
        else:
            import json

            data = json.loads(text)
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "budget": self.budget,
            "seed": self.seed,
            "bandit": self.bandit,
            "novelty_threshold": self.novelty_threshold,
            "corpus_prefer_tags": self.corpus_prefer_tags,
            "benchmark": {
                "strategies": self.benchmark_strategies,
                "budget": self.benchmark_budget,
                "repeats": self.benchmark_repeats,
            },
        }


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML subset parser (no PyYAML required)."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    pending_list_key: str | None = None
    pending_list_indent = 0
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while stack and indent < stack[-1][0]:
            stack.pop()
            pending_list_key = None
        cur = stack[-1][1]
        if line.startswith("- "):
            item = line[2:].strip().strip("\"'")
            if pending_list_key is not None:
                cur.setdefault(pending_list_key, []).append(_coerce(item))
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                nxt: dict[str, Any] = {}
                cur[key] = nxt
                stack.append((indent + 2, nxt))
                pending_list_key = None
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                cur[key] = [_coerce(x.strip()) for x in inner.split(",") if x.strip()] if inner else []
                pending_list_key = None
            else:
                cur[key] = _coerce(val.strip("\"'"))
                pending_list_key = key
                pending_list_indent = indent
    return root


def _coerce(v: str) -> Any:
    if v.lower() in {"true", "yes"}:
        return True
    if v.lower() in {"false", "no"}:
        return False
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v
