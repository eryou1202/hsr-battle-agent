# -*- coding: utf-8 -*-
"""Versioned BattleState.

State schema grows only when a recovered semantic slice proves a new
read/write requirement.

* BattleState v1: kernel infrastructure only (``extensions``).
* BattleState v2: adds ``modifier_state_by_entity``, recovered by Modifier
  Application Bridge 07 (E4): the ordered persistent modifier list owned by
  an entity component.
* BattleState v3: adds the Generic Property Runtime (Handoffs 09/10/11):
  ``entity_property_entries`` keyed by ``(entity_runtime_id, property_id)``
  and ``modifier_property_contributions`` keyed by logical ``ModifierRef``.
  Property state is the source of truth; there are still no standalone
  hp/atk/def/spd/energy/toughness fields.

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

BATTLE_STATE_SCHEMA_VERSION = 3
_STATE_SCHEMA_KEY = "schema_version"
_EXTENSIONS_KEY = "extensions"
_MODIFIER_STATE_BY_ENTITY_KEY = "modifier_state_by_entity"
_ENTITY_PROPERTY_ENTRIES_KEY = "entity_property_entries"
_MODIFIER_PROPERTY_CONTRIBUTIONS_KEY = "modifier_property_contributions"
_LEGACY_V1_SCHEMA_VERSION = 1
_LEGACY_V2_SCHEMA_VERSION = 2


@dataclass
class BattleState:
    schema_version: int = BATTLE_STATE_SCHEMA_VERSION
    extensions: dict[str, Any] = field(default_factory=dict)
    modifier_state_by_entity: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )
    entity_property_entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    modifier_property_contributions: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if self.schema_version != BATTLE_STATE_SCHEMA_VERSION:
            raise UnsupportedStateVersionError(self.schema_version)
        if not isinstance(self.extensions, dict):
            raise TypeError("BattleState extensions must be a dict")
        if not isinstance(self.modifier_state_by_entity, dict):
            raise TypeError("BattleState modifier_state_by_entity must be a dict")
        if not isinstance(self.entity_property_entries, dict):
            raise TypeError("BattleState entity_property_entries must be a dict")
        if not isinstance(self.modifier_property_contributions, dict):
            raise TypeError(
                "BattleState modifier_property_contributions must be a dict"
            )
        # Normalize to private deep copies: caller-owned nested containers can
        # never alias BattleState internals, even on direct construction.
        self.extensions = deep_copy_json_value(self.extensions)
        self.modifier_state_by_entity = deep_copy_json_value(
            self.modifier_state_by_entity
        )
        self.entity_property_entries = deep_copy_json_value(
            self.entity_property_entries
        )
        self.modifier_property_contributions = deep_copy_json_value(
            self.modifier_property_contributions
        )

    def clone(self) -> "BattleState":
        return BattleState(
            schema_version=self.schema_version,
            extensions=deep_copy_json_value(self.extensions),
            modifier_state_by_entity=deep_copy_json_value(
                self.modifier_state_by_entity
            ),
            entity_property_entries=deep_copy_json_value(
                self.entity_property_entries
            ),
            modifier_property_contributions=deep_copy_json_value(
                self.modifier_property_contributions
            ),
        )

    def set_extension(self, key: str, value: Any) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("extension key must be a non-empty string")
        self.extensions[key] = deep_copy_json_value(value)

    def remove_extension(self, key: str) -> None:
        self.extensions.pop(key, None)

    def set_modifier_collection(self, entity_runtime_id: int, items: list[dict[str, Any]]) -> None:
        """Replace one entity modifier collection with a validated deep copy."""
        if isinstance(entity_runtime_id, bool) or not isinstance(entity_runtime_id, int):
            raise TypeError("entity_runtime_id must be an int")
        if not isinstance(items, list):
            raise TypeError("modifier collection items must be a list in JSON form")
        self.modifier_state_by_entity[str(entity_runtime_id)] = deep_copy_json_value(
            items
        )

    def clear_modifier_collection(self, entity_runtime_id: int) -> None:
        if isinstance(entity_runtime_id, bool) or not isinstance(entity_runtime_id, int):
            raise TypeError("entity_runtime_id must be an int")
        self.modifier_state_by_entity.pop(str(entity_runtime_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            _STATE_SCHEMA_KEY: self.schema_version,
            _EXTENSIONS_KEY: deep_copy_json_value(self.extensions),
            _MODIFIER_STATE_BY_ENTITY_KEY: deep_copy_json_value(
                self.modifier_state_by_entity
            ),
            _ENTITY_PROPERTY_ENTRIES_KEY: deep_copy_json_value(
                self.entity_property_entries
            ),
            _MODIFIER_PROPERTY_CONTRIBUTIONS_KEY: deep_copy_json_value(
                self.modifier_property_contributions
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BattleState":
        if not isinstance(data, Mapping):
            raise TypeError("BattleState dict must be a mapping")
        schema_version = data.get(_STATE_SCHEMA_KEY)
        if schema_version not in (
            BATTLE_STATE_SCHEMA_VERSION,
            _LEGACY_V1_SCHEMA_VERSION,
            _LEGACY_V2_SCHEMA_VERSION,
        ):
            raise UnsupportedStateVersionError(schema_version)

        if schema_version == _LEGACY_V1_SCHEMA_VERSION:
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

        if schema_version == _LEGACY_V2_SCHEMA_VERSION:
            unknown = set(data) - {
                _STATE_SCHEMA_KEY,
                _EXTENSIONS_KEY,
                _MODIFIER_STATE_BY_ENTITY_KEY,
            }
            if unknown:
                raise ValueError(
                    f"unknown BattleState v2 keys: {', '.join(sorted(unknown))}"
                )
            extensions = data.get(_EXTENSIONS_KEY, {})
            if not isinstance(extensions, dict):
                raise TypeError("BattleState extensions must be a dict")
            modifiers = data.get(_MODIFIER_STATE_BY_ENTITY_KEY, {})
            if not isinstance(modifiers, dict):
                raise TypeError(
                    "BattleState modifier_state_by_entity must be a dict"
                )
            return cls(
                schema_version=BATTLE_STATE_SCHEMA_VERSION,
                extensions=deep_copy_json_value(extensions),
                modifier_state_by_entity=deep_copy_json_value(modifiers),
            )

        unknown = set(data) - {
            _STATE_SCHEMA_KEY,
            _EXTENSIONS_KEY,
            _MODIFIER_STATE_BY_ENTITY_KEY,
            _ENTITY_PROPERTY_ENTRIES_KEY,
            _MODIFIER_PROPERTY_CONTRIBUTIONS_KEY,
        }
        if unknown:
            raise ValueError(
                f"unknown BattleState v{BATTLE_STATE_SCHEMA_VERSION} keys: "
                f"{', '.join(sorted(unknown))}"
            )
        extensions = data.get(_EXTENSIONS_KEY, {})
        if not isinstance(extensions, dict):
            raise TypeError("BattleState extensions must be a dict")
        modifiers = data.get(_MODIFIER_STATE_BY_ENTITY_KEY, {})
        if not isinstance(modifiers, dict):
            raise TypeError(
                "BattleState modifier_state_by_entity must be a dict"
            )
        properties = data.get(_ENTITY_PROPERTY_ENTRIES_KEY, {})
        if not isinstance(properties, dict):
            raise TypeError(
                "BattleState entity_property_entries must be a dict"
            )
        contributions = data.get(_MODIFIER_PROPERTY_CONTRIBUTIONS_KEY, {})
        if not isinstance(contributions, dict):
            raise TypeError(
                "BattleState modifier_property_contributions must be a dict"
            )
        return cls(
            schema_version=BATTLE_STATE_SCHEMA_VERSION,
            extensions=deep_copy_json_value(extensions),
            modifier_state_by_entity=deep_copy_json_value(modifiers),
            entity_property_entries=deep_copy_json_value(properties),
            modifier_property_contributions=deep_copy_json_value(contributions),
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
