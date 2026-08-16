# -*- coding: utf-8 -*-
"""Narrow loader/validator for Battle Semantic Vertical Slice 01.

This is intentionally **not** a general compiler.  It reads the machine-readable
recovery artifact ``data/semantics/4.4.54/vertical_slice_01.json``, validates
the fields that the sandbox kernel needs, and produces a separated
``PrimitiveSpec`` + ``SourceProvenance`` pair that callers can register into a
``PrimitiveRegistry``.

Hot execution paths never call this module: loading happens once during kernel
setup.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.model import (
    DYNAMIC_VALUE_EQUALS_SPEC,
    PrimitiveSpec,
)
from hsr_battle_agent.battle_ir.provenance import SourceProvenance

ARTIFACT_SCHEMA = "battle_semantics_vertical_slice/1"

EXPECTED_PRIMITIVE_ID = "battle.ir.value.dynamic_value_equals"
EXPECTED_SEMANTIC_NAME = "DynamicValueEquals"
EXPECTED_DYNAMIC_VALUE_TYPES = (
    ("INT", 0),
    ("FLOAT", 1),
    ("BOOL", 2),
    ("ARRAY", 3),
    ("MAP", 4),
    ("STRING", 5),
    ("NULL", 6),
)


class SemanticArtifactError(ValueError):
    """The semantic artifact is missing a required field or mismatches E4."""


@dataclass(frozen=True)
class RecoveredPrimitive:
    """Runtime semantics + separated source provenance for one primitive."""

    spec: PrimitiveSpec
    provenance: SourceProvenance

    def provenance_reference(self) -> str:
        return self.provenance.source_reference()


def default_artifact_path() -> Path:
    # .../src/hsr_battle_agent/battle_ir/semantic_artifact.py
    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "semantics"
        / "4.4.54"
        / "vertical_slice_01.json"
    )


def load_vertical_slice_01(path: str | Path | None = None) -> RecoveredPrimitive:
    artifact_path = Path(path) if path is not None else default_artifact_path()
    try:
        raw = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SemanticArtifactError(f"cannot read semantic artifact {artifact_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SemanticArtifactError(f"semantic artifact is not valid JSON: {exc}") from exc
    return validate_vertical_slice_01(data, artifact_path=str(artifact_path))


def validate_vertical_slice_01(
    data: Mapping[str, Any],
    artifact_path: str = "<memory>",
) -> RecoveredPrimitive:
    def require(container: Mapping[str, Any], key: str) -> Any:
        if key not in container:
            raise SemanticArtifactError(
                f"{artifact_path}: missing required field '{key}'"
            )
        return container[key]

    if require(data, "schema") != ARTIFACT_SCHEMA:
        raise SemanticArtifactError(
            f"{artifact_path}: unexpected schema {data.get('schema')!r}; "
            f"expected {ARTIFACT_SCHEMA!r}"
        )

    game_version = require(data, "game_version")
    evidence_level = require(data, "evidence_level")
    if evidence_level != "E4_STATIC_MACHINE_CODE":
        raise SemanticArtifactError(
            f"{artifact_path}: evidence_level {evidence_level!r}; "
            "expected 'E4_STATIC_MACHINE_CODE'"
        )

    ir = require(data, "ir_primitive")
    if not isinstance(ir, Mapping):
        raise SemanticArtifactError(f"{artifact_path}: ir_primitive must be an object")

    spec = PrimitiveSpec.from_dict(ir)
    if spec.primitive_id != EXPECTED_PRIMITIVE_ID:
        raise SemanticArtifactError(
            f"{artifact_path}: primitive_id {spec.primitive_id!r}; "
            f"expected {EXPECTED_PRIMITIVE_ID!r}"
        )
    if spec.semantic_name != EXPECTED_SEMANTIC_NAME:
        raise SemanticArtifactError(
            f"{artifact_path}: semantic_name {spec.semantic_name!r}; "
            f"expected {EXPECTED_SEMANTIC_NAME!r}"
        )
    if spec != DYNAMIC_VALUE_EQUALS_SPEC:
        raise SemanticArtifactError(
            f"{artifact_path}: ir_primitive semantic fields do not match "
            "the recovered DynamicValueEquals specification"
        )
    if require(ir, "result") != "boolean":
        raise SemanticArtifactError(f"{artifact_path}: result must be 'boolean'")
    if require(ir, "determinism") != "DETERMINISTIC":
        raise SemanticArtifactError(
            f"{artifact_path}: determinism must be 'DETERMINISTIC'"
        )

    _validate_dynamic_value_enum(data, artifact_path)

    source_method_index = require(ir, "source_method_index")
    source_native_rva = require(ir, "source_native_rva")
    source_evidence_level = require(ir, "evidence_level")
    if source_evidence_level != evidence_level:
        raise SemanticArtifactError(
            f"{artifact_path}: ir evidence_level {source_evidence_level!r} "
            f"does not match root evidence_level {evidence_level!r}"
        )
    provenance_note = require(ir, "provenance_note")
    if "provenance only" not in provenance_note:
        raise SemanticArtifactError(
            f"{artifact_path}: provenance_note must declare provenance-only status"
        )

    provenance = SourceProvenance(
        game_version=str(game_version),
        runtime_type=str(require(ir, "source_runtime_type")),
        method=str(require(ir, "source_method")),
        method_index=int(source_method_index),
        native_rva=str(source_native_rva),
        evidence_level=str(source_evidence_level),
        note=str(provenance_note),
    )

    return RecoveredPrimitive(spec=spec, provenance=provenance)


def _validate_dynamic_value_enum(data: Mapping[str, Any], artifact_path: str) -> None:
    enum_block = data.get("dynamic_value_type_enum")
    if not isinstance(enum_block, Mapping):
        raise SemanticArtifactError(
            f"{artifact_path}: missing required field 'dynamic_value_type_enum'"
        )
    values = enum_block.get("values")
    if not isinstance(values, list) or not values:
        raise SemanticArtifactError(
            f"{artifact_path}: dynamic_value_type_enum.values must be a non-empty list"
        )
    observed = tuple((item.get("name"), item.get("ordinal")) for item in values)
    if observed != EXPECTED_DYNAMIC_VALUE_TYPES:
        raise SemanticArtifactError(
            f"{artifact_path}: dynamic_value_type_enum.values mismatch: {observed!r}"
        )
