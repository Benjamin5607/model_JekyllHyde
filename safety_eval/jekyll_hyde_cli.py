"""Jekyll & Hyde — co-evolving guideline defense CLI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich.console import Console

from safety_eval.arena import run_arena
from safety_eval.arena_report import print_arena_report, save_arena_json
from safety_eval.blue_team import build_blue_team
from safety_eval.evolution import run_evolution
from safety_eval.evolution_report import print_evolution_report, save_evolution_json
from safety_eval.guidelines import load_guidelines
from safety_eval.jekyll_hyde import TAGLINE
from safety_eval.red_team import build_red_team

DEFAULT_RULES = Path(__file__).resolve().parent.parent / "data" / "keyword_rules.yaml"
DEFAULT_GUIDELINES = Path(__file__).resolve().parent.parent / "data" / "community_guidelines.md"
DEFAULT_PROBES = Path(__file__).resolve().parent.parent / "data" / "guideline_probes.yaml"


def _build_agents(args: argparse.Namespace) -> tuple:
    red_kwargs: dict = {}
    if args.hyde == "guideline":
        red_kwargs["guidelines"] = args.guidelines
        red_kwargs["probes_path"] = args.probes
        red_kwargs["seed"] = args.seed
        if args.url:
            red_kwargs["url"] = args.url
            red_kwargs["model"] = args.model
            if args.api_key:
                red_kwargs["api_key"] = args.api_key
    elif args.hyde == "template":
        red_kwargs["seeds_path"] = args.seeds
        red_kwargs["seed"] = args.seed
    elif args.hyde == "llm":
        if not args.url:
            raise SystemExit("--url required for LLM Hyde")
        red_kwargs["url"] = args.url
        red_kwargs["model"] = args.model
        if args.api_key:
            red_kwargs["api_key"] = args.api_key

    blue_kwargs: dict = {}
    if args.guidelines.exists():
        blue_kwargs["guidelines_path"] = args.guidelines
    if args.jekyll == "keyword":
        blue_kwargs["rules_path"] = args.rules
    elif args.jekyll in ("http", "llm"):
        if not args.url:
            raise SystemExit("--url required for http/llm Jekyll")
        blue_kwargs["url"] = args.url
        if args.api_key:
            blue_kwargs["api_key"] = args.api_key
        if args.jekyll == "llm":
            blue_kwargs["model"] = args.model

    return build_red_team(args.hyde, **red_kwargs), build_blue_team(args.jekyll, **blue_kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jekyll-hyde",
        description="Jekyll & Hyde — co-evolving guideline defense experiment.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{TAGLINE}

Hyde (attack): reads your guidelines and evolves escapes / gray-zone probes.
Jekyll (defense): enforces the same guidelines and learns from Hyde's bypasses.

Examples:
  python -m safety_eval.jekyll_hyde_cli -g data/community_guidelines.md --rounds 5 -n 12
  python -m safety_eval.jekyll_hyde_cli -g my_rules.txt --attack-mode evasion --attack-mode gray_zone
  python -m safety_eval.jekyll_hyde_cli --hyde guideline --jekyll llm --url https://api.openai.com -g rules.md
        """,
    )
    parser.add_argument("--hyde", choices=["guideline", "template", "llm"], default="guideline")
    parser.add_argument("--jekyll", choices=["keyword", "mock", "http", "llm"], default="keyword")
    parser.add_argument("--guidelines", "-g", type=Path, default=DEFAULT_GUIDELINES)
    parser.add_argument("--probes", type=Path, default=DEFAULT_PROBES)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--seeds", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "red_team_seeds.yaml")
    parser.add_argument("--attack-mode", action="append", dest="attack_modes", choices=["violation", "evasion", "gray_zone"])
    parser.add_argument("--rounds", "-r", type=int, default=3, help="Co-evolution rounds (default: 3)")
    parser.add_argument("--count", "-n", type=int, default=15, help="Attacks per round")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--url")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--single-round", action="store_true", help="Skip evolution; one duel only")

    args = parser.parse_args()
    console = Console()

    if not args.guidelines.exists():
        console.print(f"[red]Guidelines not found:[/red] {args.guidelines}")
        raise SystemExit(1)

    hyde, jekyll = _build_agents(args)
    guidelines = load_guidelines(args.guidelines)

    console.print("[bold]Jekyll & Hyde[/bold]")
    console.print(f"[dim]{TAGLINE}[/dim]")
    console.print(f"Guidelines: [cyan]{guidelines.title}[/cyan] ({args.guidelines.name})")
    console.print(f"Hyde: {hyde.name} · Jekyll: {jekyll.name}")

    if args.single_round or args.rounds <= 1:
        console.print(f"[dim]Single duel · {args.count} attacks[/dim]")
        report = run_arena(
            hyde,
            jekyll,
            categories=args.categories,
            count=args.count,
            attack_modes=args.attack_modes,
        )
        print_arena_report(report, console)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            save_arena_json(report, args.output)
    else:
        console.print(f"[dim]Evolution · {args.rounds} rounds × {args.count} attacks[/dim]")
        session = run_evolution(
            hyde,
            jekyll,
            guidelines_title=guidelines.title,
            rounds=args.rounds,
            count_per_round=args.count,
            categories=args.categories,
            attack_modes=args.attack_modes,
        )
        print_evolution_report(session, console)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            save_evolution_json(session, args.output)

    if args.output:
        console.print(f"\n[green]Saved[/green] {args.output}")


if __name__ == "__main__":
    main()
