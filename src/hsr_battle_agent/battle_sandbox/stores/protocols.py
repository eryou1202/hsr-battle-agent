# -*- coding: utf-8 -*-
"""Store classes and the state ownership catalog.

TERRA F02-006.  This module is classification and ownership only: it defines
what kinds of store exist, and which owner holds each frozen ``BattleState``
field family.  It implements no storage behaviour.

Store classes
-------------

``IMMUTABLE_INPUT``
    Content fixed before the battle starts.  Class definitions, but also any
    fixed marker.  Never written during a transaction.
``MUTABLE_STATE``
    Live battle state that a transaction may stage and then publish.
``DERIVED_CACHE``
    A value derived from other stores.  It is rebuildable, never authoritative,
    and never the source of truth for a transaction.
``OPAQUE_UNRESOLVED``
    Material whose contents are unresolved, so it is carried losslessly and
    never interpreted.

Ownership rules
---------------

* Every frozen ``BattleState`` field family is assigned to **exactly one**
  owner; :func:`validate_catalog` rejects a duplicate assignment, an
  unclassified field family and a catalog entry that names a non-existent field
  family.
* Writing is only permitted through a class that owns the field family.
  :func:`require_writable` refuses writes to a non-writable owner.
* The generic ``extensions`` bag is **not** writable on the Terra path: it is
  carried as unresolved material so that nothing can smuggle undeclared state
  through an untyped dictionary.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any, NoReturn

from hsr_battle_agent.battle_sandbox.state import BattleState

__all__ = [
    "FROZEN_FIELD_FAMILIES",
    "OWNERSHIP_CATALOG",
    "STORE_CLASSES",
    "StoreClass",
    "StoreOwnershipError",
    "StoreOwner",
    "frozen_field_families",
    "owner_for",
    "require_writable",
    "validate_catalog",
]


class StoreOwnershipError(ValueError):
    """Raised for a malformed catalog or a write to a non-owning store."""


class StoreClass(Enum):
    """The four store classifications.

    Deliberately not a ``str`` mixin, and ``__bool__`` refuses, so a
    classification can never be used as a truthy writability shortcut; use
    :meth:`StoreOwner.is_writable` instead.
    """

    IMMUTABLE_INPUT = "IMMUTABLE_INPUT"
    MUTABLE_STATE = "MUTABLE_STATE"
    DERIVED_CACHE = "DERIVED_CACHE"
    OPAQUE_UNRESOLVED = "OPAQUE_UNRESOLVED"

    def __bool__(self) -> NoReturn:
        raise StoreOwnershipError(
            f"StoreClass.{self.name} is a classification, not a boolean; use "
            "StoreOwner.is_writable()"
        )

    def serialize(self) -> str:
        return str(self.value)

    @classmethod
    def spellings(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)


STORE_CLASSES: tuple[str, ...] = StoreClass.spellings()


def frozen_field_families() -> tuple[str, ...]:
    """The frozen ``BattleState`` field families, read from the live class.

    Read rather than hard-coded so the catalog can never silently drift away
    from the frozen state shape.
    """
    if not dataclasses.is_dataclass(BattleState):
        raise StoreOwnershipError("BattleState must be a dataclass")
    return tuple(field.name for field in dataclasses.fields(BattleState))


FROZEN_FIELD_FAMILIES: tuple[str, ...] = frozen_field_families()


@dataclass(frozen=True)
class StoreOwner:
    """The single owner of one frozen state field family."""

    field_family: str
    store_class: StoreClass
    namespace: str
    writable: bool
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.field_family, str) or not self.field_family:
            raise StoreOwnershipError(
                "StoreOwner.field_family must be a non-empty string"
            )
        if not isinstance(self.store_class, StoreClass):
            if not isinstance(self.store_class, str):
                raise StoreOwnershipError(
                    "StoreOwner.store_class must be a StoreClass or its spelling"
                )
            try:
                object.__setattr__(
                    self, "store_class", StoreClass(self.store_class)
                )
            except ValueError:
                raise StoreOwnershipError(
                    f"unknown store class {self.store_class!r}; expected one of "
                    f"{STORE_CLASSES}"
                ) from None
        if not isinstance(self.namespace, str) or not self.namespace:
            raise StoreOwnershipError(
                "StoreOwner.namespace must be a non-empty string"
            )
        if not isinstance(self.writable, bool):
            raise StoreOwnershipError("StoreOwner.writable must be a bool")
        if not isinstance(self.rationale, str) or not self.rationale:
            raise StoreOwnershipError(
                "StoreOwner.rationale must be a non-empty string"
            )
        if self.writable and self.store_class is not StoreClass.MUTABLE_STATE:
            raise StoreOwnershipError(
                f"{self.field_family!r} is writable but is classified "
                f"{self.store_class.value}; only MUTABLE_STATE may be writable"
            )

    def is_writable(self) -> bool:
        return self.writable is True

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_family": self.field_family,
            "store_class": self.store_class.value,
            "namespace": self.namespace,
            "writable": self.writable,
            "rationale": self.rationale,
        }


#: The ownership catalog.  Exactly one entry per frozen field family.
OWNERSHIP_CATALOG: tuple[StoreOwner, ...] = (
    StoreOwner(
        field_family="schema_version",
        store_class=StoreClass.IMMUTABLE_INPUT,
        namespace="battle.state.schema",
        writable=False,
        rationale=(
            "the schema marker is fixed for the life of the state and is never "
            "written during a transaction"
        ),
    ),
    StoreOwner(
        field_family="extensions",
        store_class=StoreClass.OPAQUE_UNRESOLVED,
        namespace="battle.state.extensions",
        writable=False,
        rationale=(
            "a generic extension bag carries material whose contents are "
            "unresolved; it is preserved losslessly and must never accept "
            "generic writes on the Terra path"
        ),
    ),
    StoreOwner(
        field_family="modifier_state_by_entity",
        store_class=StoreClass.MUTABLE_STATE,
        namespace="battle.modifier",
        writable=True,
        rationale="live modifier instances per entity are mutated by a transaction",
    ),
    StoreOwner(
        field_family="entity_property_entries",
        store_class=StoreClass.MUTABLE_STATE,
        namespace="battle.property",
        writable=True,
        rationale="live property entries per entity are mutated by a transaction",
    ),
    StoreOwner(
        field_family="modifier_property_contributions",
        store_class=StoreClass.MUTABLE_STATE,
        namespace="battle.property.contribution",
        writable=True,
        rationale="modifier contributions are staged and published with the state",
    ),
    StoreOwner(
        field_family="component_lock_hp_records",
        store_class=StoreClass.MUTABLE_STATE,
        namespace="battle.component.lock_hp",
        writable=True,
        rationale="component lock records change as the battle progresses",
    ),
    StoreOwner(
        field_family="turn_timeline",
        store_class=StoreClass.MUTABLE_STATE,
        namespace="battle.scheduler",
        writable=True,
        rationale="the turn timeline advances as turns are consumed",
    ),
)


def validate_catalog(
    catalog: tuple[StoreOwner, ...] = OWNERSHIP_CATALOG,
    frozen: tuple[str, ...] = FROZEN_FIELD_FAMILIES,
) -> None:
    """Raise unless the catalog assigns every frozen family exactly once."""
    if not isinstance(catalog, (tuple, list)):
        raise StoreOwnershipError("catalog must be a tuple or list of StoreOwner")
    seen: dict[str, StoreOwner] = {}
    for owner in catalog:
        if not isinstance(owner, StoreOwner):
            raise StoreOwnershipError(
                f"catalog entries must be StoreOwner instances, got "
                f"{type(owner).__name__}"
            )
        if owner.field_family in seen:
            raise StoreOwnershipError(
                f"duplicate owner for field family {owner.field_family!r}: "
                f"{seen[owner.field_family].namespace!r} and {owner.namespace!r}"
            )
        seen[owner.field_family] = owner
    missing = [name for name in frozen if name not in seen]
    if missing:
        raise StoreOwnershipError(
            f"unclassified field families: {missing}"
        )
    extra = [name for name in seen if name not in frozen]
    if extra:
        raise StoreOwnershipError(
            f"catalog names field families that are not frozen state fields: "
            f"{extra}"
        )


def owner_for(field_family: str) -> StoreOwner:
    """The single owner of a field family, or raise."""
    if not isinstance(field_family, str) or not field_family:
        raise StoreOwnershipError(
            "field_family must be a non-empty string"
        )
    for owner in OWNERSHIP_CATALOG:
        if owner.field_family == field_family:
            return owner
    raise StoreOwnershipError(
        f"field family {field_family!r} has no owner; every state field family "
        "must be classified"
    )


def require_writable(field_family: str) -> StoreOwner:
    """The owner of a field family when it accepts writes, else raise."""
    owner = owner_for(field_family)
    if not owner.is_writable():
        raise StoreOwnershipError(
            f"field family {field_family!r} is owned by "
            f"{owner.store_class.value} and is not writable on the Terra path; "
            "generic extension writes are forbidden"
        )
    return owner


# Validate at import time so an inconsistent catalog can never load.
validate_catalog()
