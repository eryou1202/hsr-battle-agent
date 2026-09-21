# -*- coding: utf-8 -*-
"""Independent Terra BattleState aggregate.

This is the first state aggregate on the Terra path.  It composes the frozen
one-owner-per-family store catalog with a revision, allocator, sandbox RNG
state sequence and explicit opaque-unresolved stores.  It neither subclasses nor
projects to the legacy :mod:`battle_sandbox.state` ``BattleState``.

The class is a representation boundary only.  It implements no transaction,
lifecycle or client-native RNG semantics, and it provides no bidirectional
legacy facade.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from hsr_battle_agent.battle_sandbox.identity import IdentityAllocator
from hsr_battle_agent.battle_sandbox.opaque import OpaqueUnresolvedStore
from hsr_battle_agent.battle_sandbox.revision import (
    RevisionAndTransactionSequence,
    StateRevision,
)
from hsr_battle_agent.battle_sandbox.rng import (
    SANDBOX_RNG_ALGORITHM,
    SandboxRng,
)
from hsr_battle_agent.battle_sandbox.state import F01StateEnvelope
from hsr_battle_agent.battle_sandbox.stores.core import (
    STORE_FAMILY_NAMES,
    TypedStore,
    empty_stores,
)
from hsr_battle_agent.battle_sandbox.stores.protocols import (
    ALLOCATOR_FIELD_FAMILY,
    FROZEN_FIELD_FAMILIES,
    OPAQUE_FIELD_FAMILIES,
    REVISION_FIELD_FAMILY,
    RNG_FIELD_FAMILY,
)

__all__ = [
    "TERRA_BATTLE_STATE_SCHEMA",
    "TERRA_COMPONENT_FIELD_FAMILIES",
    "TERRA_TYPED_STORE_FAMILIES",
    "TerraBattleState",
    "TerraStateError",
]

TERRA_BATTLE_STATE_SCHEMA = "terra_battle_state/2"

TERRA_COMPONENT_FIELD_FAMILIES = MappingProxyType(
    {
        REVISION_FIELD_FAMILY: "revision_sequence",
        ALLOCATOR_FIELD_FAMILY: "allocator",
        RNG_FIELD_FAMILY: "rng_state",
        **{family: "opaque_stores" for family in OPAQUE_FIELD_FAMILIES},
    }
)

TERRA_TYPED_STORE_FAMILIES: tuple[str, ...] = tuple(
    name for name in STORE_FAMILY_NAMES if name not in TERRA_COMPONENT_FIELD_FAMILIES
)


class TerraStateError(ValueError):
    """Raised for malformed or incompletely owned Terra state."""


def _require_exact_keys(
    data: Mapping[str, Any], expected: set[str], label: str
) -> None:
    actual = set(data)
    if actual != expected:
        missing = tuple(sorted(expected - actual))
        extra = tuple(sorted(actual - expected))
        raise TerraStateError(
            f"{label} keys do not match the frozen ownership catalog; "
            f"missing={missing}, extra={extra}"
        )


def _validate_rng_document(data: Mapping[str, Any]) -> None:
    """Reject missing/defaulted RNG fields before the legacy RNG reader."""
    if not isinstance(data, Mapping):
        raise TerraStateError("rng_state must be a mapping")
    if set(data) != {"schema_version", "algorithm", "state"}:
        raise TerraStateError(
            "rng_state must contain exactly schema_version, algorithm and state"
        )
    if data["algorithm"] != SANDBOX_RNG_ALGORITHM:
        raise TerraStateError(
            "Terra state accepts only the declared sandbox RNG algorithm; "
            "client-native RNG remains unknown and distinct"
        )
    state = data["state"]
    if not isinstance(state, Mapping) or set(state) != {
        "version",
        "internal_state",
        "gauss_next",
    }:
        raise TerraStateError(
            "rng_state.state must contain exactly version, internal_state and "
            "gauss_next"
        )


class TerraBattleState:
    """A complete, independently owned Terra state representation.

    All 61 frozen field families are represented exactly once.  The three
    structural component families and eight opaque families are held by their
    dedicated objects; every remaining family has its own ``TypedStore``.
    Caller-owned allocator and RNG objects are cloned on entry and exit.
    """

    __slots__ = (
        "_stores",
        "_revision_sequence",
        "_allocator",
        "_rng",
        "_opaque",
    )

    def __init__(
        self,
        *,
        revision_sequence: RevisionAndTransactionSequence,
        allocator: IdentityAllocator,
        rng_state: SandboxRng,
        stores: Mapping[str, TypedStore] | None = None,
        opaque_stores: Mapping[str, OpaqueUnresolvedStore] | None = None,
    ) -> None:
        if not isinstance(
            revision_sequence, RevisionAndTransactionSequence
        ):
            raise TerraStateError(
                "revision_sequence must be a RevisionAndTransactionSequence; "
                "published revision, replay sequence and committed effect "
                "sequence are all required explicitly"
            )
        if not isinstance(allocator, IdentityAllocator):
            raise TerraStateError("allocator must be an IdentityAllocator")
        if not isinstance(rng_state, SandboxRng):
            raise TerraStateError("rng_state must be a SandboxRng")

        all_empty = empty_stores()
        selected_stores: Mapping[str, TypedStore]
        if stores is None:
            selected_stores = {
                name: all_empty[name] for name in TERRA_TYPED_STORE_FAMILIES
            }
        else:
            if not isinstance(stores, Mapping):
                raise TerraStateError("stores must be a mapping")
            selected_stores = stores
        _require_exact_keys(
            selected_stores,
            set(TERRA_TYPED_STORE_FAMILIES),
            "typed store",
        )
        normalized_stores: dict[str, TypedStore] = {}
        for name in TERRA_TYPED_STORE_FAMILIES:
            store = selected_stores[name]
            if not isinstance(store, TypedStore) or store.name != name:
                raise TerraStateError(
                    f"typed store {name!r} must be a TypedStore for that exact family"
                )
            # A serialization round trip provides a private, validated value.
            normalized_stores[name] = TypedStore.from_dict(store.to_dict())

        selected_opaque: Mapping[str, OpaqueUnresolvedStore]
        if opaque_stores is None:
            selected_opaque = {
                name: OpaqueUnresolvedStore(field_family=name)
                for name in OPAQUE_FIELD_FAMILIES
            }
        else:
            if not isinstance(opaque_stores, Mapping):
                raise TerraStateError("opaque_stores must be a mapping")
            selected_opaque = opaque_stores
        _require_exact_keys(
            selected_opaque,
            set(OPAQUE_FIELD_FAMILIES),
            "opaque store",
        )
        normalized_opaque: dict[str, OpaqueUnresolvedStore] = {}
        for name in OPAQUE_FIELD_FAMILIES:
            store = selected_opaque[name]
            if not isinstance(store, OpaqueUnresolvedStore):
                raise TerraStateError(
                    f"opaque store {name!r} must be an OpaqueUnresolvedStore"
                )
            if store.field_family != name:
                raise TerraStateError(
                    f"opaque store {name!r} carries family {store.field_family!r}"
                )
            normalized_opaque[name] = OpaqueUnresolvedStore.from_dict(
                store.to_dict()
            )

        represented = (
            set(normalized_stores)
            | set(normalized_opaque)
            | {
                REVISION_FIELD_FAMILY,
                ALLOCATOR_FIELD_FAMILY,
                RNG_FIELD_FAMILY,
            }
        )
        if represented != set(FROZEN_FIELD_FAMILIES):
            raise TerraStateError(
                "Terra state ownership is incomplete or duplicated relative to "
                "the frozen field-family catalog"
            )

        self._stores = normalized_stores
        self._opaque = normalized_opaque
        self._revision_sequence = revision_sequence
        self._allocator = allocator.clone()
        self._rng = rng_state.clone()

    @property
    def revision(self) -> StateRevision:
        """The published revision part of the complete sequence component."""
        return self._revision_sequence.published_revision

    @property
    def revision_sequence(self) -> RevisionAndTransactionSequence:
        return self._revision_sequence

    @property
    def stores(self) -> Mapping[str, TypedStore]:
        # TypedStore is a frozen wrapper, but a PRESENT payload may itself be a
        # list/dict. Return validated copies so nested mutation cannot reach the
        # aggregate through the read surface.
        return MappingProxyType(
            {
                name: TypedStore.from_dict(store.to_dict())
                for name, store in self._stores.items()
            }
        )

    @property
    def opaque_stores(self) -> Mapping[str, OpaqueUnresolvedStore]:
        # UnknownHandle payload/provenance values can contain mutable nested
        # containers; copy through the lossless schema before exporting.
        return MappingProxyType(
            {
                name: OpaqueUnresolvedStore.from_dict(store.to_dict())
                for name, store in self._opaque.items()
            }
        )

    @property
    def allocator(self) -> IdentityAllocator:
        return self._allocator.clone()

    @property
    def rng_state(self) -> SandboxRng:
        return self._rng.clone()

    def owned_field_families(self) -> tuple[str, ...]:
        """Every frozen field family, in authority declaration order."""
        return tuple(FROZEN_FIELD_FAMILIES)

    def owner_component_for(self, field_family: str) -> str:
        if field_family not in FROZEN_FIELD_FAMILIES:
            raise TerraStateError(f"unclassified field family {field_family!r}")
        return TERRA_COMPONENT_FIELD_FAMILIES.get(field_family, "typed_store")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TERRA_BATTLE_STATE_SCHEMA,
            "stores": [
                F01StateEnvelope(self._stores[name].to_dict()).to_dict()
                for name in TERRA_TYPED_STORE_FAMILIES
            ],
            "revision_and_transaction_sequence": self._revision_sequence.to_dict(),
            "allocator": self._allocator.to_dict(),
            "rng_state": self._rng.to_dict(),
            "opaque_stores": [
                F01StateEnvelope(self._opaque[name].to_dict()).to_dict()
                for name in OPAQUE_FIELD_FAMILIES
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TerraBattleState":
        if not isinstance(data, Mapping):
            raise TerraStateError("TerraBattleState document must be a mapping")
        expected = {
            "schema",
            "stores",
            "revision_and_transaction_sequence",
            "allocator",
            "rng_state",
            "opaque_stores",
        }
        if set(data) != expected:
            raise TerraStateError(
                "TerraBattleState document must contain exactly schema, stores, "
                "revision_and_transaction_sequence, allocator, rng_state and "
                "opaque_stores"
            )
        if data["schema"] != TERRA_BATTLE_STATE_SCHEMA:
            raise TerraStateError(
                f"unknown TerraBattleState schema {data['schema']!r}"
            )

        raw_stores = data["stores"]
        if isinstance(raw_stores, (str, bytes)) or not isinstance(
            raw_stores, (tuple, list)
        ):
            raise TerraStateError("stores must be a list")
        stores: dict[str, TypedStore] = {}
        for raw in raw_stores:
            try:
                decoded = F01StateEnvelope.from_dict(raw).value
            except (TypeError, ValueError) as exc:
                raise TerraStateError(f"invalid lossless typed-store envelope: {exc}") from exc
            if not isinstance(decoded, Mapping):
                raise TerraStateError("typed-store envelope must decode to a mapping")
            store = TypedStore.from_dict(decoded)
            if store.name in stores:
                raise TerraStateError(f"duplicate store family {store.name!r}")
            stores[store.name] = store

        raw_opaque = data["opaque_stores"]
        if isinstance(raw_opaque, (str, bytes)) or not isinstance(
            raw_opaque, (tuple, list)
        ):
            raise TerraStateError("opaque_stores must be a list")
        opaque: dict[str, OpaqueUnresolvedStore] = {}
        for raw in raw_opaque:
            try:
                decoded = F01StateEnvelope.from_dict(raw).value
            except (TypeError, ValueError) as exc:
                raise TerraStateError(f"invalid lossless opaque-store envelope: {exc}") from exc
            if not isinstance(decoded, Mapping):
                raise TerraStateError("opaque-store envelope must decode to a mapping")
            store = OpaqueUnresolvedStore.from_dict(decoded)
            if store.field_family in opaque:
                raise TerraStateError(
                    f"duplicate opaque store family {store.field_family!r}"
                )
            opaque[store.field_family] = store

        rng_document = data["rng_state"]
        _validate_rng_document(rng_document)
        try:
            return cls(
                revision_sequence=RevisionAndTransactionSequence.from_dict(
                    data["revision_and_transaction_sequence"]
                ),
                allocator=IdentityAllocator.from_dict(data["allocator"]),
                rng_state=SandboxRng.from_dict(rng_document),
                stores=stores,
                opaque_stores=opaque,
            )
        except TerraStateError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise TerraStateError(f"invalid TerraBattleState document: {exc}") from exc

    def clone(self) -> "TerraBattleState":
        return type(self).from_dict(self.to_dict())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TerraBattleState):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"TerraBattleState(revision={self.revision.identity()!r}, "
            f"replay={self._revision_sequence.replay_sequence}, "
            f"effects={self._revision_sequence.committed_effect_sequence}, "
            f"stores={len(self._stores)}, opaque={len(self._opaque)}, "
            f"rng={SANDBOX_RNG_ALGORITHM!r})"
        )
