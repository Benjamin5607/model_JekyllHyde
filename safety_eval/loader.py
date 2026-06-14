"""Load test case datasets from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from safety_eval.models import ExpectedAction, Severity, TestCase


def _parse_case(raw: dict[str, Any]) -> TestCase:
    return TestCase(
        id=str(raw["id"]),
        prompt=str(raw["prompt"]).strip(),
        category=str(raw["category"]),
        expected=ExpectedAction(str(raw["expected"]).lower()),
        severity=Severity(str(raw.get("severity", "medium")).lower()),
        tags=tuple(str(t) for t in raw.get("tags", [])),
        notes=str(raw.get("notes", "")),
        metadata=dict(raw.get("metadata", {})),
    )


def load_dataset(path: str | Path) -> list[TestCase]:
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError(f"Invalid dataset format: {path}")

    cases = [_parse_case(item) for item in data["cases"]]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate test case IDs in {path}")

    return cases
