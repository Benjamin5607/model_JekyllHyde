"""Replay engine — Action → Snapshot → Replay → Verify + confidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from decision_architecture.engine.types import Action, Snapshot, State

TransitionFn = Callable[[State, Action], State]
VerifyFn = Callable[[State, State], bool]


@dataclass
class ReplayResult:
    ok: bool
    snapshots: list[Snapshot] = field(default_factory=list)
    final_state: State | None = None
    errors: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "confidence": self.confidence,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "final_state": self.final_state.to_dict() if self.final_state else None,
            "errors": self.errors,
        }


class ReplayEngine:
    def __init__(self) -> None:
        self._recordings: dict[str, list[Snapshot]] = {}

    def snapshot(self, state: State, action: Action | None = None, **metadata: Any) -> Snapshot:
        return Snapshot(state=state, action=action, metadata=dict(metadata))

    def record(self, recording_id: str, snapshot: Snapshot) -> None:
        self._recordings.setdefault(recording_id, []).append(snapshot)

    def get_recording(self, recording_id: str) -> list[Snapshot]:
        return list(self._recordings.get(recording_id, []))

    def replay(
        self,
        *,
        initial: State,
        actions: Sequence[Action],
        transition: TransitionFn,
        expected_final: State | None = None,
        verify: VerifyFn | None = None,
        recording_id: str | None = None,
        trials: int = 1,
    ) -> ReplayResult:
        """
        Replay once (or trials times) and compute replay_confidence = success_rate.
        """
        successes = 0
        last: ReplayResult | None = None
        for _ in range(max(1, trials)):
            result = self._replay_once(
                initial=initial,
                actions=actions,
                transition=transition,
                expected_final=expected_final,
                verify=verify,
                recording_id=recording_id,
            )
            last = result
            if result.ok:
                successes += 1
        assert last is not None
        last.confidence = successes / max(1, trials)
        last.ok = last.confidence >= 0.5
        return last

    def _replay_once(
        self,
        *,
        initial: State,
        actions: Sequence[Action],
        transition: TransitionFn,
        expected_final: State | None,
        verify: VerifyFn | None,
        recording_id: str | None,
    ) -> ReplayResult:
        state = initial
        snapshots: list[Snapshot] = [self.snapshot(state, metadata={"phase": "initial"})]
        errors: list[str] = []
        for i, action in enumerate(actions):
            try:
                state = transition(state, action)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"step {i} ({action.name}): {exc}")
                break
            snap = self.snapshot(state, action=action, step=i)
            snapshots.append(snap)
            if recording_id:
                self.record(recording_id, snap)
        ok = not errors
        if expected_final is not None and ok:
            if verify is not None:
                ok = verify(state, expected_final)
            else:
                ok = state.cell_key == expected_final.cell_key
            if not ok:
                errors.append("final state mismatch")
        return ReplayResult(ok=ok, snapshots=snapshots, final_state=state, errors=errors)
