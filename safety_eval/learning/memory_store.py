"""Embedding-based rule memory — distill gray-zone patches, RAG on similar prompts."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from safety_eval.learning.diet import cosine, embed_text, record_user_assistant, normalize_text

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"
_lock = threading.Lock()
_memory: RuleMemory | None = None


def _load_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("memory", {})


@dataclass
class MemoryEntry:
    id: str
    rule_text: str
    zone_description: str
    topic: str
    source: str
    ts: str
    vector: list[float] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryHit:
    entry: MemoryEntry
    score: float


class RuleMemory:
    def __init__(self, cfg: dict[str, Any] | None = None):
        self.cfg = cfg or _load_cfg()
        paths = self.cfg.get("paths", {})
        self.store_path = ROOT / paths.get("rules", "data/learning/memory_rules.jsonl")
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = int(self.cfg.get("max_entries", 500))
        self.retrieve_k = int(self.cfg.get("retrieve_k", 3))
        self.min_similarity = float(self.cfg.get("min_similarity", 0.55))

    def _load_entries(self) -> list[MemoryEntry]:
        if not self.store_path.exists():
            return []
        entries: list[MemoryEntry] = []
        for line in self.store_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                entries.append(MemoryEntry(**data))
            except (json.JSONDecodeError, TypeError):
                continue
        return entries

    def _save_entries(self, entries: list[MemoryEntry]) -> None:
        with self.store_path.open("w", encoding="utf-8") as f:
            for e in entries[-self.max_entries :]:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")

    def store(
        self,
        *,
        rule_text: str,
        zone_description: str = "",
        topic: str = "",
        source: str = "gray_reinforce",
        meta: dict[str, Any] | None = None,
    ) -> MemoryEntry | None:
        rule_text = (rule_text or "").strip()
        if len(rule_text) < 20:
            return None
        text = f"{topic}\n{zone_description}\n{rule_text}"
        vec = embed_text(text)
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            rule_text=rule_text[:1200],
            zone_description=(zone_description or "")[:400],
            topic=(topic or "")[:200],
            source=source,
            ts=datetime.now(UTC).isoformat(),
            vector=vec,
            meta=meta or {},
        )
        with _lock:
            entries = self._load_entries()
            # Dedupe by normalized rule
            key = normalize_text(rule_text)
            if any(normalize_text(e.rule_text) == key for e in entries):
                return None
            entries.append(entry)
            self._save_entries(entries)
            if len(entries) >= int(self.cfg.get("consolidate_after", 40)):
                self.consolidate_if_needed()
        return entry

    def store_from_training(self, record: dict[str, Any], *, topic: str = "") -> MemoryEntry | None:
        user, assistant = record_user_assistant(record)
        meta = record.get("meta") or {}
        rule = ""
        zone = ""
        for line in assistant.splitlines():
            low = line.lower()
            if "suggested rule" in low or "**rule:**" in low:
                rule = line.split(":", 1)[-1].strip().strip("*")
            if "problem:" in low or "gray zone" in low:
                zone = line.split(":", 1)[-1].strip().strip("*")
        if not rule:
            rule = assistant[:500]
        return self.store(
            rule_text=rule,
            zone_description=zone or user[:200],
            topic=topic or user[:200],
            source=str(meta.get("source", "training")),
            meta={"type": meta.get("type"), "zone_id": meta.get("zone_id")},
        )

    def retrieve(self, query: str, *, k: int | None = None) -> list[MemoryHit]:
        k = k or self.retrieve_k
        qvec = embed_text(query)
        hits: list[MemoryHit] = []
        for entry in self._load_entries():
            if not entry.vector:
                continue
            sim = cosine(qvec, entry.vector)
            if sim >= self.min_similarity:
                hits.append(MemoryHit(entry=entry, score=sim))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def format_block(self, query: str, *, k: int | None = None) -> str:
        if not self.cfg.get("inject_on_query", True):
            return ""
        hits = self.retrieve(query, k=k)
        if not hits:
            return ""
        lines = ["PAST GRAY-ZONE RULES (distilled memory — apply when relevant):"]
        for i, hit in enumerate(hits, 1):
            e = hit.entry
            lines.append(f"{i}. [{e.source}] {e.rule_text[:280]}")
            if e.zone_description:
                lines.append(f"   Context: {e.zone_description[:120]}")
        return "\n".join(lines)

    def distill_evicted_records(self, records: list[dict[str, Any]]) -> int:
        """FIFO eviction → persist rule summaries before drop."""
        if not self.cfg.get("distill_on_evict", True):
            return 0
        stored = 0
        for rec in records:
            meta = rec.get("meta") or {}
            if meta.get("source") == "gray_reinforce" or meta.get("format") in (
                "policy_hardening",
                "gray_zone_map",
            ):
                if self.store_from_training(rec):
                    stored += 1
        return stored

    def consolidate_if_needed(self) -> dict[str, Any]:
        """Merge similar gray-zone rules when the store grows past the threshold."""
        if not self.cfg.get("consolidation_enabled", True):
            return {"consolidated": False, "reason": "disabled"}

        threshold = int(self.cfg.get("consolidate_after", 40))
        entries = self._load_entries()
        if len(entries) < threshold:
            return {"consolidated": False, "count": len(entries), "reason": "below_threshold"}

        sim_thresh = float(self.cfg.get("consolidate_similarity", 0.88))
        merged_entries: list[MemoryEntry] = []
        used: set[int] = set()
        clusters_merged = 0

        for i, entry in enumerate(entries):
            if i in used:
                continue
            cluster = [entry]
            used.add(i)
            for j in range(i + 1, len(entries)):
                if j in used:
                    continue
                other = entries[j]
                if not entry.vector or not other.vector:
                    continue
                if cosine(entry.vector, other.vector) >= sim_thresh:
                    cluster.append(other)
                    used.add(j)
            if len(cluster) == 1:
                merged_entries.append(cluster[0])
            else:
                merged_entries.append(self._merge_cluster(cluster))
                clusters_merged += 1

        self._save_entries(merged_entries)
        return {
            "consolidated": True,
            "before": len(entries),
            "after": len(merged_entries),
            "clusters_merged": clusters_merged,
        }

    def _merge_cluster(self, cluster: list[MemoryEntry]) -> MemoryEntry:
        """Generalize a cluster of similar rules into one distilled entry."""
        topics = sorted({c.topic for c in cluster if c.topic})
        rules = [c.rule_text for c in cluster]
        primary = max(rules, key=len)
        extras: list[str] = []
        primary_norm = normalize_text(primary)
        for rule in rules:
            norm = normalize_text(rule)
            if norm != primary_norm and norm not in primary_norm:
                extras.append(rule[:120])
        rule_text = primary
        if extras:
            rule_text = f"{primary} Also covers: {'; '.join(extras[:3])}"
        zones = [c.zone_description for c in cluster if c.zone_description]
        zone = zones[0] if zones else ""
        topic = (topics[0] if topics else cluster[0].topic)[:200]
        combined = f"{topic}\n{zone}\n{rule_text}"
        return MemoryEntry(
            id=uuid.uuid4().hex[:12],
            rule_text=rule_text[:1200],
            zone_description=zone[:400],
            topic=topic,
            source="consolidated",
            ts=datetime.now(UTC).isoformat(),
            vector=embed_text(combined),
            meta={"merged_from": len(cluster), "sources": [c.source for c in cluster]},
        )


def get_rule_memory() -> RuleMemory:
    global _memory
    if _memory is None:
        _memory = RuleMemory()
    return _memory


def distill_evicted_records(records: list[dict[str, Any]]) -> int:
    return get_rule_memory().distill_evicted_records(records)


def consolidate_memory_if_needed() -> dict[str, Any]:
    return get_rule_memory().consolidate_if_needed()
