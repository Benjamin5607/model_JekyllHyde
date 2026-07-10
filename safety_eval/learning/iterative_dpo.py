"""Online iterative DPO — RLAIF scores as preference weights, background auto-loop."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from safety_eval.learning.diet import record_user_assistant
from safety_eval.learning.dpo_pairs import build_preference_pairs, export_dpo_dataset
from safety_eval.learning.rlaif_gate import RlaifGate

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"
PYTHON = ROOT / ".venv-train" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


def _load_iter_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("iterative_dpo", {})


def _load_state() -> dict[str, Any]:
    path = ROOT / "data" / "learning" / "iterative_dpo_state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    path = ROOT / "data" / "learning" / "iterative_dpo_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def weight_pairs_with_rlaif(pairs: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Attach RLAIF reward score to each DPO pair (chosen vs rejected)."""
    gate = RlaifGate()
    weighted: list[dict[str, Any]] = []
    for row in pairs:
        chosen_rec = {
            "messages": [
                {"role": "user", "content": row["prompt"]},
                {"role": "assistant", "content": row["chosen"]},
            ],
            "meta": {"quality_score": 0.85},
        }
        rejected_rec = {
            "messages": [
                {"role": "user", "content": row["prompt"]},
                {"role": "assistant", "content": row["rejected"]},
            ],
            "meta": {"quality_score": 0.3},
        }
        chosen_score = gate.score_record(chosen_rec, topic=row["prompt"])
        rejected_score = gate.score_record(rejected_rec, topic=row["prompt"])
        margin = max(0.0, chosen_score.score - rejected_score.score)
        reward = margin / 100.0
        weighted.append({
            **row,
            "reward": round(reward, 4),
            "chosen_rlaif": chosen_score.score,
            "rejected_rlaif": rejected_score.score,
            "weight": max(0.1, reward),
        })
    return weighted


def export_weighted_dataset() -> dict[str, Any]:
    cfg = _load_iter_cfg()
    pairs = build_preference_pairs()
    weighted = weight_pairs_with_rlaif(pairs)
    min_reward = float(cfg.get("min_reward_margin", 0.05))
    kept = [p for p in weighted if p["reward"] >= min_reward]
    out_path = ROOT / cfg.get("weighted_dataset", "data/learning/dpo_pairs_weighted.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"path": str(out_path), "pairs": len(kept), "total": len(weighted)}


def should_run_iterative_dpo() -> tuple[bool, str]:
    cfg = _load_iter_cfg()
    if not cfg.get("enabled", False):
        return False, "disabled"
    state = _load_state()
    last = state.get("last_run_at")
    interval_h = float(cfg.get("interval_hours", 12))
    if last:
        try:
            t = datetime.fromisoformat(last)
            if datetime.now(UTC) - t.replace(tzinfo=UTC) < timedelta(hours=interval_h):
                return False, "interval"
        except ValueError:
            pass
    from safety_eval.learning.dpo_pairs import pair_count

    min_pairs = int(cfg.get("min_pairs", 4))
    if pair_count() < min_pairs:
        return False, f"need_{min_pairs}_pairs"
    return True, "ready"


def run_iterative_dpo_cycle(*, base: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Export RLAIF-weighted pairs and run DPO training."""
    cfg = _load_iter_cfg()
    ok, reason = should_run_iterative_dpo()
    if not ok and not dry_run:
        return {"started": False, "reason": reason}

    export_info = export_dpo_dataset()
    weighted_info = export_weighted_dataset()
    if dry_run:
        return {"dry_run": True, **export_info, **weighted_info}

    base = base or cfg.get("train_base") or "gemma3-4b"
    dp_flag = ["--dp"] if cfg.get("use_dp_sgd", True) else []
    proc = subprocess.run(
        [
            str(PYTHON),
            str(ROOT / "training" / "train_dpo.py"),
            "--base",
            base,
            "--4bit",
            "--persona",
            "both",
            *dp_flag,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=7200,
    )
    state = {
        "last_run_at": datetime.now(UTC).isoformat(),
        "ok": proc.returncode == 0,
        "pairs": weighted_info.get("pairs", 0),
        "base": base,
    }
    if proc.returncode != 0:
        state["error"] = (proc.stderr or proc.stdout or "dpo failed")[-500:]
    _save_state(state)
    return {
        "started": True,
        "ok": proc.returncode == 0,
        **export_info,
        **weighted_info,
        "state": state,
    }
