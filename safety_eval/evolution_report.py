"""Evolution session reporting."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from safety_eval.evolution import EvolutionSession
from safety_eval.jekyll_hyde import TAGLINE
from safety_eval.arena_report import print_arena_report


def print_evolution_report(session: EvolutionSession, console: Console | None = None) -> None:
    console = console or Console()

    console.print("\n[bold]Jekyll & Hyde[/bold] — Co-evolution Session")
    console.print(f"[dim]{TAGLINE}[/dim]")
    if session.guidelines:
        console.print(f"Guidelines: {session.guidelines}")
    console.print()

    trend = Table(title="Catch Rate Trend (Jekyll vs Hyde)")
    trend.add_column("Round")
    trend.add_column("Attacks", justify="right")
    trend.add_column("Caught", justify="right")
    trend.add_column("Bypassed", justify="right")
    trend.add_column("Catch rate", justify="right")
    trend.add_column("Hyde escapes learned", justify="right")
    trend.add_column("Jekyll rules learned", justify="right")

    for round_info in session.rounds:
        report = round_info.report
        trend.add_row(
            str(round_info.round_number),
            str(report.total),
            str(report.caught),
            str(report.bypassed),
            f"{report.catch_rate:.0%}",
            str(round_info.new_escapes),
            str(round_info.new_learnings),
        )

    console.print(trend)

    if len(session.rounds) > 1:
        first = session.rounds[0].report.catch_rate
        last = session.rounds[-1].report.catch_rate
        delta = last - first
        direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
        console.print(
            f"\nJekyll defense evolved: {first:.0%} -> {last:.0%} ({direction} {abs(delta):.0%})"
        )

    console.print(f"\n[bold]Final round detail[/bold]")
    print_arena_report(session.rounds[-1].report, console)


def save_evolution_json(session: EvolutionSession, path: str | Path) -> None:
    payload = {
        "model": "Jekyll & Hyde",
        "guidelines": session.guidelines,
        "hyde_backend": session.hyde_backend,
        "jekyll_backend": session.jekyll_backend,
        "final_catch_rate": round(session.final_catch_rate, 4),
        "catch_rate_trend": [round(r, 4) for r in session.catch_rate_trend()],
        "rounds": [
            {
                "round": r.round_number,
                "catch_rate": round(r.report.catch_rate, 4),
                "caught": r.report.caught,
                "bypassed": r.report.bypassed,
                "new_escapes": r.new_escapes,
                "new_learnings": r.new_learnings,
            }
            for r in session.rounds
        ],
        "hyde_total_escapes": len(session.hyde_memory.bypasses),
        "jekyll_learned_patterns": len(session.jekyll_memory.learned_patterns),
    }
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
