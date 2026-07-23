"""CLI: real Kaggle env Search Benchmark (Optimal/Allow + agent)."""

from __future__ import annotations

import argparse
from pathlib import Path

from decision_architecture.engine.benchmark.kaggle_bench import RealSearchBenchmark, save_report
from decision_architecture.engine.search.config import SearchConfig


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Real-env Search Strategy Zoo benchmark")
    p.add_argument("--config", default="configs/search.yaml")
    p.add_argument("--guardrail", default="optimal", choices=["optimal", "allow"])
    p.add_argument(
        "--agent",
        default="deterministic",
        choices=["deterministic", "gpt_oss", "openai", "gemma", "auto"],
    )
    p.add_argument("--recipes", type=int, default=12)
    p.add_argument("--out-dir", default="experiments/archive")
    p.add_argument("--stem", default=None)
    args = p.parse_args(argv)

    cfg_path = Path(args.config)
    config = SearchConfig.load(cfg_path) if cfg_path.exists() else SearchConfig.from_dict()
    bench = RealSearchBenchmark(config)
    report = bench.run(
        guardrail=args.guardrail,
        agent=args.agent,
        recipes_per_strategy=args.recipes,
    )
    stem = args.stem or f"real_{args.guardrail}_{args.agent}"
    paths = save_report(report, args.out_dir, stem=stem)
    print(report.to_markdown())
    print("ranking:", ", ".join(report.to_dict()["ranking_by_findings"]))
    print("wrote", paths["md"], paths["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
