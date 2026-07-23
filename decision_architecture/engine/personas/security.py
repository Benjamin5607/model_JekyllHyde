"""Explorer / Critic / Verifier / Attacker / Defender — security personas."""

from __future__ import annotations

from typing import Any, Mapping

from decision_architecture.engine.personas.base import Persona
from decision_architecture.engine.types import ScoreVector, State


class ExplorerPersona(Persona):
    name = "explorer"
    role = "search"
    system_prompt = "Prefer under-visited cells and novel tool sequences."

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        novelty = float(context.get("novelty", 0.0) or 0.0)
        bias = 0.25 * novelty
        if any(k in label for k in ("explore", "mutate", "sequence", "open", "search")):
            bias += 0.2
        return bias

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(state, stance="explore", rationale="신규 셀 / 툴 시퀀스 우선.")


class CriticPersona(Persona):
    name = "critic"
    role = "review"
    system_prompt = "Challenge weak plans; prefer falsifiable options."

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        if any(k in label for k in ("verify", "replay", "check")):
            return 0.15
        if "blind" in label:
            return -0.2
        return 0.0

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(state, stance="critique", rationale="논증·재현성 재평가.")


class VerifierPersona(Persona):
    name = "verifier"
    role = "verify"
    system_prompt = "Prefer replayable, independently verifiable options."

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        if any(k in label for k in ("replay", "verify", "snapshot", "confirm")):
            return 0.25
        return 0.05 if context.get("replayable") else -0.05

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(state, stance="verify", rationale="리플레이·검증 가능성 기준.")


class AttackerPersona(Persona):
    name = "attacker"
    role = "red_team"
    system_prompt = "Maximize coverage of threat beliefs with authorized attack sequences."

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        if any(k in label for k in ("inject", "exfil", "bypass", "tool", "sequence", "post", "delete")):
            return 0.3
        belief = context.get("belief", {}) or {}
        posterior = belief.get("posterior", belief) if isinstance(belief, dict) else {}
        return 0.15 * float(posterior.get("prompt_injection", 0.4) or 0.4)

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(
            state,
            stance="attack",
            rationale="위협 Belief에 정렬된 공격 시퀀스.",
            risks=["authorized_lab_only"],
        )


class DefenderPersona(Persona):
    name = "defender"
    role = "blue_team"
    system_prompt = "Propose mitigations; refuse unsafe execution paths."

    def _label_bias(self, label: str, context: Mapping[str, Any]) -> float:
        if any(k in label for k in ("mitigate", "block", "sandbox", "harden", "guard")):
            return 0.3
        if any(k in label for k in ("attack", "inject", "exfil")):
            return -0.2
        return 0.0

    def think(self, state: State) -> ScoreVector:
        return self._vector_from_options(state, stance="defend", rationale="완화·샌드박스 우선.")
