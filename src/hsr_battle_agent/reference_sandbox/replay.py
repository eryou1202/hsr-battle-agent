"""Independent deterministic re-execution of local action session records."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from hsr_battle_agent.battle_sandbox.canonical_v2 import canonical_v2_bytes

from .contract import ReferenceSandboxBlocked, ReferenceSessionSpec
from .session import ReferenceBattleSession, ReferenceStepResult


def make_replay_record(initial: ReferenceBattleSession,
                       steps: Sequence[ReferenceStepResult]) -> dict[str, Any]:
    if not isinstance(initial, ReferenceBattleSession):
        raise ReferenceSandboxBlocked("INVALID_REPLAY_INITIAL")
    return {
        "schema": "ReferenceBattleReplay/1",
        "spec": initial.spec.to_dict(),
        "initial_snapshot": initial.initial_snapshot.to_dict(),
        "initial_hash": initial.semantic_hash(),
        "steps": [step.to_dict() for step in steps],
        "validation": "DETERMINISTIC_REPLAY_ONLY",
    }


def replay_session(record: Mapping[str, Any]) -> ReferenceBattleSession:
    if not isinstance(record, Mapping) or set(record) != {
        "schema", "spec", "initial_snapshot", "initial_hash", "steps", "validation"
    } or record["schema"] != "ReferenceBattleReplay/1" or record["validation"] != "DETERMINISTIC_REPLAY_ONLY":
        raise ReferenceSandboxBlocked("INVALID_REPLAY_RECORD")
    try:
        spec = ReferenceSessionSpec.from_dict(record["spec"])
        current = ReferenceBattleSession.create(spec)
        if canonical_v2_bytes(current.initial_snapshot.to_dict()) != canonical_v2_bytes(record["initial_snapshot"]):
            raise ReferenceSandboxBlocked("REPLAY_INITIAL_MISMATCH")
        if current.semantic_hash() != record["initial_hash"]:
            raise ReferenceSandboxBlocked("REPLAY_INITIAL_HASH_MISMATCH")
        if not isinstance(record["steps"], list):
            raise ReferenceSandboxBlocked("INVALID_REPLAY_STEPS")
        for recorded in record["steps"]:
            if not isinstance(recorded, Mapping) or not isinstance(recorded.get("selected_action_id"), str):
                raise ReferenceSandboxBlocked("INVALID_REPLAY_STEP")
            actual = current.step(recorded["selected_action_id"])
            if canonical_v2_bytes(actual.to_dict()) != canonical_v2_bytes(recorded):
                raise ReferenceSandboxBlocked("REPLAY_STEP_MISMATCH")
            current = actual.session
        return current
    except ReferenceSandboxBlocked:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ReferenceSandboxBlocked("REPLAY_CORRUPT", str(exc)) from exc
