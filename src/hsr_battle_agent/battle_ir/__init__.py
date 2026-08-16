# -*- coding: utf-8 -*-
"""Canonical Battle IR model.

This package contains only semantic IR structures and value representations.
Provenance (game version, method index, native RVA) is stored separately from
runtime semantics and must never participate in sandbox execution logic.
"""
from __future__ import annotations

from hsr_battle_agent.battle_ir.model import (
    DYNAMIC_VALUE_EQUALS_SPEC,
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
from hsr_battle_agent.battle_ir.values import (
    DynamicValue,
    DynamicValueType,
    ObjectRef,
)

__all__ = [
    "DYNAMIC_VALUE_EQUALS_SPEC",
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
    "SourceProvenance",
    "default_artifact_path",
    "load_vertical_slice_01",
]
