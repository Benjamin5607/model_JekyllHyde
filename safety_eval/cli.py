"""Command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from safety_eval.classifiers import build_classifier
from safety_eval.evaluator import run_evaluation
from safety_eval.loader import load_dataset
from safety_eval.report import print_report, save_report_json

DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "data" / "test_cases.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate content moderation classifiers against labeled test cases.",
    )
    parser.add_argument(
        "--dataset",
        "-d",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to YAML test case dataset",
    )
    parser.add_argument(
        "--classifier",
        "-c",
        choices=["mock", "keyword", "http"],
        default="keyword",
        help="Classifier backend to evaluate",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        help="Custom keyword rules YAML (keyword classifier only)",
    )
    parser.add_argument(
        "--url",
        help="Moderation API URL (http classifier only)",
    )
    parser.add_argument(
        "--api-key",
        help="Bearer token for moderation API",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Save JSON report to this path",
    )
    parser.add_argument(
        "--filter-category",
        action="append",
        dest="categories",
        help="Run only cases in this category (repeatable)",
    )
    parser.add_argument(
        "--filter-tag",
        action="append",
        dest="tags",
        help="Run only cases with this tag (repeatable)",
    )

    args = parser.parse_args()
    console = Console()

    if not args.dataset.exists():
        console.print(f"[red]Dataset not found:[/red] {args.dataset}")
        raise SystemExit(1)

    cases = load_dataset(args.dataset)

    if args.categories:
        allowed = set(args.categories)
        cases = [c for c in cases if c.category in allowed]

    if args.tags:
        required = set(args.tags)
        cases = [c for c in cases if required.intersection(c.tags)]

    if not cases:
        console.print("[red]No test cases matched filters.[/red]")
        raise SystemExit(1)

    classifier_kwargs: dict = {}
    if args.classifier == "keyword" and args.rules:
        classifier_kwargs["rules_path"] = args.rules
    if args.classifier == "http":
        if not args.url:
            console.print("[red]--url is required for http classifier[/red]")
            raise SystemExit(1)
        classifier_kwargs["url"] = args.url
        if args.api_key:
            classifier_kwargs["api_key"] = args.api_key

    classifier = build_classifier(args.classifier, **classifier_kwargs)
    report = run_evaluation(cases, classifier, dataset_path=str(args.dataset))

    print_report(report, console)

    if args.output:
        save_report_json(report, args.output)
        console.print(f"\n[green]Report saved to[/green] {args.output}")


if __name__ == "__main__":
    main()
