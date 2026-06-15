"""Score and record chat turns for continuous learning."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from safety_eval.learning.curator import LearningCurator
from safety_eval.learning.store import InteractionRecord, LearningStore, get_learning_store

_LEAK = re.compile(r"(^|\n)model(\n|$)|<start_of_turn>|Hyde test probe:", re.I)
_STRUCTURE = re.compile(r"(^|\n)## |^\|.+\|$|\n\d+\. ", re.M)


class LearningCollector:
    def __init__(self, store: LearningStore | None = None):
        self.store = store or get_learning_store()
        self.curator = LearningCurator(self.store)
        self.cfg = self.store.cfg

    def score_quality(
        self,
        user: str,
        assistant: str,
        *,
        meta: dict[str, Any] | None = None,
        feedback: str | None = None,
    ) -> float:
        meta = meta or {}
        if meta.get("error") or meta.get("guard"):
            return 0.0
        if not assistant or not user:
            return 0.0

        score = 0.4
        qcfg = self.cfg.get("quality", {})
        min_chars = qcfg.get("min_assistant_chars", 80)

        if len(assistant.strip()) >= min_chars:
            score += 0.2
        if _STRUCTURE.search(assistant):
            score += 0.15
        if meta.get("format") and meta["format"] != "conversational":
            score += 0.1
        if meta.get("domains"):
            score += 0.1
        specialist_formats = {
            "market_analysis", "guideline_audit", "gray_zone_map",
            "policy_hardening", "investment_memo", "moderation_verdict",
        }
        if meta.get("format") in specialist_formats:
            score += 0.1
        if _LEAK.search(assistant):
            score -= 0.5

        for pat in qcfg.get("reject_leak_patterns", []):
            if re.search(pat, assistant, re.I | re.M):
                score -= 0.3
                break

        if feedback == "up":
            score += self.cfg.get("feedback", {}).get("upvote_boost", 0.35)
        elif feedback == "down":
            score -= 0.6

        return max(0.0, min(1.0, score))

    def record_turn(
        self,
        *,
        user: str,
        assistant: str,
        mode: str = "chat",
        format_id: str = "conversational",
        language: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> InteractionRecord | None:
        meta = meta or {}
        if meta.get("error") or not assistant.strip():
            return None

        score = self.score_quality(user, assistant, meta=meta)
        rec = InteractionRecord(
            id=self.store.new_id(),
            ts=datetime.now(UTC).isoformat(),
            user=user.strip(),
            assistant=assistant.strip(),
            mode=mode,
            format_id=format_id,
            language=language or "en",
            quality_score=score,
            meta=meta,
        )
        self.store.append_interaction(rec)

        auto = self.cfg.get("auto", {})
        if auto.get("curate_after_each_turn", True):
            self.curator.try_curate(rec)

        from safety_eval.learning.pipeline import get_pipeline

        get_pipeline().maybe_start_training()
        return rec

    def apply_feedback(self, interaction_id: str, feedback: str) -> dict[str, Any]:
        updated = self.store.update_feedback(interaction_id, feedback)
        if not updated:
            return {"ok": False, "error": "not_found"}

        updated.quality_score = self.score_quality(
            updated.user,
            updated.assistant,
            meta=updated.meta,
            feedback=feedback,
        )

        if feedback == "down" and self.cfg.get("feedback", {}).get("downvote_reject", True):
            self.store.mark_rejected(interaction_id)
            self.store.append_rejected(updated, "user_downvote")
            return {"ok": True, "action": "rejected"}

        if feedback == "up":
            promoted = self.curator.try_curate(updated, force=True)
            from safety_eval.learning.pipeline import get_pipeline

            get_pipeline().maybe_start_training()
            return {"ok": True, "action": "curated" if promoted else "queued"}

        return {"ok": True, "action": "recorded"}


_collector: LearningCollector | None = None


def get_collector() -> LearningCollector:
    global _collector
    if _collector is None:
        _collector = LearningCollector()
    return _collector
