# -*- coding: utf-8 -*-
"""Opaque unresolved store for the Terra state path.

TERRA F02-007.  Unresolved material is carried as :class:`UnknownHandle`
instances inside an explicitly typed opaque store.  The store preserves the
payload losslessly, never interprets it, and folds it into its own identity so
that changing an opaque payload changes the store's identity.

Nothing here resolves anything: there is no lifecycle, no interpretation and no
fallback.  UNKNOWN stays UNKNOWN.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import (
    EvidenceVocabularyError,
    UnknownHandle,
)
from hsr_battle_agent.battle_sandbox.stores.core import (
    STORE_FAMILIES,
    StoreDefinition,
    StoreEntry,
    TypedStore,
    TypedStoreError,
    require_store_family,
)
from hsr_battle_agent.battle_ir.lossless_value import PresenceValue

__all__ = [
    "OPAQUE_STORE_SCHEMA",
    "OpaqueUnresolvedStore",
    "opaque_store_definition",
]


OPAQUE_STORE_SCHEMA = "opaque_unresolved_store/1"

OPAQUE_STORE_FAMILY = "opaque_handles"


def opaque_store_definition() -> StoreDefinition:
    """The declared definition of the opaque store family."""
    return require_store_family(OPAQUE_STORE_FAMILY)


@dataclass(frozen=True)
class OpaqueUnresolvedStore:
    """An ordered store of unresolved handles, carried losslessly.

    Handles are held in an ordered tuple, duplicates are preserved, and the
    store identity is a digest over every handle's own identity hash, so a
    changed opaque payload changes the store identity.
    """

    handles: tuple[UnknownHandle, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if isinstance(self.handles, (str, bytes)) or not isinstance(
            self.handles, (tuple, list)
        ):
            raise TypedStoreError(
                "OpaqueUnresolvedStore.handles must be a tuple or list"
            )
        for handle in self.handles:
            if not isinstance(handle, UnknownHandle):
                raise TypedStoreError(
                    "OpaqueUnresolvedStore entries must be UnknownHandle "
                    f"instances, got {type(handle).__name__}"
                )
        object.__setattr__(self, "handles", tuple(self.handles))

    # -- surface ---------------------------------------------------------

    def definition(self) -> StoreDefinition:
        return opaque_store_definition()

    def is_empty(self) -> bool:
        return len(self.handles) == 0

    def __len__(self) -> int:
        return len(self.handles)

    def blocker_ids(self) -> tuple[str, ...]:
        """Blocker ids in insertion order, duplicates included."""
        return tuple(handle.blocker_id for handle in self.handles)

    def with_handle(self, handle: UnknownHandle) -> "OpaqueUnresolvedStore":
        """Return a new store with one handle appended, order preserved."""
        if not isinstance(handle, UnknownHandle):
            raise TypedStoreError(
                f"with_handle() requires an UnknownHandle, got "
                f"{type(handle).__name__}"
            )
        return OpaqueUnresolvedStore(handles=self.handles + (handle,))

    def identity_hash(self) -> str:
        """Digest over every handle's identity hash, in order."""
        text = json.dumps(
            {
                "family": OPAQUE_STORE_FAMILY,
                "handles": [handle.identity_hash() for handle in self.handles],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def resolve(self, *_args: Any, **_kwargs: Any) -> NoReturn:
        """Refuse: an opaque store resolves nothing."""
        raise TypedStoreError(
            "an opaque unresolved store never resolves material; supply the "
            "required evidence and rebuild"
        )

    def __bool__(self) -> NoReturn:
        raise TypedStoreError(
            "OpaqueUnresolvedStore has no truthiness; use is_empty()"
        )

    # -- interop with the typed store ------------------------------------

    def to_typed_store(self) -> TypedStore:
        """Project onto the generic typed store shape.

        Populated directly rather than through ``TypedStore.append``, because a
        generic write to an opaque family is forbidden.
        """
        entries = tuple(
            StoreEntry(
                key=handle.blocker_id,
                value=PresenceValue.present(copy.deepcopy(handle.to_dict())),
                occurrence=index,
            )
            for index, handle in enumerate(self.handles)
        )
        return TypedStore(definition=opaque_store_definition(), entries=entries)

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OPAQUE_STORE_SCHEMA,
            "definition": opaque_store_definition().to_dict(),
            "handles": [handle.to_dict() for handle in self.handles],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OpaqueUnresolvedStore":
        if not isinstance(data, Mapping):
            raise TypedStoreError(
                f"opaque store document must be a mapping, got "
                f"{type(data).__name__}"
            )
        if "schema" not in data:
            raise TypedStoreError(
                "opaque store document is missing its schema marker; a document "
                "without one is not an opaque store"
            )
        schema = data["schema"]
        if schema != OPAQUE_STORE_SCHEMA:
            raise TypedStoreError(
                f"unknown opaque store schema {schema!r}; expected "
                f"{OPAQUE_STORE_SCHEMA!r}"
            )
        raw = data["handles"] if "handles" in data else []
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
            raise TypedStoreError("opaque store handles must be a list")
        try:
            handles = tuple(UnknownHandle.from_dict(item) for item in raw)
        except EvidenceVocabularyError as exc:
            raise TypedStoreError(f"invalid opaque handle: {exc}") from exc
        return cls(handles=handles)

    def empty_copy(self) -> "OpaqueUnresolvedStore":
        return OpaqueUnresolvedStore()
