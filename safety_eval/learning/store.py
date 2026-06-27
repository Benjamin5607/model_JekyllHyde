"""Persistent store for continuous learning data."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"


def _load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


@dataclass
class LearningState:
    generation: int = 0
    interactions_total: int = 0
    curated_total: int = 0
    rejected_total: int = 0
    curated_since_train: int = 0
    last_train_at: str = ""
    last_curate_at: str = ""
    last_train_samples: int = 0
    training_in_progress: bool = False
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InteractionRecord:
    id: str
    ts: str
    user: str
    assistant: str
    mode: str = "chat"
    format_id: str = "conversational"
    language: str = "en"
    quality_score: float = 0.0
    feedback: str | None = None
    curated: bool = False
    rejected: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_store: LearningStore | None = None
_lock = threading.Lock()


class LearningStore:
    def __init__(self, cfg: dict[str, Any] | None = None):
        self.cfg = cfg or _load_config()
        paths = self.cfg.get("paths", {})
        self.interactions_path = ROOT / paths.get("interactions", "data/learning/interactions.jsonl")
        self.curated_path = ROOT / paths.get("curated", "data/learning/curated_train.jsonl")
        self.rejected_path = ROOT / paths.get("rejected", "data/learning/rejected.jsonl")
        self.state_path = ROOT / paths.get("state", "data/learning/state.json")
        for p in (self.interactions_path, self.curated_path, self.rejected_path, self.state_path):
            p.parent.mkdir(parents=True, exist_ok=True)

    def load_state(self) -> LearningState:
        if not self.state_path.exists():
            return LearningState()
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        return LearningState(**{k: data[k] for k in LearningState.__dataclass_fields__ if k in data})

    def save_state(self, state: LearningState) -> None:
        self.state_path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_interaction(self, record: InteractionRecord) -> None:
        with _lock:
            with self.interactions_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
            state = self.load_state()
            state.interactions_total += 1
            self.save_state(state)

    def append_curated_training(self, record: dict[str, Any]) -> bool:
        """Append if not duplicate. Returns True if stored."""
        from safety_eval.learning.diet import DataDiet

        diet_cfg = self.cfg.get("diet", {})
        if diet_cfg.get("enabled", True):
            diet = DataDiet(self.cfg)
            if diet.is_near_duplicate(record):
                return False

        with _lock:
            with self.curated_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            state = self.load_state()
            state.curated_total += 1
            state.curated_since_train += 1
            state.last_curate_at = datetime.now(UTC).isoformat()
            self.save_state(state)

        if diet_cfg.get("enabled", True):
            DataDiet(self.cfg).register_record(record)
        return True

    def append_rejected(self, record: InteractionRecord, reason: str) -> None:
        with _lock:
            payload = record.to_dict()
            payload["reject_reason"] = reason
            with self.rejected_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            state = self.load_state()
            state.rejected_total += 1
            self.save_state(state)

    def update_feedback(self, interaction_id: str, feedback: str) -> InteractionRecord | None:
        if not self.interactions_path.exists():
            return None
        lines = self.interactions_path.read_text(encoding="utf-8").splitlines()
        updated: InteractionRecord | None = None
        out: list[str] = []
        for line in lines:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("id") == interaction_id:
                row["feedback"] = feedback
                updated = InteractionRecord(**{k: row[k] for k in InteractionRecord.__dataclass_fields__ if k in row})
                if updated.meta is None:
                    updated.meta = row.get("meta") or {}
            out.append(json.dumps(row, ensure_ascii=False))
        if updated:
            self.interactions_path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        return updated

    def iter_interactions(self, *, uncured_only: bool = False) -> list[InteractionRecord]:
        if not self.interactions_path.exists():
            return []
        rows: list[InteractionRecord] = []
        for line in self.interactions_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            rec = InteractionRecord(**{k: data[k] for k in InteractionRecord.__dataclass_fields__ if k in data})
            if rec.meta is None:
                rec.meta = data.get("meta") or {}
            if uncured_only and (rec.curated or rec.rejected):
                continue
            rows.append(rec)
        return rows

    def mark_curated(self, interaction_id: str) -> None:
        self._mark_flag(interaction_id, "curated")

    def mark_rejected(self, interaction_id: str) -> None:
        self._mark_flag(interaction_id, "rejected")

    def _mark_flag(self, interaction_id: str, flag: str) -> None:
        if not self.interactions_path.exists():
            return
        lines = self.interactions_path.read_text(encoding="utf-8").splitlines()
        out: list[str] = []
        for line in lines:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("id") == interaction_id:
                row[flag] = True
            out.append(json.dumps(row, ensure_ascii=False))
        self.interactions_path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def status(self) -> dict[str, Any]:
        state = self.load_state()
        cfg_auto = self.cfg.get("auto", {})
        return {
            "generation": state.generation,
            "interactions_total": state.interactions_total,
            "curated_total": state.curated_total,
            "curated_since_train": state.curated_since_train,
            "rejected_total": state.rejected_total,
            "last_train_at": state.last_train_at,
            "last_curate_at": state.last_curate_at,
            "last_train_samples": state.last_train_samples,
            "training_in_progress": state.training_in_progress,
            "last_error": state.last_error,
            "auto_train_enabled": cfg_auto.get("auto_train_enabled", False),
            "train_threshold": cfg_auto.get("train_when_curated_reaches", 20),
        }


def get_learning_store() -> LearningStore:
    global _store
    if _store is None:
        _store = LearningStore()
    return _store
