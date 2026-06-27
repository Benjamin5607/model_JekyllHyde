"""Run data diet: semantic dedup + balance on all learning datasets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from safety_eval.learning.diet import clean_all_datasets  # noqa: E402


def main() -> int:
    print("=== Jekyll & Hyde Data Diet ===")
    report = clean_all_datasets(rebuild_index=True)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    removed = report.get("total_removed", 0)
    print(f"\nDone. Removed {removed} duplicate/low-priority records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
