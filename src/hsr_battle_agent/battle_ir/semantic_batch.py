# -*- coding: utf-8 -*-
"""Loader/validator for Battle Semantic batch artifacts.

A batch artifact (``battle_semantics_batch/1``) contains one or more E4
recovered primitives plus the candidate-selection evidence that produced them.
This loader is intentionally narrow: it validates the fields the sandbox needs
and returns ``list[RecoveredPrimitive]``, exactly like the single-primitive
vertical-slice loader.  It is **not** a general compiler and it never derives
semantics from method names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.model import PrimitiveSpec
from hsr_battle_agent.battle_ir.provenance import (
    PROVENANCE_NOTE_DEFAULT,
    SourceProvenance,
)
from hsr_battle_agent.battle_ir.semantic_artifact import (
    EXPECTED_DYNAMIC_VALUE_TYPES,
    RecoveredPrimitive,
    SemanticArtifactError,
    _validate_dynamic_value_enum,
)

BATCH_SCHEMA = "battle_semantics_batch/1"
EVIDENCE_E4 = "E4_STATIC_MACHINE_CODE"
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEX_RVA = re.compile(r"^0x[0-9A-Fa-f]+$")


def default_batch_02_path() -> Path:
    # .../src/hsr_battle_agent/battle_ir/semantic_batch.py
    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "semantics"
        / "4.4.54"
        / "dynamic_value_batch_02.json"
    )


def load_dynamic_value_batch_02(
    path: str | Path | None = None,
) -> list[RecoveredPrimitive]:
    """Load the DynamicValue Batch 02 artifact as validated primitives."""
    artifact_path = Path(path) if path is not None else default_batch_02_path()
    return _load_batch_artifact(artifact_path, require_dynamic_value_enum=True)


def load_battle_semantics_batch(
    path: str | Path,
) -> list[RecoveredPrimitive]:
    """Load any ``battle_semantics_batch/1`` artifact as validated primitives.

    This is the shared batch loader used by the catalog.  It is not tied to a
    specific batch; batch-specific knowledge (for example the DynamicValue enum
    block of Batch 02) is passed as validation flags, never encoded as a new
    loader module.
    """
    return _load_batch_artifact(Path(path), require_dynamic_value_enum=False)


def _load_batch_artifact(
    artifact_path: Path,
    *,
    require_dynamic_value_enum: bool,
) -> list[RecoveredPrimitive]:
    try:
        raw = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SemanticArtifactError(
            f"cannot read semantic batch artifact {artifact_path}: {exc}"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SemanticArtifactError(
            f"semantic batch artifact is not valid JSON: {exc}"
        ) from exc
    return validate_battle_semantics_batch(
        data,
        artifact_path=str(artifact_path),
        require_dynamic_value_enum=require_dynamic_value_enum,
    )


def validate_dynamic_value_batch_02(
    data: Mapping[str, Any],
    artifact_path: str = "<memory>",
) -> list[RecoveredPrimitive]:
    """Back-compatible Batch 02 validator (requires the DynamicValue enum)."""
    return validate_battle_semantics_batch(
        data,
        artifact_path=artifact_path,
        require_dynamic_value_enum=True,
    )


def validate_battle_semantics_batch(
    data: Mapping[str, Any],
    artifact_path: str = "<memory>",
    *,
    require_dynamic_value_enum: bool = False,
) -> list[RecoveredPrimitive]:
    """Validate the shared ``battle_semantics_batch/1`` contract.

    Batch-specific evidence blocks are optional.  When
    ``require_dynamic_value_enum`` is true the Batch 02 DynamicValue enum block
    is mandatory; for other batches (FixPoint Comparison Batch 03) the block
    is allowed
    but not required, and is validated whenever present.
    """
    def require(container: Mapping[str, Any], key: str) -> Any:
        if key not in container:
            raise SemanticArtifactError(
                f"{artifact_path}: missing required field '{key}'"
            )
        return container[key]

    if require(data, "schema") != BATCH_SCHEMA:
        raise SemanticArtifactError(
            f"{artifact_path}: unexpected schema {data.get('schema')!r}; "
            f"expected {BATCH_SCHEMA!r}"
        )

    game_version = require(data, "game_version")
    if not isinstance(game_version, str) or not game_version:
        raise SemanticArtifactError(f"{artifact_path}: game_version must be a string")

    evidence_level = require(data, "evidence_level")
    if evidence_level != EVIDENCE_E4:
        raise SemanticArtifactError(
            f"{artifact_path}: evidence_level {evidence_level!r}; "
            f"expected {EVIDENCE_E4!r}"
        )

    if require_dynamic_value_enum:
        _validate_dynamic_value_enum(data, artifact_path)
    elif "dynamic_value_type_enum" in data:
        _validate_dynamic_value_enum(data, artifact_path)

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

        p_evidence = p.get("evidence_level")
        if p_evidence != EVIDENCE_E4:
            raise SemanticArtifactError(
                f"{label}: evidence_level {p_evidence!r}; expected {EVIDENCE_E4!r}"
            )

        spec = _build_spec(p, label)
        if spec.primitive_id in seen_ids:
            raise SemanticArtifactError(
                f"{artifact_path}: duplicate primitive_id {spec.primitive_id!r}"
            )
        seen_ids.add(spec.primitive_id)

        source_method_index = _require_int(p, "source_method_index", label)
        if source_method_index in seen_method_indices:
            raise SemanticArtifactError(
                f"{artifact_path}: duplicate source_method_index {source_method_index}"
            )
        seen_method_indices.add(source_method_index)

        source_native_rva = require(p, "source_native_rva")
        if not isinstance(source_native_rva, str) or not _HEX_RVA.match(
            source_native_rva
        ):
            raise SemanticArtifactError(
                f"{label}: source_native_rva {source_native_rva!r} is not an RVA hex string"
            )
        native_body_hash = require(p, "native_body_hash")
        if not isinstance(native_body_hash, str) or not _HEX_SHA256.match(
            native_body_hash
        ):
            raise SemanticArtifactError(
                f"{label}: native_body_hash must be a 64-char hex sha256"
            )

        for key in (
            "source_runtime_type",
            "source_method",
            "semantic_name",
            "result",
            "determinism",
        ):
            value = require(p, key)
            if not isinstance(value, str) or not value:
                raise SemanticArtifactError(f"{label}: {key} must be a non-empty string")
        if p["determinism"] != "DETERMINISTIC":
            raise SemanticArtifactError(
                f"{label}: determinism {p['determinism']!r}; expected 'DETERMINISTIC'"
            )
        if spec.context_writes != ():
            raise SemanticArtifactError(
                f"{label}: batch primitives must have empty context_writes, "
                f"got {spec.context_writes!r}"
            )

        provenance = SourceProvenance(
            game_version=str(game_version),
            runtime_type=str(p["source_runtime_type"]),
            method=str(p["source_method"]),
            method_index=int(source_method_index),
            native_rva=str(source_native_rva),
            evidence_level=str(p_evidence),
            note=PROVENANCE_NOTE_DEFAULT,
        )
        recovered.append(RecoveredPrimitive(spec=spec, provenance=provenance))

    return recovered


def _require_int(mapping: Mapping[str, Any], key: str, label: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SemanticArtifactError(f"{label}: {key} must be an int")
    if value < 0:
        raise SemanticArtifactError(f"{label}: {key} must be >= 0")
    return value


def _build_spec(data: Mapping[str, Any], label: str) -> PrimitiveSpec:
    spec_data = {
        "primitive_id": data.get("primitive_id"),
        "semantic_name": data.get("semantic_name"),
        "description": data.get("description"),
        "inputs": data.get("inputs"),
        "context_reads": data.get("context_reads", ()),
        "context_writes": data.get("context_writes", ()),
        "result": data.get("result"),
        "determinism": data.get("determinism"),
    }
    try:
        return PrimitiveSpec.from_dict(spec_data)
    except (KeyError, TypeError, ValueError) as exc:
        raise SemanticArtifactError(f"{label}: invalid primitive spec: {exc}") from exc


def expected_dynamic_value_types() -> tuple[tuple[str, int], ...]:
    """Expose the seven recovered enum ordinals for catalog/loader tests."""
    return EXPECTED_DYNAMIC_VALUE_TYPES
