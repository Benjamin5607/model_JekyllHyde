"""CLI: search-bench — run Strategy Zoo comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from decision_architecture.engine.benchmark.search_bench import SearchBenchmark
from decision_architecture.engine.search.config import SearchConfig
from decision_architecture.engine.types import Action, State


def _toy_expand(state: State):
    n = int(state.data.get("n", 0))
    path = list(state.data.get("path") or [])
    moves = ["email", "web", "read", "wash", "http", "shell", "delete", "memory"]
    out = []
    for m in moves:
        action = Action(name=m, args={})
        nxt_path = path + [m]
        nxt = State(
            data={"n": n + 1, "last": m, "path": nxt_path},
            cell_key="|".join(nxt_path[-4:]) or m,
        )
        out.append((action, nxt))
    return out


def _toy_reward(state: State) -> float:
    path = state.data.get("path") or []
    score = 0.1 * len(path)
    if "wash" in path and "http" in path:
        score += 0.5
    if "email" in path and "delete" in path:
        score += 0.4
    if "memory" in path and "shell" in path:
        score += 0.35
    return score


def _toy_predicates(state: State) -> list[str]:
    path = set(state.data.get("path") or [])
    preds = []
    if "http" in path and ("email" in path or "web" in path):
        preds.append("UNTRUSTED_TO_ACTION")
    if "delete" in path:
        preds.append("DESTRUCTIVE_WRITE")
    if "http" in path and "wash" in path:
        preds.append("EXFILTRATION")
    return preds


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Search Strategy Zoo benchmark")
    p.add_argument("--config", default="configs/search.yaml")
    p.add_argument("--budget", type=int, default=None)
    p.add_argument("--json-out", default=None)
    p.add_argument("--md-out", default=None)
    args = p.parse_args(argv)

    cfg_path = Path(args.config)
    config = SearchConfig.load(cfg_path) if cfg_path.exists() else SearchConfig.from_dict()
    if args.budget:
        config.benchmark_budget = args.budget

    bench = SearchBenchmark(config)
    start = State(data={"n": 0, "path": []}, cell_key="root")
    report = bench.run(
        start=start,
        expand=_toy_expand,
        reward=_toy_reward,
        predicates=_toy_predicates,
    )
    md = report.to_markdown()
    print(md)
    print("ranking:", ", ".join(report.to_dict()["ranking_by_novel"]))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    if args.md_out:
        Path(args.md_out).write_text(md + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
