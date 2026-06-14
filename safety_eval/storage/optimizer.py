"""Compress, rotate, dedupe, and prune local data to minimize disk usage."""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "storage.yaml"

_optimizer: StorageOptimizer | None = None
_lock = threading.Lock()


def _load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class StorageOptimizer:
    def __init__(self, cfg: dict[str, Any] | None = None):
        self.cfg = cfg or _load_config()
        paths = self.cfg.get("paths", {})
        self.logs_dir = ROOT / paths.get("logs_dir", "logs")
        self.learning_dir = ROOT / paths.get("learning_dir", "data/learning")
        self.adapters_dir = ROOT / paths.get("adapters_dir", "models/adapters")
        self.archive_dir = ROOT / paths.get("archive_dir", "data/archive")
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    @property
    def gzip_level(self) -> int:
        return int(self.cfg.get("rotation", {}).get("gzip_level", 9))

    def _gzip_file(self, src: Path, dest: Path) -> int:
        raw = src.read_bytes()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(dest, "wb", compresslevel=self.gzip_level) as gz:
            gz.write(raw)
        saved = len(raw) - dest.stat().st_size
        return saved

    def _rotate_jsonl(self, path: Path, *, max_lines: int) -> dict[str, Any]:
        if not path.exists():
            return {"rotated": False}
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if len(lines) <= max_lines:
            return {"rotated": False, "lines": len(lines)}
        keep = lines[-max_lines:]
        archive = lines[:-max_lines]
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        gz_path = self.archive_dir / f"{path.stem}_{stamp}.jsonl.gz"
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(archive) + "\n", encoding="utf-8")
        saved = self._gzip_file(tmp, gz_path)
        tmp.unlink(missing_ok=True)
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")
        return {"rotated": True, "archived": str(gz_path.name), "saved_bytes": saved, "lines_kept": len(keep)}

    def _compress_logs(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        max_bytes = int(self.cfg.get("rotation", {}).get("max_log_bytes", 2_097_152))
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        for log in self.logs_dir.glob("*.log"):
            if log.stat().st_size <= max_bytes:
                continue
            stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            gz_path = self.archive_dir / f"{log.stem}_{stamp}.log.gz"
            saved = self._gzip_file(log, gz_path)
            log.write_text("", encoding="utf-8")
            results.append({"file": log.name, "archive": gz_path.name, "saved_bytes": saved})
        return results

    def _dedupe_curated(self) -> dict[str, Any]:
        curated = self.learning_dir / "curated_train.jsonl"
        if not curated.exists():
            return {"deduped": 0}
        dedupe_cfg = self.cfg.get("dedupe", {})
        hash_file = ROOT / dedupe_cfg.get("curated_hash_file", "data/learning/curated_hashes.txt")
        known: set[str] = set()
        if hash_file.exists():
            known = {ln.strip() for ln in hash_file.read_text(encoding="utf-8").splitlines() if ln.strip()}

        kept: list[str] = []
        removed = 0
        for line in curated.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            h = hashlib.sha256(line.encode("utf-8")).hexdigest()[:16]
            if h in known:
                removed += 1
                continue
            known.add(h)
            kept.append(line)

        curated.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        hash_file.parent.mkdir(parents=True, exist_ok=True)
        hash_file.write_text("\n".join(sorted(known)) + ("\n" if known else ""), encoding="utf-8")
        return {"deduped": removed, "remaining": len(kept)}

    def _prune_adapter_checkpoints(self) -> dict[str, Any]:
        keep_n = int(self.cfg.get("prune", {}).get("keep_adapter_checkpoints", 1))
        removed: list[str] = []
        if not self.adapters_dir.exists():
            return {"removed": removed}
        for adapter in self.adapters_dir.iterdir():
            if not adapter.is_dir():
                continue
            checkpoints = sorted(
                [p for p in adapter.glob("checkpoint-*") if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for old in checkpoints[keep_n:]:
                shutil.rmtree(old, ignore_errors=True)
                removed.append(old.name)
        return {"removed": removed}

    def _prune_old_archives(self) -> dict[str, Any]:
        keep = int(self.cfg.get("rotation", {}).get("keep_archives", 12))
        archives = sorted(self.archive_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        removed = []
        for old in archives[keep:]:
            old.unlink(missing_ok=True)
            removed.append(old.name)
        return {"removed": removed}

    def _compress_rejected(self) -> dict[str, Any]:
        rejected = self.learning_dir / "rejected.jsonl"
        if not rejected.exists():
            return {"compressed": False}
        lines = [ln for ln in rejected.read_text(encoding="utf-8").splitlines() if ln.strip()]
        threshold = int(self.cfg.get("prune", {}).get("compress_rejected_after_lines", 200))
        if len(lines) <= threshold:
            return {"compressed": False, "lines": len(lines)}
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        gz_path = self.archive_dir / f"rejected_{stamp}.jsonl.gz"
        tmp = rejected.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        saved = self._gzip_file(tmp, gz_path)
        tmp.unlink(missing_ok=True)
        rejected.write_text("", encoding="utf-8")
        return {"compressed": True, "archive": gz_path.name, "saved_bytes": saved}

    def optimize(self) -> dict[str, Any]:
        with _lock:
            max_lines = int(self.cfg.get("rotation", {}).get("max_interaction_lines", 5000))
            report = {
                "ts": datetime.now(UTC).isoformat(),
                "interactions": self._rotate_jsonl(
                    self.learning_dir / "interactions.jsonl", max_lines=max_lines
                ),
                "logs": self._compress_logs(),
                "curated_dedupe": self._dedupe_curated(),
                "adapter_prune": self._prune_adapter_checkpoints(),
                "rejected": self._compress_rejected(),
                "archive_prune": self._prune_old_archives(),
            }
            report["disk"] = self.disk_summary()
            return report

    def disk_summary(self) -> dict[str, Any]:
        def dir_size(path: Path) -> int:
            if not path.exists():
                return 0
            total = 0
            for p in path.rglob("*"):
                if p.is_file():
                    total += p.stat().st_size
            return total

        learning = dir_size(self.learning_dir)
        archive = dir_size(self.archive_dir)
        logs = dir_size(self.logs_dir)
        merged = dir_size(ROOT / "models" / "merged")
        return {
            "learning_bytes": learning,
            "archive_bytes": archive,
            "logs_bytes": logs,
            "model_bytes": merged,
            "total_data_bytes": learning + archive + logs,
        }


def get_optimizer() -> StorageOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = StorageOptimizer()
    return _optimizer


def main() -> None:
    import json

    report = get_optimizer().optimize()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
