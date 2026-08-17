# -*- coding: utf-8 -*-
"""Loaders/validators for Handoff 09/10/11 semantic artifacts.

Handoff 09 uses ``battle_semantic_capability/1``; Handoffs 10 and 11 use
``battle_semantic_bridge/1``.  Both loaders are intentionally narrow:

* They validate the E4 fields the catalog/registry needs.
* They produce the same ``RecoveredPrimitive(spec, provenance)`` pair as the
  vertical-slice and batch loaders.
* They never derive runtime semantics from gameplay names.
* Unregistered native helpers (Handoffs 10/11) keep ``method_index=None`` in
  provenance; runtime dispatch never depends on that value.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.model import (
    DIRECT_DAMAGE_HP_TRANSITION_PRIMITIVE_ID,
    TRY_GET_LOCK_HP_PRIMITIVE_ID,
    PrimitiveInputSpec,
    PrimitiveSpec,
)
from hsr_battle_agent.battle_ir.provenance import (
    PROVENANCE_NOTE_DEFAULT,
    SourceProvenance,
)
from hsr_battle_agent.battle_ir.semantic_artifact import (
    RecoveredPrimitive,
    SemanticArtifactError,
)

PROPERTY_CAPABILITY_SCHEMA = "battle_semantic_capability/1"
PROPERTY_BRIDGE_SCHEMA = "battle_semantic_bridge/1"
EVIDENCE_E4 = "E4_STATIC_MACHINE_CODE"

_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEX_RVA = re.compile(r"^0x[0-9A-Fa-f]+$")

_BRIDGE_INPUT_TYPES = {
    "component": "ability_component_ref",
    "property_entry": "property_entry_ref",
    "property_id": "opaque_property_id",
    "source_index": "source_index",
    "source_value": "runtime_numeric_value",
    "new_source_value": "runtime_numeric_value",
    "runtime_value": "runtime_numeric_value",
    "operand": "runtime_numeric_value",
    "old_materialized_value": "runtime_numeric_value",
    "function_id": "property_modify_function_id",
    "context_token": "opaque_context_token",
    "left": "runtime_numeric_value",
    "right": "runtime_numeric_value",
}


def load_property_capability(
    path: str | Path,
) -> list[RecoveredPrimitive]:
    """Load a Handoff 09 ``battle_semantic_capability/1`` artifact."""
    return _load_property_artifact(
        Path(path),
        expected_schema=PROPERTY_CAPABILITY_SCHEMA,
        validator=_validate_capability_artifact,
    )


HP_TRANSITION_BRIDGE_CAPABILITY_ID = "DIRECT_DAMAGE_HP_TRANSITION_12_PROOF"


def load_property_bridge(
    path: str | Path,
) -> list[RecoveredPrimitive]:
    """Load a Handoff 10/11/12 ``battle_semantic_bridge/1`` artifact.

    Handoff 12 uses the same top-level bridge schema but a different primitive
    projection.  It is detected by capability id and routed to the narrow HP
    loader so the catalog can bind the new HP primitives without duplicating
    the already-registered property/fixed-point helpers.
    """
    artifact_path = Path(path)
    try:
        raw = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SemanticArtifactError(
            f"cannot read semantic property artifact {artifact_path}: {exc}"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SemanticArtifactError(
            f"semantic property artifact is not valid JSON: {exc}"
        ) from exc
    if data.get("capability_id") == HP_TRANSITION_BRIDGE_CAPABILITY_ID:
        return _validate_hp_transition_artifact(data, artifact_path=str(artifact_path))
    return _load_property_artifact(
        artifact_path,
        expected_schema=PROPERTY_BRIDGE_SCHEMA,
        validator=_validate_bridge_artifact,
    )


def validate_hp_transition_bridge(
    data: Mapping[str, Any],
    artifact_path: str = "<memory>",
) -> list[RecoveredPrimitive]:
    """Public validator for the Handoff 12 HP-transition bridge artifact."""
    return _validate_hp_transition_artifact(data, artifact_path)


def _validate_hp_transition_artifact(
    data: Mapping[str, Any],
    artifact_path: str,
) -> list[RecoveredPrimitive]:
    _require_root_common(data, artifact_path, PROPERTY_BRIDGE_SCHEMA)
    game_version = str(data["game_version"])
    primitives = data.get("primitives")
    if not isinstance(primitives, list) or not primitives:
        raise SemanticArtifactError(
            f"{artifact_path}: primitives must be a non-empty list"
        )

    recovered: list[RecoveredPrimitive] = []
    seen_ids: set[str] = set()
    for index, raw_primitive in enumerate(primitives):
        if not isinstance(raw_primitive, Mapping):
            raise SemanticArtifactError(
                f"{artifact_path}: primitives[{index}] must be an object"
            )
        p = raw_primitive
        label = f"{artifact_path}: primitives[{index}]"
        primitive_id = p.get("primitive_id")
        if primitive_id not in {
            DIRECT_DAMAGE_HP_TRANSITION_PRIMITIVE_ID,
            TRY_GET_LOCK_HP_PRIMITIVE_ID,
        }:
            # Existing property/fixed-point primitives are already registered
            # by earlier artifacts; the HP artifact lists them only as
            # dependencies and must not duplicate them in the catalog.
            continue
        if primitive_id in seen_ids:
            raise SemanticArtifactError(
                f"{artifact_path}: duplicate primitive_id {primitive_id!r}"
            )
        seen_ids.add(primitive_id)

        semantic_name = _require_string(p, "semantic_name", label)
        if p.get("evidence_level") not in (EVIDENCE_E4, "CONFIRMED"):
            raise SemanticArtifactError(
                f"{label}: evidence_level {p.get('evidence_level')!r}; "
                f"expected {EVIDENCE_E4!r} or CONFIRMED"
            )
        native_rva = _require_rva(p, "native_rva", label)

        runtime_type = p.get("runtime_type")
        if not isinstance(runtime_type, str) or not runtime_type:
            raise SemanticArtifactError(
                f"{label}: runtime_type must be a non-empty string"
            )
        method_index = p.get("method_index")
        if method_index is not None:
            if isinstance(method_index, bool) or not isinstance(method_index, int):
                raise SemanticArtifactError(
                    f"{label}: method_index must be an int or null"
                )
            if method_index < 0:
                raise SemanticArtifactError(
                    f"{label}: method_index must be >= 0"
                )
        method_name = p.get("method_name")
        method = (
            method_name
            if isinstance(method_name, str) and method_name
            else semantic_name
        )

        if primitive_id == TRY_GET_LOCK_HP_PRIMITIVE_ID:
            inputs = (
                PrimitiveInputSpec(name="component", type="ability_component_ref"),
                PrimitiveInputSpec(name="damage_kind", type="int32"),
            )
            result = "lock_hp_result"
        else:
            inputs = (
                PrimitiveInputSpec(name="component", type="ability_component_ref"),
                PrimitiveInputSpec(name="delta", type="runtime_numeric_value"),
                PrimitiveInputSpec(name="damage_kind", type="int32"),
                PrimitiveInputSpec(name="context_token", type="opaque_context_token"),
                PrimitiveInputSpec(name="input_record", type="opaque_input_record"),
                PrimitiveInputSpec(name="mode", type="int32"),
                PrimitiveInputSpec(
                    name="negative_hp_gate", type="boolean"
                ),
            )
            result = "hp_transition_result"

        spec = PrimitiveSpec(
            primitive_id=primitive_id,
            semantic_name=semantic_name,
            description=semantic_name,
            inputs=inputs,
            context_reads=(),
            context_writes=(),
            result=result,
            determinism="DETERMINISTIC",
        )
        provenance = SourceProvenance(
            game_version=game_version,
            runtime_type=runtime_type,
            method=method,
            method_index=method_index,
            native_rva=native_rva,
            evidence_level=EVIDENCE_E4,
            note=PROVENANCE_NOTE_DEFAULT,
        )
        recovered.append(RecoveredPrimitive(spec=spec, provenance=provenance))

    if not recovered:
        raise SemanticArtifactError(
            f"{artifact_path}: no Handoff 12 HP primitives found in artifact"
        )
    return recovered


def _load_property_artifact(
    artifact_path: Path,
    *,
    expected_schema: str,
    validator: Any,
) -> list[RecoveredPrimitive]:
    try:
        raw = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SemanticArtifactError(
            f"cannot read semantic property artifact {artifact_path}: {exc}"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SemanticArtifactError(
            f"semantic property artifact is not valid JSON: {exc}"
        ) from exc
    return validator(data, artifact_path=str(artifact_path))


def validate_property_capability(
    data: Mapping[str, Any],
    artifact_path: str = "<memory>",
) -> list[RecoveredPrimitive]:
    return _validate_capability_artifact(data, artifact_path)


def validate_property_bridge(
    data: Mapping[str, Any],
    artifact_path: str = "<memory>",
) -> list[RecoveredPrimitive]:
    return _validate_bridge_artifact(data, artifact_path)


def _validate_capability_artifact(
    data: Mapping[str, Any],
    artifact_path: str,
) -> list[RecoveredPrimitive]:
    def require(container: Mapping[str, Any], key: str) -> Any:
        if key not in container:
            raise SemanticArtifactError(
                f"{artifact_path}: missing required field '{key}'"
            )
        return container[key]

    _require_root_common(data, artifact_path, PROPERTY_CAPABILITY_SCHEMA)
    game_version = str(require(data, "game_version"))
    primitives = require(data, "primitives")
    if not isinstance(primitives, list) or not primitives:
        raise SemanticArtifactError(
            f"{artifact_path}: primitives must be a non-empty list"
        )

    recovered: list[RecoveredPrimitive] = []
    seen_ids: set[str] = set()
    seen_method_indices: set[int] = set()
    for index, raw_primitive in enumerate(primitives):
        if not isinstance(raw_primitive, Mapping):
            raise SemanticArtifactError(
                f"{artifact_path}: primitives[{index}] must be an object"
            )
        p = raw_primitive
        label = f"{artifact_path}: primitives[{index}]"
        _require_primitive_evidence(p, label)

        primitive_id = _require_string(p, "primitive_id", label)
        if primitive_id in seen_ids:
            raise SemanticArtifactError(
                f"{artifact_path}: duplicate primitive_id {primitive_id!r}"
            )
        seen_ids.add(primitive_id)

        method_index = _require_method_index(p, "source_method_index", label)
        if method_index in seen_method_indices:
            raise SemanticArtifactError(
                f"{artifact_path}: duplicate source_method_index {method_index}"
            )
        seen_method_indices.add(method_index)

        native_rva = _require_rva(p, "source_native_rva", label)
        _require_body_hash(p, label)

        inputs = _capability_inputs(p, label)
        context_reads = _string_tuple(p.get("context_reads", ()), "context_reads", label)
        context_writes = _string_tuple(p.get("context_writes", ()), "context_writes", label)
        output = _require_string(p, "output", label)
        determinism = _require_string(p, "determinism", label)
        if not determinism.startswith("DETERMINISTIC"):
            raise SemanticArtifactError(
                f"{label}: determinism {determinism!r} must start with 'DETERMINISTIC'"
            )

        semantic_name = _require_string(p, "semantic_name", label)
        semantic_limit = p.get("semantic_limit")
        description = semantic_name
        if isinstance(semantic_limit, str) and semantic_limit:
            description = f"{semantic_name}: {semantic_limit}"

        spec = PrimitiveSpec(
            primitive_id=primitive_id,
            semantic_name=semantic_name,
            description=description,
            inputs=tuple(inputs),
            context_reads=context_reads,
            context_writes=context_writes,
            result=output,
            determinism=determinism,
        )
        provenance = SourceProvenance(
            game_version=game_version,
            runtime_type=_require_string(p, "source_runtime_type", label),
            method=_require_string(p, "source_method", label),
            method_index=method_index,
            native_rva=native_rva,
            evidence_level=EVIDENCE_E4,
            note=PROVENANCE_NOTE_DEFAULT,
        )
        recovered.append(RecoveredPrimitive(spec=spec, provenance=provenance))
    return recovered


def _validate_bridge_artifact(
    data: Mapping[str, Any],
    artifact_path: str,
) -> list[RecoveredPrimitive]:
    def require(container: Mapping[str, Any], key: str) -> Any:
        if key not in container:
            raise SemanticArtifactError(
                f"{artifact_path}: missing required field '{key}'"
            )
        return container[key]

    _require_root_common(data, artifact_path, PROPERTY_BRIDGE_SCHEMA)
    game_version = str(require(data, "game_version"))
    primitives = require(data, "primitives")
    if not isinstance(primitives, list) or not primitives:
        raise SemanticArtifactError(
            f"{artifact_path}: primitives must be a non-empty list"
        )

    recovered: list[RecoveredPrimitive] = []
    seen_ids: set[str] = set()
    seen_method_indices: set[int] = set()
    for index, raw_primitive in enumerate(primitives):
        if not isinstance(raw_primitive, Mapping):
            raise SemanticArtifactError(
                f"{artifact_path}: primitives[{index}] must be an object"
            )
        p = raw_primitive
        label = f"{artifact_path}: primitives[{index}]"
        _require_primitive_evidence(p, label)

        primitive_id = _require_string(p, "primitive_id", label)
        if primitive_id in seen_ids:
            raise SemanticArtifactError(
                f"{artifact_path}: duplicate primitive_id {primitive_id!r}"
            )
        seen_ids.add(primitive_id)

        identity = require(p, "runtime_identity")
        if not isinstance(identity, Mapping):
            raise SemanticArtifactError(f"{label}: runtime_identity must be an object")
        runtime_type = _require_string(identity, "runtime_type", label)
        method_index = identity.get("method_index")
        if method_index is not None:
            if isinstance(method_index, bool) or not isinstance(method_index, int):
                raise SemanticArtifactError(
                    f"{label}: runtime_identity.method_index must be an int or null"
                )
            if method_index < 0:
                raise SemanticArtifactError(
                    f"{label}: runtime_identity.method_index must be >= 0"
                )
            if method_index in seen_method_indices:
                raise SemanticArtifactError(
                    f"{artifact_path}: duplicate method_index {method_index}"
                )
            seen_method_indices.add(method_index)

        native_rva = _require_rva(p, "native_rva", label)
        _require_body_hash(p, label)
        inputs = _bridge_inputs(p, label)
        output = _require_string(p, "output", label)
        determinism = _require_string(p, "determinism", label)
        if not determinism.startswith("DETERMINISTIC"):
            raise SemanticArtifactError(
                f"{label}: determinism {determinism!r} must start with 'DETERMINISTIC'"
            )

        semantic_name = _require_string(p, "semantic_name", label)
        method_name = identity.get("method_name")
        if method_name is None:
            method = f"<unregistered helper {native_rva}>"
        elif not isinstance(method_name, str) or not method_name:
            raise SemanticArtifactError(
                f"{label}: runtime_identity.method_name must be a non-empty string or null"
            )
        else:
            method = method_name

        spec = PrimitiveSpec(
            primitive_id=primitive_id,
            semantic_name=semantic_name,
            description=semantic_name,
            inputs=tuple(inputs),
            context_reads=(),
            context_writes=(),
            result=output,
            determinism=determinism,
        )
        provenance = SourceProvenance(
            game_version=game_version,
            runtime_type=runtime_type,
            method=method,
            method_index=method_index,
            native_rva=native_rva,
            evidence_level=EVIDENCE_E4,
            note=PROVENANCE_NOTE_DEFAULT,
        )
        recovered.append(RecoveredPrimitive(spec=spec, provenance=provenance))
    return recovered


def _require_root_common(
    data: Mapping[str, Any],
    artifact_path: str,
    expected_schema: str,
) -> None:
    if data.get("schema") != expected_schema:
        raise SemanticArtifactError(
            f"{artifact_path}: unexpected schema {data.get('schema')!r}; "
            f"expected {expected_schema!r}"
        )
    game_version = data.get("game_version")
    if not isinstance(game_version, str) or not game_version:
        raise SemanticArtifactError(
            f"{artifact_path}: game_version must be a non-empty string"
        )
    capability_id = data.get("capability_id")
    if not isinstance(capability_id, str) or not capability_id:
        raise SemanticArtifactError(
            f"{artifact_path}: capability_id must be a non-empty string"
        )
    evidence_level = data.get("evidence_level")
    if evidence_level != EVIDENCE_E4:
        raise SemanticArtifactError(
            f"{artifact_path}: evidence_level {evidence_level!r}; "
            f"expected {EVIDENCE_E4!r}"
        )


def _require_primitive_evidence(p: Mapping[str, Any], label: str) -> None:
    if p.get("evidence_level") != EVIDENCE_E4:
        raise SemanticArtifactError(
            f"{label}: evidence_level {p.get('evidence_level')!r}; "
            f"expected {EVIDENCE_E4!r}"
        )


def _require_string(mapping: Mapping[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise SemanticArtifactError(f"{label}: {key} must be a non-empty string")
    return value


def _require_method_index(
    mapping: Mapping[str, Any],
    key: str,
    label: str,
) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SemanticArtifactError(f"{label}: {key} must be an int")
    if value < 0:
        raise SemanticArtifactError(f"{label}: {key} must be >= 0")
    return value


def _require_rva(mapping: Mapping[str, Any], key: str, label: str) -> str:
    value = _require_string(mapping, key, label)
    if not _HEX_RVA.match(value):
        raise SemanticArtifactError(
            f"{label}: {key} {value!r} is not an RVA hex string"
        )
    return value


def _require_body_hash(mapping: Mapping[str, Any], label: str) -> str:
    value = mapping.get("native_body_hash")
    if not isinstance(value, str) or not _HEX_SHA256.match(value):
        raise SemanticArtifactError(
            f"{label}: native_body_hash must be a 64-char hex sha256"
        )
    return value


def _string_tuple(value: Any, key: str, label: str) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, (list, tuple)):
        raise SemanticArtifactError(f"{label}: {key} must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise SemanticArtifactError(
                f"{label}: {key} items must be non-empty strings"
            )
        out.append(item)
    return tuple(out)


def _capability_inputs(
    p: Mapping[str, Any],
    label: str,
) -> list[PrimitiveInputSpec]:
    raw_inputs = p.get("inputs")
    if not isinstance(raw_inputs, list):
        raise SemanticArtifactError(f"{label}: inputs must be a list")
    out: list[PrimitiveInputSpec] = []
    for item in raw_inputs:
        if not isinstance(item, Mapping):
            raise SemanticArtifactError(f"{label}: inputs items must be objects")
        name = item.get("name")
        kind = item.get("type")
        if not isinstance(name, str) or not name:
            raise SemanticArtifactError(f"{label}: input name must be a non-empty string")
        if not isinstance(kind, str) or not kind:
            raise SemanticArtifactError(f"{label}: input type must be a non-empty string")
        out.append(PrimitiveInputSpec(name=name, type=kind))
    if not out:
        raise SemanticArtifactError(f"{label}: inputs must be a non-empty list")
    return out


def _bridge_inputs(
    p: Mapping[str, Any],
    label: str,
) -> list[PrimitiveInputSpec]:
    raw_inputs = p.get("inputs")
    if not isinstance(raw_inputs, list) or not raw_inputs:
        raise SemanticArtifactError(f"{label}: inputs must be a non-empty list")
    out: list[PrimitiveInputSpec] = []
    for item in raw_inputs:
        if not isinstance(item, str) or not item:
            raise SemanticArtifactError(f"{label}: inputs items must be non-empty strings")
        out.append(
            PrimitiveInputSpec(
                name=item,
                type=_BRIDGE_INPUT_TYPES.get(item, "runtime_value"),
            )
        )
    return out
