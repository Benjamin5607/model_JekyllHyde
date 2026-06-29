"""RLAIF gate — verification API scoring before auto-curation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from safety_eval.learning.diet import record_user_assistant
from safety_eval.platform.output_guard import looks_like_template_leak
from safety_eval.verification.registry import run_verification

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "learning.yaml"


def _load_rlaif_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("rlaif", {})


@dataclass
class RlaifScore:
    score: float
    passed: bool
    providers_ok: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "passed": self.passed,
            "providers_ok": self.providers_ok,
            "reasons": self.reasons,
        }


class RlaifGate:
    def __init__(self, cfg: dict[str, Any] | None = None):
        self.cfg = cfg or _load_rlaif_cfg()

    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled", True))

    def threshold(self) -> float:
        return float(self.cfg.get("min_score", 85))

    def score_record(
        self,
        record: dict[str, Any],
        *,
        guidelines_text: str = "",
        topic: str = "",
    ) -> RlaifScore:
        user, assistant = record_user_assistant(record)
        meta = record.get("meta") or {}
        reasons: list[str] = []
        score = float(meta.get("quality_score", 0.65)) * 40.0  # up to 40 from prior quality

        if not assistant or len(assistant.strip()) < 40:
            return RlaifScore(0.0, False, reasons=["assistant_too_short"])

        if looks_like_template_leak(assistant):
            return RlaifScore(10.0, False, reasons=["template_leak"])

        if re.search(r"Hyde test probe:\s*$", assistant, re.I):
            return RlaifScore(20.0, False, reasons=["empty_probe"])

        # Structure bonus
        if "##" in assistant or "|" in assistant:
            score += 8.0
            reasons.append("structured_output")

        report = run_verification(
            text=assistant,
            topic=topic or user,
            guidelines_text=guidelines_text,
        )
        ok_findings = [f for f in report.findings if f.ok and f.finding]
        providers_ok = len(ok_findings)
        score += min(providers_ok * 6.0, 24.0)

        if ok_findings:
            avg_conf = sum(f.confidence for f in ok_findings) / len(ok_findings)
            score += avg_conf * 20.0
            reasons.append(f"verification_avg_conf={avg_conf:.2f}")

        inconsistent = any(
            f.meta.get("inconsistent") for f in ok_findings if f.provider == "local_logic"
        )
        if inconsistent:
            score -= 15.0
            reasons.append("logic_inconsistent")

        # Gray-reinforce patches need guideline alignment
        if meta.get("source") == "gray_reinforce":
            gl_hits = [f for f in ok_findings if f.provider == "local_guidelines"]
            if gl_hits:
                score += 10.0
                reasons.append("guidelines_crosscheck")
            else:
                score -= 5.0

        score = max(0.0, min(100.0, score))
        passed = score >= self.threshold()
        if passed:
            reasons.append("passed_threshold")
        else:
            reasons.append(f"below_threshold_{self.threshold():.0f}")

        return RlaifScore(score=score, passed=passed, providers_ok=providers_ok, reasons=reasons)

    def filter_records(
        self,
        records: list[dict[str, Any]],
        *,
        guidelines_text: str = "",
        topic: str = "",
    ) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], RlaifScore]]]:
        if not self.enabled():
            return records, []

        accepted: list[dict[str, Any]] = []
        rejected: list[tuple[dict[str, Any], RlaifScore]] = []
        for rec in records:
            result = self.score_record(rec, guidelines_text=guidelines_text, topic=topic)
            meta = dict(rec.get("meta") or {})
            meta["rlaif"] = result.to_dict()
            rec = {**rec, "meta": meta}
            if result.passed:
                accepted.append(rec)
            else:
                rejected.append((rec, result))
        return accepted, rejected


def curate_with_rlaif(
    records: list[dict[str, Any]],
    *,
    guidelines_text: str = "",
    topic: str = "",
) -> dict[str, Any]:
    """Score, gate, and append curated training rows."""
    from safety_eval.learning.store import get_learning_store

    gate = RlaifGate()
    store = get_learning_store()
    accepted, rejected = gate.filter_records(records, guidelines_text=guidelines_text, topic=topic)

    written = 0
    for rec in accepted:
        if store.append_curated_training(rec):
            written += 1
            _maybe_store_memory(rec)

    for rec, score in rejected:
        user, assistant = record_user_assistant(rec)
        from safety_eval.learning.store import InteractionRecord

        pseudo = InteractionRecord(
            id=store.new_id(),
            ts=__import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
            user=user,
            assistant=assistant,
            mode=str((rec.get("meta") or {}).get("mode", "chat")),
            format_id=str((rec.get("meta") or {}).get("format", "conversational")),
            meta={"rlaif_reject": score.to_dict(), **(rec.get("meta") or {})},
        )
        store.append_rejected(pseudo, f"rlaif:{score.score:.0f}")

    if written:
        from safety_eval.learning.pipeline import get_pipeline

        get_pipeline().maybe_start_training()

    return {
        "accepted": len(accepted),
        "rejected": len(rejected),
        "written": written,
        "threshold": gate.threshold(),
    }


def _maybe_store_memory(rec: dict[str, Any]) -> None:
    meta = rec.get("meta") or {}
    if meta.get("source") != "gray_reinforce":
        return
    try:
        from safety_eval.learning.memory_store import get_rule_memory

        user, assistant = record_user_assistant(rec)
        get_rule_memory().store_from_training(rec, topic=user)
    except Exception:
        pass
