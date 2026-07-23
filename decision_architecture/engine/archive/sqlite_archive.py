"""SQLite-backed Go-Explore archive."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS archive (
    state_hash TEXT PRIMARY KEY,
    coverage INTEGER NOT NULL DEFAULT 1,
    tool_sequence TEXT NOT NULL DEFAULT '[]',
    reward REAL NOT NULL DEFAULT 0.0,
    replay_ok INTEGER NOT NULL DEFAULT 0,
    novelty REAL NOT NULL DEFAULT 1.0,
    state_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
"""


@dataclass
class ArchiveRow:
    state_hash: str
    coverage: int
    tool_sequence: list[Any]
    reward: float
    replay_ok: bool
    novelty: float
    state: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_hash": self.state_hash,
            "coverage": self.coverage,
            "tool_sequence": self.tool_sequence,
            "reward": self.reward,
            "replay_ok": self.replay_ok,
            "novelty": self.novelty,
            "state": self.state,
            "metadata": self.metadata,
        }


class SQLiteArchive:
    """
    State → Hash → Novel? → Archive → Mutate seed
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = str(path or ":memory:")
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __len__(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM archive").fetchone()
        return int(row["n"])

    def has(self, state_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM archive WHERE state_hash=?", (state_hash,)
        ).fetchone()
        return row is not None

    def novelty_bonus(self, state_hash: str) -> float:
        if not self.has(state_hash):
            return 1.0
        row = self._conn.execute(
            "SELECT coverage FROM archive WHERE state_hash=?", (state_hash,)
        ).fetchone()
        visits = int(row["coverage"]) if row else 0
        return 1.0 / (1.0 + visits)

    def store(
        self,
        state: Any,
        *,
        reward: float = 0.0,
        metadata: dict[str, Any] | None = None,
        trajectory: list[dict[str, Any]] | None = None,
        replay_ok: bool = False,
    ) -> ArchiveRow:
        key = getattr(state, "cell_key", None) or str(state)
        state_json = state.to_dict() if hasattr(state, "to_dict") else {"raw": str(state)}
        tool_sequence = trajectory or (metadata or {}).get("tool_sequence") or []
        novelty = self.novelty_bonus(key)
        if self.has(key):
            self._conn.execute(
                """
                UPDATE archive
                SET coverage = coverage + 1,
                    reward = MAX(reward, ?),
                    replay_ok = MAX(replay_ok, ?),
                    novelty = ?,
                    tool_sequence = ?,
                    state_json = ?,
                    metadata_json = ?
                WHERE state_hash = ?
                """,
                (
                    reward,
                    1 if replay_ok else 0,
                    novelty,
                    json.dumps(tool_sequence),
                    json.dumps(state_json),
                    json.dumps(metadata or {}),
                    key,
                ),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO archive
                (state_hash, coverage, tool_sequence, reward, replay_ok, novelty, state_json, metadata_json)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    json.dumps(tool_sequence),
                    reward,
                    1 if replay_ok else 0,
                    novelty,
                    json.dumps(state_json),
                    json.dumps(metadata or {}),
                ),
            )
        self._conn.commit()
        return self.get(key)  # type: ignore[return-value]

    def get(self, state_hash: str) -> ArchiveRow | None:
        row = self._conn.execute(
            "SELECT * FROM archive WHERE state_hash=?", (state_hash,)
        ).fetchone()
        if not row:
            return None
        return ArchiveRow(
            state_hash=row["state_hash"],
            coverage=int(row["coverage"]),
            tool_sequence=json.loads(row["tool_sequence"] or "[]"),
            reward=float(row["reward"]),
            replay_ok=bool(row["replay_ok"]),
            novelty=float(row["novelty"]),
            state=json.loads(row["state_json"] or "{}"),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def under_visited(self, limit: int = 10) -> list[ArchiveRow]:
        rows = self._conn.execute(
            "SELECT * FROM archive ORDER BY coverage ASC, reward DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self.get(r["state_hash"]) for r in rows if self.get(r["state_hash"])]

    def sample_seed(self) -> ArchiveRow | None:
        pool = self.under_visited(limit=max(1, len(self)))
        return pool[0] if pool else None

    def coverage(self) -> int:
        return len(self)

    def coverage_heatmap(self) -> dict[str, int]:
        """Tool-name coverage counts from stored sequences."""
        heat: dict[str, int] = {}
        rows = self._conn.execute("SELECT tool_sequence FROM archive").fetchall()
        for row in rows:
            seq = json.loads(row["tool_sequence"] or "[]")
            for step in seq:
                name = step.get("name") if isinstance(step, dict) else str(step)
                if not name:
                    continue
                heat[name] = heat.get(name, 0) + 1
        return heat

    def to_dict(self) -> dict[str, Any]:
        rows = self._conn.execute("SELECT state_hash FROM archive").fetchall()
        return {
            "coverage": self.coverage(),
            "heatmap": self.coverage_heatmap(),
            "cells": [self.get(r["state_hash"]).to_dict() for r in rows if self.get(r["state_hash"])],
        }


# Default archive alias used by DecisionEngine
Archive = SQLiteArchive
