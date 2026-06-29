"""Continuous lightweighting — prune artifacts and re-quantize when weights change."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
MERGED = ROOT / "models" / "merged" / "jekyll-hyde"
_lock = threading.Lock()
_last_requantize_attempt: float = 0.0


def _load_cfg() -> dict[str, Any]:
    path = ROOT / "config" / "storage.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("lightweight", {})


def _merged_mtime() -> float:
    if not MERGED.exists():
        return 0.0
    latest = 0.0
    for p in MERGED.rglob("*"):
        if p.is_file():
            latest = max(latest, p.stat().st_mtime)
    return latest


def _gguf_path(quant: str) -> Path:
    tag = quant.lower().replace("-", "_")
    return MERGED / f"jekyll-hyde-{tag}.gguf"


def prune_gguf_artifacts(*, keep_quant: str = "q4_k_m") -> dict[str, Any]:
    """Drop F16 intermediates and stale GGUF quants; keep the configured target."""
    removed: list[str] = []
    if not MERGED.exists():
        return {"removed": removed, "skipped": True}

    keep = _gguf_path(keep_quant)
    for path in list(MERGED.glob("*.gguf")):
        if path.name.endswith("-f16.gguf"):
            path.unlink(missing_ok=True)
            removed.append(path.name)
            continue
        if keep.exists() and path.resolve() == keep.resolve():
            continue
        if path.suffix == ".gguf":
            path.unlink(missing_ok=True)
            removed.append(path.name)
    return {"removed": removed, "keep": keep.name if keep.exists() else None}


def maybe_requantize(*, force: bool = False) -> dict[str, Any]:
    """Re-export GGUF when merged weights are newer than the kept quant file."""
    global _last_requantize_attempt

    cfg = _load_cfg()
    if not cfg.get("enabled", True):
        return {"skipped": True, "reason": "lightweight disabled"}

    quant = str(cfg.get("keep_gguf_quant", "q4_k_m"))
    if not cfg.get("auto_requantize_after_train", True) and not force:
        return {"skipped": True, "reason": "auto requantize disabled"}

    out = _gguf_path(quant)
    merged_ts = _merged_mtime()
    gguf_ts = out.stat().st_mtime if out.exists() else 0.0
    if not force and merged_ts <= gguf_ts:
        return {"skipped": True, "reason": "gguf up to date", "path": str(out) if out.exists() else None}

    cooldown = int(cfg.get("requantize_cooldown_minutes", 30)) * 60
    now = datetime.now(UTC).timestamp()
    with _lock:
        if not force and now - _last_requantize_attempt < cooldown:
            return {"skipped": True, "reason": "cooldown"}
        _last_requantize_attempt = now

    from training.quantize_export import export_gguf

    result = export_gguf(quantize=quant, prune_old=bool(cfg.get("prune_old_gguf", True)))
    if result.get("ok"):
        prune_gguf_artifacts(keep_quant=quant)
    return result


def register_top_moe_bucket() -> dict[str, Any]:
    """Surface the most-used MoE bucket for serving-layer hints."""
    from safety_eval.platform.lora_mix_cache import load_mix_stats, top_bucket_snap

    stats = load_mix_stats()
    snap = top_bucket_snap()
    if not snap:
        return {"skipped": True, "reason": "no_usage_stats"}
    return {
        "top_bucket": stats.get("top_bucket"),
        "total_requests": stats.get("total", 0),
        "recommended_mix": snap.to_dict(),
        "counts": stats.get("counts", {}),
    }


def run_lightweight_cycle(*, force_requantize: bool = False) -> dict[str, Any]:
    """Storage optimize + GGUF prune + optional re-quantize loop tick."""
    from safety_eval.storage.optimizer import get_optimizer

    cfg = _load_cfg()
    report: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "enabled": bool(cfg.get("enabled", True)),
    }
    if not report["enabled"]:
        return report

    report["storage"] = get_optimizer().optimize()
    keep_quant = str(cfg.get("keep_gguf_quant", "q4_k_m"))
    report["gguf_prune"] = prune_gguf_artifacts(keep_quant=keep_quant)
    if cfg.get("auto_requantize_after_train", True) or force_requantize:
        report["requantize"] = maybe_requantize(force=force_requantize)
    if cfg.get("track_top_moe_bucket", True):
        report["moe_serving"] = register_top_moe_bucket()
    if cfg.get("consolidate_memory", True):
        from safety_eval.learning.memory_store import consolidate_memory_if_needed

        report["memory_consolidation"] = consolidate_memory_if_needed()
    report["disk"] = get_optimizer().disk_summary()
    return report


def main() -> None:
    import json

    print(json.dumps(run_lightweight_cycle(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
