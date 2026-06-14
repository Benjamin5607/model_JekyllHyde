"""Red vs blue arena reporting."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from safety_eval.arena import ArenaReport


def print_arena_report(report: ArenaReport, console: Console | None = None) -> None:
    console = console or Console()

    console.print("\n[bold]Jekyll & Hyde[/bold] — Duel Report")
    console.print(f"[bold red]Hyde[/bold red] (attack) vs [bold blue]Jekyll[/bold blue] (defense)")
    console.print(f"Hyde:   {report.red_team_name}")
    console.print(f"Jekyll: {report.blue_team_name}")
    if report.guidelines:
        console.print(f"Guidelines: {report.guidelines}")
    console.print()

    summary = Table(title="Jekyll Catch Rate")
    summary.add_column("Metric")
    summary.add_column("Value", justify="right")
    summary.add_row("Total attacks", str(report.total))
    summary.add_row("Caught", str(report.caught))
    summary.add_row("Bypassed", str(report.bypassed))
    summary.add_row("Catch rate", f"{report.catch_rate:.1%}")
    console.print(summary)

    if report.by_attack_mode():
        mode_table = Table(title="By Attack Mode")
        mode_table.add_column("Mode")
        mode_table.add_column("Caught", justify="right")
        mode_table.add_column("Bypassed", justify="right")
        mode_table.add_column("Catch rate", justify="right")

        for mode, duels in sorted(report.by_attack_mode().items()):
            caught = sum(1 for d in duels if d.caught)
            total = len(duels)
            rate = caught / total if total else 0
            mode_table.add_row(mode, str(caught), str(total - caught), f"{rate:.0%}")

        console.print(mode_table)

    tech_table = Table(title="By Technique")
    tech_table.add_column("Technique")
    tech_table.add_column("Caught", justify="right")
    tech_table.add_column("Bypassed", justify="right")
    tech_table.add_column("Catch rate", justify="right")

    for technique, duels in sorted(report.by_technique().items()):
        caught = sum(1 for d in duels if d.caught)
        total = len(duels)
        rate = caught / total if total else 0
        tech_table.add_row(technique, str(caught), str(total - caught), f"{rate:.0%}")

    console.print(tech_table)

    cat_table = Table(title="By Category")
    cat_table.add_column("Category")
    cat_table.add_column("Caught", justify="right")
    cat_table.add_column("Bypassed", justify="right")
    cat_table.add_column("Catch rate", justify="right")

    for category, duels in sorted(report.by_category().items()):
        caught = sum(1 for d in duels if d.caught)
        total = len(duels)
        rate = caught / total if total else 0
        cat_table.add_row(category, str(caught), str(total - caught), f"{rate:.0%}")

    console.print(cat_table)

    bypasses = report.bypasses()
    if bypasses:
        fail_table = Table(title=f"Hyde Escapes — Jekyll Missed ({len(bypasses)})")
        fail_table.add_column("ID")
        fail_table.add_column("Mode")
        fail_table.add_column("Section")
        fail_table.add_column("Prompt", max_width=45)

        for duel in bypasses[:15]:
            fail_table.add_row(
                duel.attack.id,
                duel.attack_mode,
                (duel.attack.guideline_section or "-")[:20],
                duel.attack.prompt[:75] + ("..." if len(duel.attack.prompt) > 75 else ""),
            )
        console.print(fail_table)
        if len(bypasses) > 15:
            console.print(f"[dim]... and {len(bypasses) - 15} more bypasses[/dim]")


def save_arena_json(report: ArenaReport, path: str | Path) -> None:
    payload = {
        "red_team": report.red_team_name,
        "blue_team": report.blue_team_name,
        "guidelines": report.guidelines,
        "total": report.total,
        "caught": report.caught,
        "bypassed": report.bypassed,
        "catch_rate": round(report.catch_rate, 4),
        "duels": [
            {
                "id": d.attack.id,
                "category": d.category,
                "attack_mode": d.attack_mode,
                "guideline_section": d.attack.guideline_section,
                "technique": d.technique,
                "prompt": d.attack.prompt,
                "caught": d.caught,
                "outcome": d.outcome,
                "blocked": d.defense.blocked,
                "flagged": d.defense.flagged,
                "score": d.defense.score,
                "blue_categories": d.defense.categories,
            }
            for d in report.duels
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
