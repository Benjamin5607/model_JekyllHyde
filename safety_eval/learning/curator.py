"""Promote high-quality interactions into LoRA training records."""

from __future__ import annotations

import re

from safety_eval.learning.store import InteractionRecord, LearningStore, get_learning_store
from safety_eval.platform.formats import build_format_block
from safety_eval.platform.output_guard import is_simple_greeting, looks_like_template_leak
from safety_eval.store import get_guidelines_store

_CURATED_FORMATS = frozenset({
    "report", "market_analysis", "comparison", "how_to", "summary",
    "plan", "list", "technical", "refusal", "hyde_probe", "moderation_verdict",
    "swot", "faq", "news_brief", "research_brief", "decision_matrix", "timeline",
    "guideline_audit", "gray_zone_map", "policy_hardening", "investment_memo",
})


class LearningCurator:
    def __init__(self, store: LearningStore | None = None):
        self.store = store or get_learning_store()
        self.cfg = self.store.cfg

    def _min_score(self) -> float:
        return self.cfg.get("quality", {}).get("min_quality_score", 0.65)

    def _passes_quality(self, rec: InteractionRecord, *, force: bool = False) -> bool:
        if rec.rejected or rec.curated:
            return False
        if rec.feedback == "down":
            return False
        if looks_like_template_leak(rec.assistant):
            return False
        if force or rec.feedback == "up":
            return True
        qcfg = self.cfg.get("quality", {})
        for pat in qcfg.get("reject_leak_patterns", []):
            if re.search(pat, rec.assistant, re.I):
                return False
        if len(rec.assistant) < qcfg.get("min_assistant_chars", 80):
            if not is_simple_greeting(rec.user):
                return False
        simple = is_simple_greeting(rec.user)
        if simple and len(rec.assistant) > 320:
            return False
        if qcfg.get("require_markdown", True) and not simple:
            if not re.search(r"(^|\n)## |^\|", rec.assistant, re.M):
                return False
        return rec.quality_score >= self._min_score()

    def to_training_record(self, rec: InteractionRecord) -> dict:
        guidelines = get_guidelines_store().text[:8000]
        force_id = rec.format_id if rec.format_id in _CURATED_FORMATS else None
        format_block, _ = build_format_block(
            rec.user,
            mode=rec.mode,
            has_quant=bool(rec.meta.get("quant")),
            force_id=force_id,
        )
        system = (
            "You are Jekyll & Hyde — an independent dual-nature model derived from Gemma architecture. "
            "You are NOT Gemma or ChatGPT. Respond in the user's language.\n\n"
            f"GUIDELINES:\n{guidelines}\n\n{format_block}"
        )
        return {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": rec.user},
                {"role": "assistant", "content": rec.assistant},
            ],
            "meta": {
                "source": "continuous_learning",
                "interaction_id": rec.id,
                "format": rec.format_id,
                "mode": rec.mode,
                "language": rec.language,
                "quality_score": rec.quality_score,
            },
        }

    def try_curate(self, rec: InteractionRecord, *, force: bool = False) -> bool:
        if not self._passes_quality(rec, force=force):
            return False
        if not self.store.append_curated_training(self.to_training_record(rec)):
            return False
        self.store.mark_curated(rec.id)
        return True

    def curate_pending(self) -> int:
        count = 0
        for rec in self.store.iter_interactions(uncured_only=True):
            if self.try_curate(rec):
                count += 1
        return count
