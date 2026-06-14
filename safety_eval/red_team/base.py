"""Red team base interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from safety_eval.models import Severity


class AttackMode(str, Enum):
    """How the red team prompt challenges the blue team."""

    VIOLATION = "violation"  # clear breach — blue should block
    EVASION = "evasion"  # disguised breach — blue should block
    GRAY_ZONE = "gray_zone"  # borderline — blue should flag or block


@dataclass(frozen=True)
class RedTeamPrompt:
    """Adversarial user prompt generated for blue-team detection testing."""

    id: str
    prompt: str
    category: str
    technique: str
    severity: Severity = Severity.MEDIUM
    seed_id: str = ""
    attack_mode: AttackMode = AttackMode.VIOLATION
    guideline_section: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def should_block(self) -> bool:
        return self.attack_mode in (AttackMode.VIOLATION, AttackMode.EVASION)

    @property
    def should_flag(self) -> bool:
        return self.attack_mode == AttackMode.GRAY_ZONE


class BaseRedTeam(ABC):
    name: str = "base"
    guidelines_title: str | None = None

    @abstractmethod
    def generate(
        self,
        *,
        categories: list[str] | None = None,
        count: int = 10,
        attack_modes: list[str] | None = None,
        memory: "HydeMemory | None" = None,
    ) -> list[RedTeamPrompt]:
        """Generate adversarial prompts targeting community guidelines."""
