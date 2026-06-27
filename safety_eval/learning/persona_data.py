"""Persona-aware training record filtering for dual LoRA adapters."""

from __future__ import annotations

from safety_eval.learning.diet import persona_bucket


def filter_records_for_persona(records: list[dict], persona: str) -> list[dict]:
    """Keep persona-specific rows plus neutral shared examples."""
    persona = (persona or "both").lower()
    if persona == "both":
        return list(records)
    out: list[dict] = []
    for rec in records:
        bucket = persona_bucket(rec)
        if bucket == persona or bucket == "neutral":
            out.append(rec)
    return out
