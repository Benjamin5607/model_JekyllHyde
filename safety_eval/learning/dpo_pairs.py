"""Build DPO preference pairs from curated_train.jsonl and rejected.jsonl."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from safety_eval.learning.diet import cosine, embed_text, normalize_text, record_user_assistant

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"


def _load_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("dpo", {})


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _user_text_from_record(rec: dict[str, Any]) -> str:
    if rec.get("user"):
        return str(rec["user"])
    user, _ = record_user_assistant(rec)
    return user


def _assistant_text_from_record(rec: dict[str, Any]) -> str:
    if rec.get("assistant"):
        return str(rec["assistant"])
    _, assistant = record_user_assistant(rec)
    return assistant


def _best_chosen_match(user: str, curated: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not curated:
        return None
    u_norm = normalize_text(user)
    for rec in curated:
        cu = _user_text_from_record(rec)
        if normalize_text(cu) == u_norm:
            return rec
    qvec = embed_text(user)
    best: tuple[float, dict[str, Any]] | None = None
    for rec in curated:
        cu = _user_text_from_record(rec)
        sim = cosine(qvec, embed_text(cu))
        if best is None or sim > best[0]:
            best = (sim, rec)
    if best and best[0] >= 0.55:
        return best[1]
    return curated[0]


def build_preference_pairs(
    *,
    curated_path: Path | None = None,
    rejected_path: Path | None = None,
) -> list[dict[str, str]]:
    """Return DPO rows: prompt, chosen, rejected."""
    paths = (_load_config_paths() if curated_path is None else {})
    curated_path = curated_path or ROOT / paths.get("curated", "data/learning/curated_train.jsonl")
    rejected_path = rejected_path or ROOT / paths.get("rejected", "data/learning/rejected.jsonl")

    curated = _load_jsonl(curated_path)
    rejected = _load_jsonl(rejected_path)
    pairs: list[dict[str, str]] = []

    for rej in rejected:
        user = _user_text_from_record(rej)
        rejected_resp = _assistant_text_from_record(rej)
        if len(user) < 8 or len(rejected_resp) < 20:
            continue
        match = _best_chosen_match(user, curated)
        if match:
            chosen_resp = _assistant_text_from_record(match)
        else:
            from training.mcp_tool_examples import mcp_tool_training_records

            gold = mcp_tool_training_records("SYSTEM")
            chosen_resp = record_user_assistant(gold[0])[1] if gold else rejected_resp[:200]
        if normalize_text(chosen_resp) == normalize_text(rejected_resp):
            continue
        pairs.append(
            {
                "prompt": user,
                "chosen": chosen_resp,
                "rejected": rejected_resp,
                "reject_reason": str(rej.get("reject_reason", rej.get("meta", {}).get("rlaif", ""))),
            }
        )

    # Synthetic pairs from MCP gold examples vs malformed JSON
    from training.mcp_tool_examples import mcp_tool_training_records

    for rec in mcp_tool_training_records("SYSTEM"):
        user, chosen = record_user_assistant(rec)
        if len(chosen) < 40:
            continue
        pairs.append(
            {
                "prompt": user,
                "chosen": chosen,
                "rejected": '{"tool_calls": [{name: broken, arguments: }]}',
                "reject_reason": "synthetic_mcp_grammar",
            }
        )

    # Curated high-quality vs template-leak style rejections
    for rec in curated:
        user, chosen = record_user_assistant(rec)
        if len(chosen) < 60:
            continue
        pairs.append(
            {
                "prompt": user,
                "chosen": chosen,
                "rejected": "RESPONSE TEMPLATE\nKEY CONCEPT\n" + chosen[:80],
                "reject_reason": "synthetic_template_leak",
            }
        )

    return pairs


def _load_config_paths() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("paths", {})


def export_dpo_dataset(out_path: Path | None = None) -> dict[str, Any]:
    cfg = _load_cfg()
    pairs = build_preference_pairs()
    out_path = out_path or ROOT / cfg.get("dataset_path", "data/learning/dpo_pairs.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in pairs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"path": str(out_path), "pairs": len(pairs), "min_pairs": int(cfg.get("min_pairs", 4))}


def pair_count() -> int:
    return len(build_preference_pairs())
