"""Trace DAG + novelty helpers for Security Lab / ZeroAI UI."""

from __future__ import annotations

from typing import Any, Sequence


def build_trace_graph(tool_events: Sequence[dict[str, Any]] | Sequence[str]) -> dict[str, Any]:
    """
    Build a simple DAG:

        Email → Read → Memory → Plan → Search → Tool → HTTP → Leak
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    prev = None
    for i, ev in enumerate(tool_events):
        if isinstance(ev, str):
            name = ev
            ok = True
        else:
            name = str(ev.get("name") or ev.get("tool") or f"step_{i}")
            ok = bool(ev.get("ok", True))
        node_id = f"n{i}_{name}"
        nodes.append({"id": node_id, "label": name, "ok": ok, "index": i})
        if prev is not None:
            edges.append({"from": prev, "to": node_id})
        prev = node_id
    return {"nodes": nodes, "edges": edges}


def novelty_score(a: Sequence[str], b: Sequence[str]) -> float:
    """Jaccard-distance novelty in [0,1] (1 = fully novel)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb) or 1
    return 1.0 - (inter / union)
