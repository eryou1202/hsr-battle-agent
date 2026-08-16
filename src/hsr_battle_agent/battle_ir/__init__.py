# -*- coding: utf-8 -*-
"""Canonical Battle IR model.

This package contains only semantic IR structures and value representations.
Provenance (game version, method index, native RVA) is stored separately from
runtime semantics and must never participate in sandbox execution logic.
The source of truth for recovered primitives is the explicit semantic
artifact catalog, loaded and validated by ``catalog.py`` /
``semantic_artifact.py`` / ``semantic_batch.py``.
"""
from __future__ import annotations

from hsr_battle_agent.battle_ir.catalog import (
    CATALOG_SCHEMA,
    CatalogArtifactEntry,
    SemanticCatalog,
    default_catalog_path,
    load_catalog_primitives,
    load_semantic_catalog,
    validate_semantic_catalog,
)
from hsr_battle_agent.battle_ir.model import (
    DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_ARRAY_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_MAP_PRIMITIVE_ID,
    DYNAMIC_VALUE_IS_NULL_PRIMITIVE_ID,
    DYNAMIC_VALUE_STRING_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_DOUBLE_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_LONG_PRIMITIVE_ID,
    DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID,
    DYNAMIC_VALUE_TYPE_PRIMITIVE_ID,
    PrimitiveArgument,
    PrimitiveCall,
    PrimitiveInputSpec,
    PrimitiveResult,
    PrimitiveSpec,
)
from hsr_battle_agent.battle_ir.provenance import SourceProvenance
from hsr_battle_agent.battle_ir.semantic_artifact import (
    RecoveredPrimitive,
    SemanticArtifactError,
    default_artifact_path,
    load_vertical_slice_01,
)
from hsr_battle_agent.battle_ir.semantic_batch import (
    BATCH_SCHEMA,
    default_batch_02_path,
    load_dynamic_value_batch_02,
    validate_dynamic_value_batch_02,
)
from hsr_battle_agent.battle_ir.values import (
    DynamicValue,
    DynamicValueType,
    ObjectRef,
)

__all__ = [
    "BATCH_SCHEMA",
    "CATALOG_SCHEMA",
    "DYNAMIC_VALUE_EQUALS_PRIMITIVE_ID",
    "DYNAMIC_VALUE_IS_ARRAY_PRIMITIVE_ID",
    "DYNAMIC_VALUE_IS_MAP_PRIMITIVE_ID",
    "DYNAMIC_VALUE_IS_NULL_PRIMITIVE_ID",
    "DYNAMIC_VALUE_STRING_PRIMITIVE_ID",
    "DYNAMIC_VALUE_TO_BOOL_PRIMITIVE_ID",
    "DYNAMIC_VALUE_TO_DOUBLE_PRIMITIVE_ID",
    "DYNAMIC_VALUE_TO_FLOAT_PRIMITIVE_ID",
    "DYNAMIC_VALUE_TO_INT_PRIMITIVE_ID",
    "DYNAMIC_VALUE_TO_LONG_PRIMITIVE_ID",
    "DYNAMIC_VALUE_TO_UINT_PRIMITIVE_ID",
    "DYNAMIC_VALUE_TYPE_PRIMITIVE_ID",
    "CatalogArtifactEntry",
    "DynamicValue",
    "DynamicValueType",
    "ObjectRef",
    "PrimitiveArgument",
    "PrimitiveCall",
    "PrimitiveInputSpec",
    "PrimitiveResult",
    "PrimitiveSpec",
    "RecoveredPrimitive",
    "SemanticArtifactError",
    "SemanticCatalog",
    "SourceProvenance",
    "default_artifact_path",
    "default_batch_02_path",
    "default_catalog_path",
    "load_catalog_primitives",
    "load_dynamic_value_batch_02",
    "load_semantic_catalog",
    "load_vertical_slice_01",
    "validate_dynamic_value_batch_02",
    "validate_semantic_catalog",
]
