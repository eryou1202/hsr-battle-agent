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
        _validate_jsonable(self.extensions, "extensions")

    def clone(self) -> "BattleState":
        return BattleState(
            schema_version=self.schema_version,
            extensions={key: _deep_copy_jsonable(value) for key, value in self.extensions.items()},
        )

    def set_extension(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("extension key must be a non-empty string")
        _validate_jsonable(value, f"extensions.{key}")
        self.extensions[key] = value

    def remove_extension(self, key: str) -> None:
        self.extensions.pop(key, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            _STATE_SCHEMA_KEY: self.schema_version,
            _EXTENSIONS_KEY: _deep_copy_jsonable(self.extensions),
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
        if not isinstance(extensions, Mapping):
            raise TypeError("BattleState extensions must be a mapping")
        return cls(
            schema_version=BATTLE_STATE_SCHEMA_VERSION,
            extensions={str(key): _deep_copy_jsonable(value) for key, value in extensions.items()},
        )

    def state_hash(self) -> str:
        return stable_json_hash(self.to_dict())


def _deep_copy_jsonable(value: Any) -> Any:
    _validate_jsonable(value, "value")
    if isinstance(value, Mapping):
        return {str(key): _deep_copy_jsonable(value[key]) for key in value}
    if isinstance(value, list):
        return [_deep_copy_jsonable(item) for item in value]
    return value


def _validate_jsonable(value: Any, where: str) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{where} float values must be finite")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{where} mapping keys must be strings, got {type(key).__name__}")
            _validate_jsonable(item, f"{where}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_jsonable(item, where)
        return
    raise TypeError(
        f"{where} must be JSON-safe (None/bool/int/float/str/list/dict), "
        f"got {type(value).__name__}"
    )
