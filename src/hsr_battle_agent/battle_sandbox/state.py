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
* BattleState v3 also carries ``component_lock_hp_records`` for the Handoff 12
  native component[+0x50] lock-HP list.  It is the smallest persistent
  representation required by TryGetLockHP and DirectDamageHP mode 0.
* BattleState v4 adds ``turn_timeline`` for Turn/AV Semantics 29. Remaining
  action delay stays in the existing PropertyEntry source of truth (property
  38); the timeline stores only ordered entity ids, current actor, elapsed
  delay, phase, and turn index.

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

from hsr_battle_agent.battle_ir.evidence import (
    ContractRef,
    EvidenceMode,
    ReadinessClass,
    UnknownHandle,
    VersionRelation,
    parse_evidence_mode,
    parse_readiness_class,
    parse_version_relation,
)
from hsr_battle_agent.battle_ir.lossless_value import LosslessNumber, PresenceValue
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_sandbox.errors import (
    StructuredRejection,
    UnsupportedStateVersionError,
)
from hsr_battle_agent.battle_sandbox.hash import (
    F01_STATE_BOUNDARY_SCHEMA,
    stable_f01_envelope_hash,
    stable_json_hash,
)

BATTLE_STATE_SCHEMA_VERSION = 4
_STATE_SCHEMA_KEY = "schema_version"
_EXTENSIONS_KEY = "extensions"
_MODIFIER_STATE_BY_ENTITY_KEY = "modifier_state_by_entity"
_ENTITY_PROPERTY_ENTRIES_KEY = "entity_property_entries"
_MODIFIER_PROPERTY_CONTRIBUTIONS_KEY = "modifier_property_contributions"
_COMPONENT_LOCK_HP_RECORDS_KEY = "component_lock_hp_records"
_TURN_TIMELINE_KEY = "turn_timeline"
_LEGACY_V1_SCHEMA_VERSION = 1
_LEGACY_V2_SCHEMA_VERSION = 2
_LEGACY_V3_SCHEMA_VERSION = 3


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
    component_lock_hp_records: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )
    turn_timeline: dict[str, Any] = field(default_factory=dict)

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
        if not isinstance(self.component_lock_hp_records, dict):
            raise TypeError(
                "BattleState component_lock_hp_records must be a dict"
            )
        if not isinstance(self.turn_timeline, dict):
            raise TypeError("BattleState turn_timeline must be a dict")
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
        self.component_lock_hp_records = deep_copy_json_value(
            self.component_lock_hp_records
        )
        self.turn_timeline = deep_copy_json_value(self.turn_timeline)

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
            component_lock_hp_records=deep_copy_json_value(
                self.component_lock_hp_records
            ),
            turn_timeline=deep_copy_json_value(self.turn_timeline),
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
            _COMPONENT_LOCK_HP_RECORDS_KEY: deep_copy_json_value(
                self.component_lock_hp_records
            ),
            _TURN_TIMELINE_KEY: deep_copy_json_value(self.turn_timeline),
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
            _LEGACY_V3_SCHEMA_VERSION,
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

        allowed = {
            _STATE_SCHEMA_KEY,
            _EXTENSIONS_KEY,
            _MODIFIER_STATE_BY_ENTITY_KEY,
            _ENTITY_PROPERTY_ENTRIES_KEY,
            _MODIFIER_PROPERTY_CONTRIBUTIONS_KEY,
            _COMPONENT_LOCK_HP_RECORDS_KEY,
        }
        if schema_version == BATTLE_STATE_SCHEMA_VERSION:
            allowed.add(_TURN_TIMELINE_KEY)
        unknown = set(data) - allowed
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
        lock_records = data.get(_COMPONENT_LOCK_HP_RECORDS_KEY, {})
        if not isinstance(lock_records, dict):
            raise TypeError(
                "BattleState component_lock_hp_records must be a dict"
            )
        turn_timeline = data.get(_TURN_TIMELINE_KEY, {})
        if not isinstance(turn_timeline, dict):
            raise TypeError("BattleState turn_timeline must be a dict")
        return cls(
            schema_version=BATTLE_STATE_SCHEMA_VERSION,
            extensions=deep_copy_json_value(extensions),
            modifier_state_by_entity=deep_copy_json_value(modifiers),
            entity_property_entries=deep_copy_json_value(properties),
            modifier_property_contributions=deep_copy_json_value(contributions),
            component_lock_hp_records=deep_copy_json_value(lock_records),
            turn_timeline=deep_copy_json_value(turn_timeline),
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


# ---------------------------------------------------------------------------
# F01 lossless compatibility seam
# ---------------------------------------------------------------------------


class F01StateBoundaryError(ValueError):
    """Raised when data cannot cross the explicit F01 state boundary losslessly."""


_F01_OBJECT_TYPES = {
    "ContractRef": ContractRef,
    "UnknownHandle": UnknownHandle,
    "PresenceValue": PresenceValue,
    "LosslessNumber": LosslessNumber,
    "SourceProvenance": SourceProvenance,
    "StructuredRejection": StructuredRejection,
}


def _encode_f01_value(value: Any, where: str = "value") -> dict[str, Any]:
    """Encode a value into an explicit type-tagged, JSON-safe F01 node."""
    if isinstance(value, BattleState):
        raise F01StateBoundaryError(
            "legacy BattleState material cannot be converted implicitly into "
            "the F01 lossless path"
        )
    for enum_type, type_name in (
        (EvidenceMode, "EvidenceMode"),
        (VersionRelation, "VersionRelation"),
        (ReadinessClass, "ReadinessClass"),
    ):
        if isinstance(value, enum_type):
            return {
                "kind": "f01_enum",
                "type": type_name,
                "value": value.serialize(),
            }
    for type_name, object_type in _F01_OBJECT_TYPES.items():
        if isinstance(value, object_type):
            return {
                "kind": "f01_object",
                "type": type_name,
                "document": _encode_f01_value(
                    value.to_dict(), f"{where}.{type_name}"
                ),
            }
    if value is None:
        return {"kind": "null"}
    if isinstance(value, bool):
        return {"kind": "bool", "value": value}
    if isinstance(value, int):
        return {"kind": "int", "lexeme": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise F01StateBoundaryError(f"{where} contains a non-finite float")
        return {"kind": "float", "hex": value.hex()}
    if isinstance(value, str):
        return {"kind": "str", "value": value}
    if isinstance(value, list):
        return {
            "kind": "list",
            "items": [
                _encode_f01_value(item, f"{where}[{index}]")
                for index, item in enumerate(value)
            ],
        }
    if isinstance(value, tuple):
        return {
            "kind": "tuple",
            "items": [
                _encode_f01_value(item, f"{where}[{index}]")
                for index, item in enumerate(value)
            ],
        }
    if isinstance(value, Mapping):
        items: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise F01StateBoundaryError(
                    f"{where} mapping keys must be strings, got "
                    f"{type(key).__name__}"
                )
            items[key] = _encode_f01_value(item, f"{where}.{key}")
        return {"kind": "mapping", "items": items}
    raise F01StateBoundaryError(
        f"{where} contains unsupported {type(value).__name__}; no lossy "
        "conversion is available"
    )


def _require_node_keys(
    node: Mapping[str, Any], expected: set[str], where: str
) -> None:
    if set(node) != expected:
        raise F01StateBoundaryError(
            f"{where} must contain exactly {sorted(expected)}, got "
            f"{sorted(str(key) for key in node)}"
        )


def _decode_f01_value(node: Any, where: str = "payload") -> Any:
    """Decode one F01 node; every shape is exact and ambiguity fails closed."""
    if not isinstance(node, Mapping):
        raise F01StateBoundaryError(f"{where} must be a tagged mapping")
    if "kind" not in node:
        raise F01StateBoundaryError(f"{where} is missing its kind tag")
    kind = node["kind"]
    if kind == "null":
        _require_node_keys(node, {"kind"}, where)
        return None
    if kind == "bool":
        _require_node_keys(node, {"kind", "value"}, where)
        if not isinstance(node["value"], bool):
            raise F01StateBoundaryError(f"{where}.value must be bool")
        return node["value"]
    if kind == "int":
        _require_node_keys(node, {"kind", "lexeme"}, where)
        lexeme = node["lexeme"]
        if not isinstance(lexeme, str):
            raise F01StateBoundaryError(f"{where}.lexeme must be a string")
        try:
            value = int(lexeme)
        except ValueError as exc:
            raise F01StateBoundaryError(
                f"{where}.lexeme is not an integer"
            ) from exc
        if str(value) != lexeme:
            raise F01StateBoundaryError(
                f"{where}.lexeme is not the canonical integer spelling"
            )
        return value
    if kind == "float":
        _require_node_keys(node, {"kind", "hex"}, where)
        if not isinstance(node["hex"], str):
            raise F01StateBoundaryError(f"{where}.hex must be a string")
        try:
            value = float.fromhex(node["hex"])
        except ValueError as exc:
            raise F01StateBoundaryError(f"{where}.hex is invalid") from exc
        if not math.isfinite(value) or value.hex() != node["hex"]:
            raise F01StateBoundaryError(
                f"{where}.hex must be a canonical finite float spelling"
            )
        return value
    if kind == "str":
        _require_node_keys(node, {"kind", "value"}, where)
        if not isinstance(node["value"], str):
            raise F01StateBoundaryError(f"{where}.value must be a string")
        return node["value"]
    if kind in ("list", "tuple"):
        _require_node_keys(node, {"kind", "items"}, where)
        items = node["items"]
        if not isinstance(items, list):
            raise F01StateBoundaryError(f"{where}.items must be a list")
        decoded = [
            _decode_f01_value(item, f"{where}.items[{index}]")
            for index, item in enumerate(items)
        ]
        return tuple(decoded) if kind == "tuple" else decoded
    if kind == "mapping":
        _require_node_keys(node, {"kind", "items"}, where)
        items = node["items"]
        if not isinstance(items, Mapping):
            raise F01StateBoundaryError(f"{where}.items must be a mapping")
        decoded_mapping: dict[str, Any] = {}
        for key, item in items.items():
            if not isinstance(key, str):
                raise F01StateBoundaryError(
                    f"{where}.items keys must be strings"
                )
            decoded_mapping[key] = _decode_f01_value(item, f"{where}.items.{key}")
        return decoded_mapping
    if kind == "f01_enum":
        _require_node_keys(node, {"kind", "type", "value"}, where)
        parsers = {
            "EvidenceMode": parse_evidence_mode,
            "VersionRelation": parse_version_relation,
            "ReadinessClass": parse_readiness_class,
        }
        enum_type = node["type"]
        if enum_type not in parsers:
            raise F01StateBoundaryError(f"{where} has unknown F01 enum type")
        try:
            return parsers[enum_type](node["value"])
        except ValueError as exc:
            raise F01StateBoundaryError(f"{where} has invalid enum data") from exc
    if kind == "f01_object":
        _require_node_keys(node, {"kind", "type", "document"}, where)
        object_type = node["type"]
        if object_type not in _F01_OBJECT_TYPES:
            raise F01StateBoundaryError(f"{where} has unknown F01 object type")
        document = _decode_f01_value(node["document"], f"{where}.document")
        if not isinstance(document, Mapping):
            raise F01StateBoundaryError(
                f"{where}.document must decode to a mapping"
            )
        try:
            return _F01_OBJECT_TYPES[object_type].from_dict(document)
        except (TypeError, ValueError) as exc:
            raise F01StateBoundaryError(
                f"{where} contains invalid {object_type} data"
            ) from exc
    raise F01StateBoundaryError(f"{where} has unknown kind {kind!r}")


class F01StateEnvelope:
    """Explicit compatibility carrier for F01 data, separate from BattleState.

    This is not BattleState v2 and performs no legacy conversion.  Construction
    is the explicit crossing point; every value is type-tagged so absence/null,
    tuple/list, numeric and evidence identity survive serialization and hashing.
    """

    __slots__ = ("_payload",)

    def __init__(self, value: Any) -> None:
        self._payload = _encode_f01_value(value)

    @property
    def boundary_kind(self) -> str:
        return "F01_LOSSLESS"

    @property
    def value(self) -> Any:
        """Return an independent decoded value."""
        return _decode_f01_value(deep_copy_json_value(self._payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": F01_STATE_BOUNDARY_SCHEMA,
            "payload": deep_copy_json_value(self._payload),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "F01StateEnvelope":
        if not isinstance(data, Mapping):
            raise F01StateBoundaryError("F01 envelope document must be a mapping")
        if set(data) != {"schema", "payload"}:
            raise F01StateBoundaryError(
                "F01 envelope must contain exactly 'schema' and 'payload'; "
                "missing data is never defaulted"
            )
        if data["schema"] != F01_STATE_BOUNDARY_SCHEMA:
            raise F01StateBoundaryError(
                f"unknown F01 envelope schema {data['schema']!r}"
            )
        value = _decode_f01_value(data["payload"])
        return cls(value)

    def clone(self) -> "F01StateEnvelope":
        return type(self).from_dict(self.to_dict())

    def state_hash(self) -> str:
        return stable_f01_envelope_hash(self.to_dict())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, F01StateEnvelope):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"F01StateEnvelope(kind={self.boundary_kind!r})"
