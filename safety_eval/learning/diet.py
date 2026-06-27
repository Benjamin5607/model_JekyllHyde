"""Data diet: semantic dedup, persona/category balancing, FIFO caps."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"

_WS = re.compile(r"\s+")


def _load_cfg() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _diet_cfg(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or _load_cfg()
    return cfg.get("diet", {})


def record_user_assistant(rec: dict[str, Any]) -> tuple[str, str]:
    user = assistant = ""
    for msg in rec.get("messages", []):
        role = msg.get("role", "")
        content = (msg.get("content") or "").strip()
        if role == "user" and not user:
            user = content
        elif role == "assistant":
            assistant = content
    return user, assistant


def normalize_text(text: str) -> str:
    return _WS.sub(" ", (text or "").lower().strip())


def content_hash(rec: dict[str, Any]) -> str:
    user, assistant = record_user_assistant(rec)
    payload = f"{normalize_text(user)}|{normalize_text(assistant)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def embed_text(text: str) -> list[float]:
    """Embedding vector — bge-small when available, else hashed bag-of-words."""
    diet = _diet_cfg()
    model_id = diet.get("embedding_model", "BAAI/bge-small-en-v1.5")
    try:
        from sentence_transformers import SentenceTransformer

        if not hasattr(embed_text, "_model") or getattr(embed_text, "_model_id", "") != model_id:
            embed_text._model = SentenceTransformer(model_id)  # type: ignore[attr-defined]
            embed_text._model_id = model_id  # type: ignore[attr-defined]
        vec = embed_text._model.encode(  # type: ignore[attr-defined]
            [text], normalize_embeddings=True, show_progress_bar=False
        )[0]
        return vec.tolist()
    except Exception:
        return _bow_embed(text)


def _bow_embed(text: str, dim: int = 256) -> list[float]:
    vec = [0.0] * dim
    tokens = normalize_text(text).split()
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim
        vec[h] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def persona_bucket(rec: dict[str, Any]) -> str:
    meta = rec.get("meta") or {}
    typ = (meta.get("type") or "").lower()
    mode = (meta.get("mode") or "").lower()
    _, assistant = record_user_assistant(rec)
    al = assistant.lower()
    if mode == "hyde" or "hyde" in typ or "hyde test probe" in al[:80]:
        return "hyde"
    if mode == "jekyll" or "jekyll" in typ or al.startswith("jekyll verdict"):
        return "jekyll"
    return "neutral"


def category_bucket(rec: dict[str, Any]) -> str:
    meta = rec.get("meta") or {}
    typ = (meta.get("type") or "").lower()
    fmt = (meta.get("format") or "").lower()
    user, _ = record_user_assistant(rec)
    blob = f"{typ} {fmt} {user}".lower()
    if any(k in blob for k in ("quant", "market", "investment", "equity", "stock")):
        return "quant"
    if any(k in blob for k in ("guideline", "policy", "gray", "hardening", "moderation", "refusal")):
        return "policy"
    if "duel" in typ or "duel" in blob:
        return "duel"
    return "chat"


def record_sort_key(rec: dict[str, Any]) -> tuple[float, str]:
    meta = rec.get("meta") or {}
    score = float(meta.get("quality_score", 0.5))
    ts = str(meta.get("ts") or meta.get("interaction_id") or "")
    return (score, ts)


@dataclass
class DietStats:
    input_count: int = 0
    hash_removed: int = 0
    semantic_removed: int = 0
    balance_removed: int = 0
    output_count: int = 0
    buckets: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_count": self.input_count,
            "hash_removed": self.hash_removed,
            "semantic_removed": self.semantic_removed,
            "balance_removed": self.balance_removed,
            "output_count": self.output_count,
            "buckets": self.buckets,
        }


class DataDiet:
    def __init__(self, cfg: dict[str, Any] | None = None):
        self.cfg = cfg or _load_cfg()
        self.diet = _diet_cfg(self.cfg)
        self.threshold = float(self.diet.get("semantic_threshold", 0.92))
        self.max_total = int(self.diet.get("max_total_records", 2000))
        caps = self.diet.get("category_caps", {})
        self.category_caps: dict[str, int] = {k: int(v) for k, v in caps.items()}
        persona_caps = self.diet.get("persona_caps", {})
        self.persona_caps: dict[str, int] = {k: int(v) for k, v in persona_caps.items()}
        index_path = self.diet.get("embedding_index", "data/learning/embedding_index.json")
        self.index_path = ROOT / index_path

    def _load_index(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def save_index(self, entries: list[dict[str, Any]]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    def is_semantic_duplicate(self, rec: dict[str, Any], vectors: list[list[float]]) -> bool:
        user, assistant = record_user_assistant(rec)
        text = f"{user}\n{assistant}".strip()
        if not text:
            return True
        vec = embed_text(text)
        for existing in vectors:
            if cosine(vec, existing) >= self.threshold:
                return True
        vectors.append(vec)
        return False

    def apply(self, records: list[dict[str, Any]], *, rebuild_index: bool = False) -> tuple[list[dict[str, Any]], DietStats]:
        stats = DietStats(input_count=len(records))
        seen_hash: set[str] = set()
        vectors: list[list[float]] = []
        if not rebuild_index:
            for row in self._load_index():
                if "vector" in row:
                    vectors.append(row["vector"])

        stage1: list[dict[str, Any]] = []
        for rec in records:
            h = content_hash(rec)
            if h in seen_hash:
                stats.hash_removed += 1
                continue
            seen_hash.add(h)
            if self.is_semantic_duplicate(rec, vectors):
                stats.semantic_removed += 1
                continue
            stage1.append(rec)

        # Sort: highest quality / newest first for FIFO eviction priority
        stage1.sort(key=record_sort_key, reverse=True)

        cat_counts: dict[str, int] = defaultdict(int)
        persona_counts: dict[str, int] = defaultdict(int)
        kept: list[dict[str, Any]] = []

        default_cat_cap = self.max_total // max(len(self.category_caps), 1)
        default_persona_cap = self.max_total // max(len(self.persona_caps), 1)

        for rec in stage1:
            if len(kept) >= self.max_total:
                stats.balance_removed += 1
                continue
            cat = category_bucket(rec)
            persona = persona_bucket(rec)
            cat_cap = self.category_caps.get(cat, default_cat_cap)
            per_cap = self.persona_caps.get(persona, default_persona_cap)
            if cat_counts[cat] >= cat_cap or persona_counts[persona] >= per_cap:
                stats.balance_removed += 1
                continue
            kept.append(rec)
            cat_counts[cat] += 1
            persona_counts[persona] += 1
            stats.buckets[f"{cat}/{persona}"] = stats.buckets.get(f"{cat}/{persona}", 0) + 1

        stats.output_count = len(kept)

        if rebuild_index:
            index_entries = []
            for rec in kept:
                user, assistant = record_user_assistant(rec)
                index_entries.append({
                    "hash": content_hash(rec),
                    "vector": embed_text(f"{user}\n{assistant}"),
                    "category": category_bucket(rec),
                    "persona": persona_bucket(rec),
                })
            self.save_index(index_entries)

        return kept, stats

    def is_near_duplicate(self, rec: dict[str, Any]) -> bool:
        """Fast check before appending to curated queue."""
        h = content_hash(rec)
        for row in self._load_index():
            if row.get("hash") == h:
                return True
        user, assistant = record_user_assistant(rec)
        text = f"{user}\n{assistant}".strip()
        if not text:
            return True
        vec = embed_text(text)
        for row in self._load_index():
            existing = row.get("vector")
            if existing and cosine(vec, existing) >= self.threshold:
                return True
        return False

    def register_record(self, rec: dict[str, Any]) -> None:
        user, assistant = record_user_assistant(rec)
        entries = self._load_index()
        entries.append({
            "hash": content_hash(rec),
            "vector": embed_text(f"{user}\n{assistant}"),
            "category": category_bucket(rec),
            "persona": persona_bucket(rec),
            "ts": datetime.now(UTC).isoformat(),
        })
        if len(entries) > self.max_total * 2:
            entries = entries[-self.max_total :]
        self.save_index(entries)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def clean_file(path: Path, *, rebuild_index: bool = False) -> DietStats:
    diet = DataDiet()
    records = load_jsonl(path)
    kept, stats = diet.apply(records, rebuild_index=rebuild_index)
    write_jsonl(path, kept)
    return stats


def clean_all_datasets(*, rebuild_index: bool = True) -> dict[str, Any]:
    diet = DataDiet()
    paths = [
        ROOT / "data" / "learning" / "curated_train.jsonl",
        ROOT / "training" / "datasets" / "jekyll_hyde_train.jsonl",
    ]
    report: dict[str, Any] = {"files": {}, "total_removed": 0}
    all_kept: list[dict[str, Any]] = []

    for path in paths:
        if not path.exists():
            continue
        records = load_jsonl(path)
        kept, stats = diet.apply(records, rebuild_index=False)
        write_jsonl(path, kept)
        report["files"][str(path.relative_to(ROOT))] = stats.to_dict()
        report["total_removed"] += stats.input_count - stats.output_count
        all_kept.extend(kept)

    # Rebuild global embedding index from merged unique set
    if rebuild_index:
        _, final_stats = diet.apply(all_kept, rebuild_index=True)
        report["index"] = final_stats.to_dict()

    hash_file = ROOT / "data" / "learning" / "curated_hashes.txt"
    hashes = sorted({content_hash(r) for r in all_kept})
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    hash_file.write_text("\n".join(hashes) + ("\n" if hashes else ""), encoding="utf-8")
    report["hash_count"] = len(hashes)
    return report
