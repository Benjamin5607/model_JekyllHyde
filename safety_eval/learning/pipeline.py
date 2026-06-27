"""Orchestrate dataset merge and incremental LoRA retraining."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from safety_eval.learning.store import LearningState, get_learning_store
from safety_eval.storage.optimizer import get_optimizer

ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON = ROOT / ".venv-train" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

_train_lock = threading.Lock()
_pipeline: LearningPipeline | None = None


class LearningPipeline:
    def __init__(self):
        self.store = get_learning_store()
        self.cfg = self.store.cfg

    def maybe_merge_dataset(self) -> bool:
        prepare = ROOT / "training" / "prepare_dataset.py"
        if not prepare.exists():
            return False
        try:
            subprocess.run(
                [str(PYTHON), str(prepare)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            return True
        except Exception as exc:
            state = self.store.load_state()
            state.last_error = f"merge: {exc}"
            self.store.save_state(state)
            return False

    def _can_train(self, state: LearningState) -> bool:
        auto = self.cfg.get("auto", {})
        if not auto.get("auto_train_enabled", False):
            return False
        if state.training_in_progress:
            return False
        if state.curated_since_train < auto.get("train_when_curated_reaches", 20):
            return False
        if state.last_train_at:
            try:
                last = datetime.fromisoformat(state.last_train_at)
                hours = auto.get("train_min_interval_hours", 6)
                if datetime.now(UTC) - last.replace(tzinfo=UTC) < timedelta(hours=hours):
                    return False
            except ValueError:
                pass
        return True

    def maybe_start_training(self) -> dict:
        state = self.store.load_state()
        if not self._can_train(state):
            return {"started": False}

        if not _train_lock.acquire(blocking=False):
            return {"started": False, "reason": "busy"}

        def _run() -> None:
            try:
                self._run_training_cycle()
            finally:
                _train_lock.release()

        threading.Thread(target=_run, daemon=True, name="jh-learn-train").start()
        return {"started": True}

    def _run_gguf_export(self, qcfg: dict) -> dict:
        if not qcfg.get("export_gguf_after_train", True):
            return {"skipped": True, "reason": "disabled in config"}
        proc = subprocess.run(
            [
                str(PYTHON),
                str(ROOT / "training" / "quantize_export.py"),
                "--quant",
                qcfg.get("gguf_quant", "q4_k_m"),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=7200,
        )
        if proc.returncode != 0:
            return {"ok": False, "reason": (proc.stderr or proc.stdout or "quantize failed")[-400:]}
        try:
            return json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return {"ok": False, "reason": proc.stdout[-400:] or "unknown quantize output"}

    def _run_training_cycle(self) -> None:
        state = self.store.load_state()
        state.training_in_progress = True
        state.last_error = ""
        self.store.save_state(state)

        auto = self.cfg.get("auto", {})
        base = auto.get("train_base", "gemma2-2b")
        epochs = auto.get("train_epochs_incremental", 2)
        qcfg = self.cfg.get("quantize", {})

        try:
            get_optimizer().optimize()
            self.maybe_merge_dataset()
            train_cmds = [
                [
                    str(PYTHON),
                    str(ROOT / "training" / "train_lora.py"),
                    "--base",
                    base,
                    "--4bit",
                    "--epochs",
                    str(epochs),
                    "--persona",
                    "both",
                ],
                [str(PYTHON), str(ROOT / "training" / "merge_and_export.py"), "--base", base],
            ]
            for cmd in train_cmds:
                proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=7200)
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr[-800:] or proc.stdout[-800:] or "train failed")

            gguf_result = self._run_gguf_export(qcfg)
            if not gguf_result.get("ok") and not gguf_result.get("skipped"):
                note = gguf_result.get("reason", "gguf export failed")
                if not gguf_result.get("skipped"):
                    state = self.store.load_state()
                    state.last_error = f"gguf: {note}"[:500]
                    self.store.save_state(state)

            from safety_eval.platform.local_model import reload_model

            reload_model()

            state = self.store.load_state()
            state.generation += 1
            state.last_train_at = datetime.now(UTC).isoformat()
            state.curated_since_train = 0
            state.last_train_samples = state.curated_total
            state.training_in_progress = False
            if gguf_result.get("ok"):
                state.last_error = ""
            self.store.save_state(state)
        except Exception as exc:
            state = self.store.load_state()
            state.training_in_progress = False
            state.last_error = str(exc)[:500]
            self.store.save_state(state)

    def run_now(self, *, train: bool = True) -> dict:
        from safety_eval.learning.curator import LearningCurator

        curated = LearningCurator(self.store).curate_pending()
        merged = self.maybe_merge_dataset()
        result = {"curated": curated, "merged": merged, **self.store.status()}
        if train:
            if _train_lock.acquire(blocking=False):
                try:
                    self._run_training_cycle()
                    result["train"] = {"started": True, **self.store.status()}
                finally:
                    _train_lock.release()
            else:
                result["train"] = {"started": False, "reason": "busy"}
        return result


def get_pipeline() -> LearningPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = LearningPipeline()
    return _pipeline
