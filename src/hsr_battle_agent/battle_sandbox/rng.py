# -*- coding: utf-8 -*-
"""Deterministic RNG abstraction for the sandbox.

Important labels (also recorded in docs/battle_sandbox/kernel_01.md):

* ``CLIENT_RNG_ALGORITHM = UNKNOWN`` -- we do **not** claim to reproduce the
  client PRNG.
* ``SANDBOX_RNG = DETERMINISTIC_ABSTRACTION`` -- this is the sandbox's own
  deterministic abstraction.  Same seed + same operation sequence produces
  the same sequence under the same Python runtime.

All future game randomness must enter through ``ExecutionContext.rng``.
Direct ``random.random()`` calls are forbidden in sandbox runtime code.
"""
from __future__ import annotations

import random
from typing import Any, Mapping

CLIENT_RNG_ALGORITHM = "UNKNOWN"
SANDBOX_RNG = "DETERMINISTIC_ABSTRACTION"
SANDBOX_RNG_ALGORITHM = "PYTHON_RANDOM_MT19937"
_RNG_STATE_SCHEMA = 1
_RNG_STATE_LENGTH = 625
_JSON_SAFE_RESULT = (bool, int, float, str, type(None))


def _validate_rng_state(state: tuple[Any, ...]) -> None:
    if not isinstance(state, tuple) or len(state) != 3:
        raise ValueError("random.Random state must be a 3-tuple")
    version, internal, gauss_next = state
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("random.Random state version must be an int")
    if not isinstance(internal, tuple) or len(internal) != _RNG_STATE_LENGTH:
        raise ValueError(f"random.Random internal state must have {_RNG_STATE_LENGTH} entries")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in internal):
        raise TypeError("random.Random internal state entries must be ints")
    if gauss_next is not None and not isinstance(gauss_next, float):
        raise TypeError("random.Random gauss_next must be float or None")


class SandboxRng:
    """Small deterministic wrapper around stdlib ``random.Random``."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def seed(self, seed: int | None = None) -> None:
        self._rng.seed(seed)

    def next_u64(self) -> int:
        return self._rng.getrandbits(64)

    def randint(self, low: int, high: int) -> int:
        return self._rng.randint(low, high)

    def uniform(self, low: float, high: float) -> float:
        return self._rng.uniform(low, high)

    def getstate(self) -> tuple[Any, ...]:
        return self._rng.getstate()

    def setstate(self, state: tuple[Any, ...]) -> None:
        _validate_rng_state(state)
        self._rng.setstate(state)

    def clone(self) -> "SandboxRng":
        return SandboxRng.from_state(self.getstate())

    def to_dict(self) -> dict[str, Any]:
        version, internal, gauss_next = self.getstate()
        return {
            "schema_version": _RNG_STATE_SCHEMA,
            "algorithm": SANDBOX_RNG_ALGORITHM,
            "state": {
                "version": version,
                "internal_state": list(internal),
                "gauss_next": gauss_next,
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SandboxRng":
        if not isinstance(data, Mapping):
            raise TypeError("RNG state dict must be a mapping")
        if data.get("schema_version") != _RNG_STATE_SCHEMA:
            raise ValueError(f"unsupported RNG state schema_version: {data.get('schema_version')!r}")
        if data.get("algorithm") != SANDBOX_RNG_ALGORITHM:
            raise ValueError(
                f"unsupported RNG algorithm {data.get('algorithm')!r}; "
                f"expected {SANDBOX_RNG_ALGORITHM!r}"
            )
        state_block = data.get("state")
        if not isinstance(state_block, Mapping):
            raise TypeError("RNG state block must be a mapping")
        internal = state_block.get("internal_state")
        if not isinstance(internal, list):
            raise TypeError("RNG internal_state must be a list")
        state = (state_block.get("version"), tuple(internal), state_block.get("gauss_next"))
        _validate_rng_state(state)
        rng = cls.__new__(cls)
        rng._rng = random.Random()
        rng._rng.setstate(state)
        return rng

    @classmethod
    def from_state(cls, state: tuple[Any, ...]) -> "SandboxRng":
        _validate_rng_state(state)
        rng = cls.__new__(cls)
        rng._rng = random.Random()
        rng._rng.setstate(state)
        return rng

    def __repr__(self) -> str:
        return (
            f"SandboxRng(algorithm={SANDBOX_RNG_ALGORITHM!r}, "
            f"client_algorithm={CLIENT_RNG_ALGORITHM!r})"
        )
