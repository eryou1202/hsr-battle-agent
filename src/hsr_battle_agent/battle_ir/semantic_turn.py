# -*- coding: utf-8 -*-
"""Narrow validator/loader for Turn/AV Semantics 29."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.model import (
    TURN_ADVANCE_TO_NEXT_ACTOR_PRIMITIVE_ID,
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

TURN_AV_SCHEMA = "turn_av_semantics/1"
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEX_RVA = re.compile(r"^0x[0-9A-Fa-f]+$")


def load_turn_av_semantics(path: str | Path) -> list[RecoveredPrimitive]:
    artifact_path = Path(path)
    try:
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SemanticArtifactError(
            f"cannot read Turn/AV artifact {artifact_path}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise SemanticArtifactError(
            f"Turn/AV artifact is not valid JSON: {exc}"
        ) from exc
    return validate_turn_av_semantics(data, artifact_path=str(artifact_path))


def validate_turn_av_semantics(
    data: Mapping[str, Any], artifact_path: str = "<memory>"
) -> list[RecoveredPrimitive]:
    if not isinstance(data, Mapping):
        raise SemanticArtifactError(f"{artifact_path}: root must be an object")
    if data.get("schema") != TURN_AV_SCHEMA:
        raise SemanticArtifactError(
            f"{artifact_path}: expected schema {TURN_AV_SCHEMA!r}"
        )
    if data.get("evidence_level") != "E4_STATIC_MACHINE_CODE":
        raise SemanticArtifactError(f"{artifact_path}: expected E4 evidence")
    game_version = data.get("game_version")
    if not isinstance(game_version, str) or not game_version:
        raise SemanticArtifactError(f"{artifact_path}: invalid game_version")

    methods = data.get("native_methods")
    if not isinstance(methods, list) or not methods:
        raise SemanticArtifactError(f"{artifact_path}: native_methods must be non-empty")
    method_by_index: dict[int, Mapping[str, Any]] = {}
    for index, method in enumerate(methods):
        label = f"{artifact_path}: native_methods[{index}]"
        if not isinstance(method, Mapping):
            raise SemanticArtifactError(f"{label} must be an object")
        method_index = method.get("method_index")
        if isinstance(method_index, bool) or not isinstance(method_index, int):
            raise SemanticArtifactError(f"{label}: invalid method_index")
        rva = method.get("native_rva")
        body_hash = method.get("bounded_body_sha256")
        if not isinstance(rva, str) or _HEX_RVA.fullmatch(rva) is None:
            raise SemanticArtifactError(f"{label}: invalid native_rva")
        if not isinstance(body_hash, str) or _HEX_SHA256.fullmatch(body_hash) is None:
            raise SemanticArtifactError(f"{label}: invalid body hash")
        method_by_index[method_index] = method

    primitive = data.get("primitive")
    if not isinstance(primitive, Mapping):
        raise SemanticArtifactError(f"{artifact_path}: primitive must be an object")
    primitive_id = primitive.get("primitive_id")
    if primitive_id != TURN_ADVANCE_TO_NEXT_ACTOR_PRIMITIVE_ID:
        raise SemanticArtifactError(f"{artifact_path}: unexpected primitive_id")
    source_method_index = primitive.get("source_method_index")
    if source_method_index not in method_by_index:
        raise SemanticArtifactError(
            f"{artifact_path}: source method lacks bounded native evidence"
        )
    source = method_by_index[source_method_index]
    source_rva = primitive.get("source_native_rva")
    if source_rva != source.get("native_rva"):
        raise SemanticArtifactError(f"{artifact_path}: source RVA mismatch")

    inputs = primitive.get("inputs")
    if inputs != []:
        raise SemanticArtifactError(
            f"{artifact_path}: advance primitive must have no explicit inputs"
        )
    context_reads = _string_tuple(
        primitive.get("context_reads"), "context_reads", artifact_path
    )
    context_writes = _string_tuple(
        primitive.get("context_writes"), "context_writes", artifact_path
    )
    semantic_name = primitive.get("semantic_name")
    result = primitive.get("output")
    determinism = primitive.get("determinism")
    for name, value in (
        ("semantic_name", semantic_name),
        ("output", result),
        ("determinism", determinism),
    ):
        if not isinstance(value, str) or not value:
            raise SemanticArtifactError(f"{artifact_path}: invalid {name}")
    if not determinism.startswith("DETERMINISTIC"):
        raise SemanticArtifactError(f"{artifact_path}: invalid determinism")

    spec = PrimitiveSpec(
        primitive_id=primitive_id,
        semantic_name=semantic_name,
        description=(
            "Ordinary eligible action-list sort, next-actor selection, and "
            "remaining/elapsed action-delay advance"
        ),
        inputs=(),
        context_reads=context_reads,
        context_writes=context_writes,
        result=result,
        determinism=determinism,
    )
    provenance = SourceProvenance(
        game_version=game_version,
        runtime_type="RPG.GameCore.TurnBasedGameMode",
        method=str(primitive.get("source_method")),
        method_index=source_method_index,
        native_rva=source_rva,
        evidence_level="E4_STATIC_MACHINE_CODE",
        note=PROVENANCE_NOTE_DEFAULT,
    )
    return [RecoveredPrimitive(spec=spec, provenance=provenance)]


def _string_tuple(value: Any, name: str, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise SemanticArtifactError(f"{label}: {name} must be a string list")
    return tuple(value)
