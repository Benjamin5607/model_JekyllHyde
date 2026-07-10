"""MCP Mesh protocol — Manager dispatches workers to remote nodes."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "mesh.yaml"

_lock = threading.Lock()
_nodes: dict[str, dict[str, Any]] = {}


@dataclass
class MeshTask:
    id: str
    worker: str
    args: dict[str, Any] = field(default_factory=dict)
    node_id: str = ""
    status: str = "pending"
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_mesh_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"mesh": {"enabled": False}}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def mesh_enabled() -> bool:
    return bool(_load_mesh_cfg().get("mesh", {}).get("enabled", False))


def list_nodes() -> list[dict[str, Any]]:
    cfg = _load_mesh_cfg()
    return list(cfg.get("nodes", []))


def pick_node(worker: str) -> dict[str, Any] | None:
    """Select a remote node that advertises this worker capability."""
    if not mesh_enabled():
        return None
    prefer = set(_load_mesh_cfg().get("mesh", {}).get("prefer_remote_for", []))
    if worker not in prefer:
        return None
    for node in list_nodes():
        workers = node.get("workers") or []
        if worker in workers and node.get("url"):
            return node
    return None


def dispatch_remote(worker: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST task to remote mesh worker HTTP endpoint."""
    node = pick_node(worker)
    if not node:
        raise RuntimeError(f"no mesh node for worker={worker}")

    task_id = uuid.uuid4().hex[:12]
    payload = {
        "task_id": task_id,
        "worker": worker,
        "args": args or {},
        "manager_id": _load_mesh_cfg().get("mesh", {}).get("node_id", "manager"),
    }
    url = f"{node['url'].rstrip('/')}/mesh/run"
    timeout = float(_load_mesh_cfg().get("mesh", {}).get("task_timeout_seconds", 120))
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


def register_local_node(node_id: str, workers: list[str], port: int = 8092) -> dict[str, Any]:
    """Return node descriptor for mesh.yaml documentation."""
    return {
        "id": node_id,
        "url": f"http://127.0.0.1:{port}",
        "workers": workers,
        "registered_at": datetime.now(UTC).isoformat(),
    }


# --- Hub (optional central registry on manager PC) ---

_hub_tasks: dict[str, MeshTask] = {}


def hub_enqueue(worker: str, args: dict[str, Any] | None = None) -> MeshTask:
    task = MeshTask(
        id=uuid.uuid4().hex[:12],
        worker=worker,
        args=args or {},
        created_at=datetime.now(UTC).isoformat(),
    )
    with _lock:
        _hub_tasks[task.id] = task
    return task


def hub_complete(task_id: str, *, ok: bool, output: dict[str, Any] | None = None, error: str = "") -> MeshTask | None:
    with _lock:
        task = _hub_tasks.get(task_id)
        if not task:
            return None
        task.status = "ok" if ok else "failed"
        task.result = output or {}
        task.error = error
        task.completed_at = datetime.now(UTC).isoformat()
        return task


def hub_status() -> dict[str, Any]:
    with _lock:
        tasks = [t.to_dict() for t in _hub_tasks.values()]
    return {
        "enabled": mesh_enabled(),
        "nodes": list_nodes(),
        "tasks": tasks[-20:],
    }


def run_worker_local(worker: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    from safety_eval.mcp.workforce import WORKER_REGISTRY

    fn = WORKER_REGISTRY.get(worker)
    if not fn:
        raise KeyError(f"unknown worker: {worker}")
    return fn(**(args or {}))
