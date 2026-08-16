# -*- coding: utf-8 -*-
"""BattleState v0.

State schema grows only when a recovered semantic slice proves a new
read/write requirement.  BattleState v0 therefore has **no** client battle
fields (no hp / atk / def / spd / energy / toughness / buffs / ...).

It contains only kernel infrastructure:

* ``schema_version`` -- versioned snapshot evolution
* ``extensions``      -- infrastructure-only key/value bag used to prove clone
  isolation and future migration mechanics; game-semantic fields must become
  real dataclass fields in a later schema version, never hide in extensions

JSON contract (strict):

* allowed values: ``None``, ``bool``, ``int``, finite ``float``, ``str``,
  ``list``, ``dict`` with ``str`` keys;
* tuples are **forbidden** even though Python can serialize them: the kernel
  only accepts the JSON model and every boundary deep-copies nested
  lists/dicts, so clone/snapshot can never alias a caller-owned container.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.errors import UnsupportedStateVersionError
from hsr_battle_agent.battle_sandbox.hash import stable_json_hash

BATTLE_STATE_SCHEMA_VERSION = 1
_STATE_SCHEMA_KEY = "schema_version"
_EXTENSIONS_KEY = "extensions"


@dataclass
class BattleState:
    schema_version: int = BATTLE_STATE_SCHEMA_VERSION
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != BATTLE_STATE_SCHEMA_VERSION:
            raise UnsupportedStateVersionError(self.schema_version)
        if not isinstance(self.extensions, dict):
            raise TypeError("BattleState extensions must be a dict")
        # Normalize to a private deep copy: caller-owned nested containers can
        # never alias BattleState internals, even on direct construction.
        self.extensions = deep_copy_json_value(self.extensions)

    def clone(self) -> "BattleState":
        return BattleState(
            schema_version=self.schema_version,
            extensions=deep_copy_json_value(self.extensions),
        )

    def set_extension(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("extension key must be a non-empty string")
        self.extensions[key] = deep_copy_json_value(value)

    def remove_extension(self, key: str) -> None:
        self.extensions.pop(key, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            _STATE_SCHEMA_KEY: self.schema_version,
            _EXTENSIONS_KEY: deep_copy_json_value(self.extensions),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BattleState":
        if not isinstance(data, Mapping):
            raise TypeError("BattleState dict must be a mapping")
        schema_version = data.get(_STATE_SCHEMA_KEY)
        if schema_version != BATTLE_STATE_SCHEMA_VERSION:
            raise UnsupportedStateVersionError(schema_version)
        unknown = set(data) - {_STATE_SCHEMA_KEY, _EXTENSIONS_KEY}
        if unknown:
            raise ValueError(
                f"unknown BattleState v1 keys: {', '.join(sorted(unknown))}"
            )
        extensions = data.get(_EXTENSIONS_KEY, {})
        if not isinstance(extensions, dict):
            raise TypeError("BattleState extensions must be a dict")
        return cls(
            schema_version=BATTLE_STATE_SCHEMA_VERSION,
            extensions=deep_copy_json_value(extensions),
        )

    def state_hash(self) -> str:
        return stable_json_hash(self.to_dict())


def validate_json_value(value: Any, where: str = "value") -> None:
    """Validate the strict BattleState JSON value model."""
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{where} float values must be finite")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"{where} mapping keys must be strings, got {type(key).__name__}"
                )
            validate_json_value(item, f"{where}.{key}")
        return
    if isinstance(value, tuple):
        raise TypeError(
            f"{where} tuples are forbidden by the strict JSON model; "
            "use a list instead"
        )
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_json_value(item, f"{where}[{index}]")
        return
    raise TypeError(
        f"{where} must be JSON-safe "
        "(None/bool/int/finite float/str/list/dict with str keys), "
        f"got {type(value).__name__}"
    )


def deep_copy_json_value(value: Any) -> Any:
    """Validate and recursively copy a strict JSON value.

    Returns a fully independent copy for every nested ``list`` / ``dict``;
    tuples are rejected by the validator and therefore never pass through.
    """
    validate_json_value(value)
    if isinstance(value, dict):
        return {key: deep_copy_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [deep_copy_json_value(item) for item in value]
    return value
