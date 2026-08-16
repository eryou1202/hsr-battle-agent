# -*- coding: utf-8 -*-
"""Deterministic canonical JSON hashing for sandbox logical state."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

_HASH_SCHEMA = "battle_sandbox_logical_state/1"


def _canonical_jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical_jsonable(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_canonical_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_canonical_jsonable(item) for item in value]
    return value


def stable_json_hash(value: Any) -> str:
    """SHA-256 over deterministic, sorted-key, compact JSON."""
    canonical = _canonical_jsonable(value)
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def logical_battle_hash(state: Mapping[str, Any], rng_state: Mapping[str, Any]) -> str:
    """Hash of the logical battle state (BattleState + RNG state).

    Trace contents are explicitly excluded: traces are observational output,
    not logical state.  Python object ids never enter this hash.
    """
    return stable_json_hash(
        {
            "schema": _HASH_SCHEMA,
            "battle_state": state,
            "rng_state": rng_state,
        }
    )
