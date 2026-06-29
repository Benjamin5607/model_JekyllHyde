"""MoE LoRA mix buckets, usage stats, and pre-warmed adapter pool."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
STATS_PATH = ROOT / "data" / "learning" / "moe_mix_stats.json"
SERVING_PATH = ROOT / "models" / "merged" / "jekyll-hyde" / "moe_serving.json"
_lock = threading.Lock()

# Five canonical blend buckets (Jekyll : Hyde)
MOE_BUCKETS: list[tuple[str, float, float]] = [
    ("moe_j90_h10", 0.9, 0.1),
    ("moe_j70_h30", 0.7, 0.3),
    ("moe_j50_h50", 0.5, 0.5),
    ("moe_j30_h70", 0.3, 0.7),
    ("moe_j10_h90", 0.1, 0.9),
]

PURE_JEKYLL = ("jekyll", 1.0, 0.0)
PURE_HYDE = ("hyde", 0.0, 1.0)


@dataclass(frozen=True)
class BucketSnap:
    adapter_name: str
    jekyll: float
    hyde: float
    bucket_id: str

    def label(self) -> str:
        return f"J{int(self.jekyll * 100)}:H{int(self.hyde * 100)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter_name,
            "jekyll": self.jekyll,
            "hyde": self.hyde,
            "bucket": self.bucket_id,
            "label": self.label(),
        }


def snap_to_bucket(jekyll_w: float, hyde_w: float) -> BucketSnap:
    """Quantize continuous mix to nearest of five MoE buckets (or pure adapters)."""
    jw, hw = max(0.0, jekyll_w), max(0.0, hyde_w)
    if jw + hw <= 0:
        jw, hw = 1.0, 0.0
    else:
        s = jw + hw
        jw, hw = jw / s, hw / s

    if jw >= 0.95:
        return BucketSnap("jekyll", 1.0, 0.0, "pure_jekyll")
    if hw >= 0.95:
        return BucketSnap("hyde", 0.0, 1.0, "pure_hyde")

    best = MOE_BUCKETS[0]
    best_dist = 1e9
    for item in MOE_BUCKETS:
        name, bj, bh = item
        dist = (jw - bj) ** 2 + (hw - bh) ** 2
        if dist < best_dist:
            best_dist = dist
            best = item
    name, bj, bh = best
    return BucketSnap(name, bj, bh, name)


def load_mix_stats() -> dict[str, Any]:
    if not STATS_PATH.exists():
        return {"counts": {}, "total": 0, "top_bucket": None}
    try:
        return json.loads(STATS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"counts": {}, "total": 0, "top_bucket": None}


def _save_mix_stats(data: dict[str, Any]) -> None:
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_mix_usage(snap: BucketSnap) -> None:
    """Increment bucket usage for lightweight top-bucket GGUF hints."""
    with _lock:
        data = load_mix_stats()
        counts: dict[str, int] = data.get("counts") or {}
        key = snap.bucket_id
        counts[key] = counts.get(key, 0) + 1
        total = sum(counts.values())
        top = max(counts.items(), key=lambda x: x[1])[0] if counts else None
        data.update({
            "counts": counts,
            "total": total,
            "top_bucket": top,
            "last_used": snap.to_dict(),
            "updated": datetime.now(UTC).isoformat(),
        })
        _save_mix_stats(data)
        _write_serving_manifest(data)


def _write_serving_manifest(stats: dict[str, Any]) -> None:
    """Register top MoE bucket for serving / GGUF precompile hints."""
    top = stats.get("top_bucket")
    if not top:
        return
    snap = snap_to_bucket(0.7, 0.3)
    for name, j, h in MOE_BUCKETS:
        if name == top:
            snap = BucketSnap(name, j, h, name)
            break
    if top == "pure_jekyll":
        snap = BucketSnap("jekyll", 1.0, 0.0, "pure_jekyll")
    elif top == "pure_hyde":
        snap = BucketSnap("hyde", 0.0, 1.0, "pure_hyde")

    SERVING_PATH.parent.mkdir(parents=True, exist_ok=True)
    SERVING_PATH.write_text(
        json.dumps(
            {
                "top_bucket": top,
                "recommended_mix": snap.to_dict(),
                "counts": stats.get("counts", {}),
                "updated": datetime.now(UTC).isoformat(),
                "note": "Use pre-warmed PEFT bucket adapter at runtime; optional GGUF export per bucket.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def top_bucket_snap() -> BucketSnap | None:
    stats = load_mix_stats()
    top = stats.get("top_bucket")
    if not top:
        return None
    if top == "pure_jekyll":
        return BucketSnap("jekyll", 1.0, 0.0, "pure_jekyll")
    if top == "pure_hyde":
        return BucketSnap("hyde", 0.0, 1.0, "pure_hyde")
    for name, j, h in MOE_BUCKETS:
        if name == top:
            return BucketSnap(name, j, h, name)
    return None


def list_bucket_snaps() -> list[BucketSnap]:
    return [BucketSnap(n, j, h, n) for n, j, h in MOE_BUCKETS]
