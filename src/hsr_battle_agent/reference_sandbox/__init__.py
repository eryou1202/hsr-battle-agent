"""Post-baseline reference combat sandbox with explicit local actions."""

from .contract import (
    COMPLETION_POLICY, SCHEDULE_POLICY, SCOPE, TERMINAL_POLICY,
    ReferenceActionEnvelope, ReferenceSandboxBlocked, ReferenceSessionSpec,
)
from .replay import make_replay_record, replay_session
from .session import ReferenceBattleSession, ReferenceStepResult

__all__ = [
    "COMPLETION_POLICY", "SCHEDULE_POLICY", "SCOPE", "TERMINAL_POLICY",
    "ReferenceActionEnvelope", "ReferenceSandboxBlocked", "ReferenceSessionSpec",
    "ReferenceBattleSession", "ReferenceStepResult", "make_replay_record", "replay_session",
]
