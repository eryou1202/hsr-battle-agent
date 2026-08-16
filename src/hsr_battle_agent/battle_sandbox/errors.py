# -*- coding: utf-8 -*-
"""Sandbox kernel error types."""
from __future__ import annotations


class BattleSandboxError(Exception):
    """Base class for all sandbox kernel errors."""


class UnsupportedPrimitiveError(BattleSandboxError):
    def __init__(self, primitive_id: str) -> None:
        super().__init__(
            f"unsupported battle IR primitive: {primitive_id!r} "
            "(no silent no-op; register the primitive or fail)"
        )
        self.primitive_id = primitive_id


class InvalidPrimitiveInputError(BattleSandboxError):
    pass


class DuplicatePrimitiveError(BattleSandboxError):
    def __init__(self, primitive_id: str) -> None:
        super().__init__(f"primitive already registered: {primitive_id!r}")
        self.primitive_id = primitive_id


class FrozenRegistryError(BattleSandboxError):
    def __init__(self) -> None:
        super().__init__("primitive registry is frozen")


class UnsupportedStateVersionError(BattleSandboxError):
    def __init__(self, schema_version: object) -> None:
        super().__init__(
            f"unsupported BattleState schema_version: {schema_version!r}"
        )
        self.schema_version = schema_version


class StubNotImplementedError(BattleSandboxError):
    """Explicit NOT_IMPLEMENTED guard for future sandbox surface."""
