# -*- coding: utf-8 -*-
"""Battle Sandbox kernel.

The sandbox executes canonical Battle IR primitives over isolated BattleState.
It is **not** a clone of the client runtime; the client is a semantic
oracle/evidence source only.
"""
from __future__ import annotations

from hsr_battle_agent.battle_sandbox.context import ExecutionContext
from hsr_battle_agent.battle_sandbox.errors import (
    BattleSandboxError,
    DuplicatePrimitiveError,
    FrozenRegistryError,
    InvalidPrimitiveInputError,
    StubNotImplementedError,
    UnsupportedPrimitiveError,
    UnsupportedStateVersionError,
)
from hsr_battle_agent.battle_sandbox.executor import PrimitiveExecutor
from hsr_battle_agent.battle_sandbox.registry import PrimitiveRegistry
from hsr_battle_agent.battle_sandbox.rng import (
    CLIENT_RNG_ALGORITHM,
    SANDBOX_RNG,
    SANDBOX_RNG_ALGORITHM,
    SandboxRng,
)
from hsr_battle_agent.battle_sandbox.sandbox import Sandbox
from hsr_battle_agent.battle_sandbox.snapshot import SandboxSnapshot, capture_snapshot
from hsr_battle_agent.battle_sandbox.state import BATTLE_STATE_SCHEMA_VERSION, BattleState
from hsr_battle_agent.battle_sandbox.trace import (
    ExecutionTrace,
    PrimitiveFinished,
    PrimitiveStarted,
    TraceSink,
)

__all__ = [
    "BATTLE_STATE_SCHEMA_VERSION",
    "CLIENT_RNG_ALGORITHM",
    "SANDBOX_RNG",
    "SANDBOX_RNG_ALGORITHM",
    "BattleSandboxError",
    "BattleState",
    "DuplicatePrimitiveError",
    "ExecutionContext",
    "ExecutionTrace",
    "FrozenRegistryError",
    "InvalidPrimitiveInputError",
    "PrimitiveExecutor",
    "PrimitiveFinished",
    "PrimitiveRegistry",
    "PrimitiveStarted",
    "Sandbox",
    "SandboxRng",
    "SandboxSnapshot",
    "StubNotImplementedError",
    "TraceSink",
    "UnsupportedPrimitiveError",
    "UnsupportedStateVersionError",
    "capture_snapshot",
]
