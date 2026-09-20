# -*- coding: utf-8 -*-
"""Deterministic canonical JSON hashing for sandbox logical state."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

_HASH_SCHEMA = "battle_sandbox_logical_state/1"
F01_STATE_BOUNDARY_SCHEMA = "f01_state_boundary/1"
_F01_HASH_SCHEMA = "battle_sandbox_f01_boundary_hash/1"


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


def _validate_f01_encoded_value(value: Any, where: str = "payload") -> None:
    """Reject ambiguity before the legacy JSON canonicalizer can coerce it."""
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{where} contains a non-finite float")
        return
    if isinstance(value, tuple):
        raise TypeError(
            f"{where} contains an untagged tuple; encode it through "
            "F01StateEnvelope before hashing"
        )
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_f01_encoded_value(item, f"{where}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"{where} mapping keys must be strings, got "
                    f"{type(key).__name__}"
                )
            _validate_f01_encoded_value(item, f"{where}.{key}")
        return
    raise TypeError(
        f"{where} contains unsupported {type(value).__name__}; expected an "
        "encoded F01 envelope"
    )


def stable_f01_envelope_hash(envelope: Mapping[str, Any]) -> str:
    """Hash only an explicit, already lossless F01 boundary envelope.

    Raw legacy state and arbitrary dictionaries are refused.  The separate hash
    domain prevents accidental equality with the legacy logical-state hash; it
    is a compatibility-seam hash, not the future Terra semantic hash.
    """
    if not isinstance(envelope, Mapping):
        raise TypeError("F01 hash input must be an envelope mapping")
    if set(envelope) != {"schema", "payload"}:
        raise ValueError(
            "F01 hash input must contain exactly 'schema' and 'payload'"
        )
    if envelope["schema"] != F01_STATE_BOUNDARY_SCHEMA:
        raise ValueError(
            f"F01 hash input must declare {F01_STATE_BOUNDARY_SCHEMA!r}"
        )
    _validate_f01_encoded_value(envelope["payload"])
    return stable_json_hash(
        {
            "schema": _F01_HASH_SCHEMA,
            "envelope": dict(envelope),
        }
    )


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
