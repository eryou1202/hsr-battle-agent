# -*- coding: utf-8 -*-
"""Minimal semantic artifact catalog.

Boot path:

    catalog.json
      -> artifact validation (schema + sha256 + enabled)
      -> single / batch artifact loaders
      -> list[RecoveredPrimitive]
      -> implementation bindings
      -> frozen PrimitiveRegistry

The catalog is the explicit source of truth.  Filesystem globs are **not**
used to discover semantic artifacts, and execution paths never read the
catalog or artifacts after registry setup.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.semantic_artifact import (
    RecoveredPrimitive,
    SemanticArtifactError,
    load_vertical_slice_01,
)
from hsr_battle_agent.battle_ir.semantic_batch import (
    load_battle_semantics_batch,
)
from hsr_battle_agent.battle_ir.semantic_property import (
    PROPERTY_BRIDGE_SCHEMA,
    PROPERTY_CAPABILITY_SCHEMA,
    load_property_bridge,
    load_property_capability,
)
from hsr_battle_agent.battle_ir.semantic_turn import (
    TURN_AV_SCHEMA,
    load_turn_av_semantics,
)

CATALOG_SCHEMA = "battle_semantics_catalog/1"
VERTICAL_SLICE_SCHEMA = "battle_semantics_vertical_slice/1"
BATCH_SCHEMA = "battle_semantics_batch/1"

_LOADERS = {
    VERTICAL_SLICE_SCHEMA: lambda path: [load_vertical_slice_01(path)],
    BATCH_SCHEMA: load_battle_semantics_batch,
    PROPERTY_CAPABILITY_SCHEMA: load_property_capability,
    PROPERTY_BRIDGE_SCHEMA: load_property_bridge,
    TURN_AV_SCHEMA: load_turn_av_semantics,
}


@dataclass(frozen=True)
class CatalogArtifactEntry:
    path: str
    schema: str
    sha256: str
    enabled: bool

    def resolved_path(self, catalog_path: Path) -> Path:
        candidate = Path(self.path)
        if candidate.is_absolute():
            return candidate
        return catalog_path.parent / candidate

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "schema": self.schema,
            "sha256": self.sha256,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class SemanticCatalog:
    schema: str
    game_version: str
    artifacts: tuple[CatalogArtifactEntry, ...]
    catalog_path: Path

    def load_enabled_primitives(self) -> list[RecoveredPrimitive]:
        recovered: list[RecoveredPrimitive] = []
        seen_ids: set[str] = set()
        for entry in self.artifacts:
            if not entry.enabled:
                continue
            path = entry.resolved_path(self.catalog_path)
            try:
                raw = path.read_bytes()
            except OSError as exc:
                raise SemanticArtifactError(
                    f"cannot read semantic artifact {path}: {exc}"
                ) from exc
            actual_sha256 = hashlib.sha256(raw).hexdigest()
            if actual_sha256 != entry.sha256:
                raise SemanticArtifactError(
                    f"{path}: sha256 mismatch (catalog {entry.sha256}, "
                    f"actual {actual_sha256})"
                )
            try:
                loader = _LOADERS[entry.schema]
            except KeyError:
                raise SemanticArtifactError(
                    f"{path}: unsupported artifact schema {entry.schema!r}"
                ) from None
            primitives = loader(path)
            for primitive in primitives:
                primitive_id = primitive.spec.primitive_id
                if primitive_id in seen_ids:
                    raise SemanticArtifactError(
                        f"duplicate primitive_id across catalog artifacts: {primitive_id!r}"
                    )
                seen_ids.add(primitive_id)
                recovered.append(primitive)
        return recovered


def default_catalog_path() -> Path:
    # .../src/hsr_battle_agent/battle_ir/catalog.py
    return (
        Path(__file__).resolve().parents[3]
        / "data"
        / "semantics"
        / "4.4.54"
        / "catalog.json"
    )


def load_semantic_catalog(path: str | Path | None = None) -> SemanticCatalog:
    catalog_path = Path(path) if path is not None else default_catalog_path()
    try:
        raw = catalog_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SemanticArtifactError(f"cannot read semantic catalog {catalog_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SemanticArtifactError(f"semantic catalog is not valid JSON: {exc}") from exc
    return validate_semantic_catalog(data, catalog_path=catalog_path)


def validate_semantic_catalog(
    data: Mapping[str, Any],
    catalog_path: str | Path = "<memory>",
) -> SemanticCatalog:
    path_obj = Path(catalog_path)
    label = str(catalog_path)

    def require(container: Mapping[str, Any], key: str) -> Any:
        if key not in container:
            raise SemanticArtifactError(f"{label}: missing required field '{key}'")
        return container[key]

    if require(data, "schema") != CATALOG_SCHEMA:
        raise SemanticArtifactError(
            f"{label}: unexpected schema {data.get('schema')!r}; "
            f"expected {CATALOG_SCHEMA!r}"
        )
    game_version = require(data, "game_version")
    if not isinstance(game_version, str) or not game_version:
        raise SemanticArtifactError(f"{label}: game_version must be a non-empty string")

    raw_artifacts = require(data, "artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise SemanticArtifactError(f"{label}: artifacts must be a non-empty list")

    entries: list[CatalogArtifactEntry] = []
    seen_paths: set[str] = set()
    for index, raw_entry in enumerate(raw_artifacts):
        if not isinstance(raw_entry, Mapping):
            raise SemanticArtifactError(f"{label}: artifacts[{index}] must be an object")
        entry_label = f"{label}: artifacts[{index}]"
        rel_path = require(raw_entry, "path")
        if not isinstance(rel_path, str) or not rel_path:
            raise SemanticArtifactError(f"{entry_label}: path must be a non-empty string")
        if rel_path in seen_paths:
            raise SemanticArtifactError(f"{entry_label}: duplicate path {rel_path!r}")
        seen_paths.add(rel_path)
        schema = require(raw_entry, "schema")
        if schema not in _LOADERS:
            raise SemanticArtifactError(f"{entry_label}: unsupported artifact schema {schema!r}")
        sha256 = require(raw_entry, "sha256")
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(char not in "0123456789abcdef" for char in sha256)
        ):
            raise SemanticArtifactError(f"{entry_label}: sha256 must be a lowercase 64-char hex string")
        enabled = require(raw_entry, "enabled")
        if not isinstance(enabled, bool):
            raise SemanticArtifactError(f"{entry_label}: enabled must be a boolean")
        entries.append(
            CatalogArtifactEntry(
                path=rel_path,
                schema=str(schema),
                sha256=str(sha256),
                enabled=enabled,
            )
        )
    return SemanticCatalog(
        schema=CATALOG_SCHEMA,
        game_version=str(game_version),
        artifacts=tuple(entries),
        catalog_path=path_obj,
    )


def load_catalog_primitives(
    path: str | Path | None = None,
) -> list[RecoveredPrimitive]:
    """Load every enabled catalog artifact and return unified primitives."""
    return load_semantic_catalog(path).load_enabled_primitives()
