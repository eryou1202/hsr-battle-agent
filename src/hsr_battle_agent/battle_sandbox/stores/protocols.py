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

from dataclasses import dataclass
from enum import Enum
from typing import Any, NoReturn

__all__ = [
    "ALLOCATOR_FIELD_FAMILY",
    "DERIVED_CACHE_FIELD_FAMILIES",
    "FROZEN_FIELD_FAMILIES",
    "OPAQUE_FIELD_FAMILIES",
    "OWNERSHIP_CATALOG",
    "REVISION_FIELD_FAMILY",
    "RNG_FIELD_FAMILY",
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
    """Exact field-family order from the frozen ``battle_state_contract``.

    Legacy ``state.py`` is deliberately not consulted: it is a quarantined
    compatibility surface and contains only seven implementation fields, while
    the frozen Terra contract names sixty-one authoritative families.
    """
    return tuple(spec[0] for spec in _FROZEN_OWNER_SPECS)


@dataclass(frozen=True)
class StoreOwner:
    """The single owner of one frozen state field family."""

    field_family: str
    store_class: StoreClass
    namespace: str
    authority_owner: str
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
        if not isinstance(self.authority_owner, str) or not self.authority_owner:
            raise StoreOwnershipError(
                "StoreOwner.authority_owner must be a non-empty string"
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
            "authority_owner": self.authority_owner,
            "writable": self.writable,
            "rationale": self.rationale,
        }


# Verbatim field-family/classification/owner triples from
# astra_semantic_freeze_v1.json#/battle_state_contract/state_fields.  This is
# structural authority, not a native lifecycle implementation.
_FROZEN_OWNER_SPECS: tuple[tuple[str, StoreClass, str], ...] = (
    ("schema_and_numeric_profile", StoreClass.IMMUTABLE_INPUT, "Kernel"),
    ("content_provenance", StoreClass.IMMUTABLE_INPUT, "Content"),
    ("progression_loadout_input", StoreClass.IMMUTABLE_INPUT, "Progression"),
    ("scenario_definition", StoreClass.IMMUTABLE_INPUT, "Scenario"),
    ("behavior_definitions", StoreClass.IMMUTABLE_INPUT, "Behavior"),
    ("contract_registry", StoreClass.IMMUTABLE_INPUT, "Kernel"),
    ("initial_state_spec", StoreClass.IMMUTABLE_INPUT, "Kernel"),
    ("revision_and_transaction_sequence", StoreClass.MUTABLE_STATE, "Kernel"),
    ("identity_allocators", StoreClass.MUTABLE_STATE, "Kernel"),
    ("entities", StoreClass.MUTABLE_STATE, "Entity"),
    ("teams", StoreClass.MUTABLE_STATE, "Team"),
    ("topology_relations", StoreClass.MUTABLE_STATE, "Topology"),
    ("formations", StoreClass.MUTABLE_STATE, "Formation"),
    ("survival", StoreClass.MUTABLE_STATE, "Survival"),
    ("toughness", StoreClass.MUTABLE_STATE, "Damage"),
    ("properties", StoreClass.MUTABLE_STATE, "Property"),
    ("resources", StoreClass.MUTABLE_STATE, "Resource"),
    ("skill_runtime", StoreClass.MUTABLE_STATE, "Behavior"),
    ("behavior_instances", StoreClass.MUTABLE_STATE, "Behavior"),
    ("invocation_frames", StoreClass.MUTABLE_STATE, "Invocation"),
    ("task_states", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("continuations", StoreClass.MUTABLE_STATE, "Behavior"),
    ("dynamic_value_stores", StoreClass.MUTABLE_STATE, "DynamicValue"),
    ("property_snapshots", StoreClass.MUTABLE_STATE, "Property"),
    ("modifier_instances", StoreClass.MUTABLE_STATE, "Modifier"),
    ("modifier_order", StoreClass.MUTABLE_STATE, "Modifier"),
    ("target_bindings", StoreClass.MUTABLE_STATE, "Target"),
    ("target_contexts", StoreClass.MUTABLE_STATE, "Target"),
    ("ordinary_timeline", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("behavior_action_delay", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("scheduler_owners", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("pending_insert_abilities", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("ultra_requests", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("turn_insert_actions", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("one_more_requests", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("immediate_actions", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("scheduler_phase", StoreClass.MUTABLE_STATE, "Scheduler"),
    ("ai_runtime", StoreClass.MUTABLE_STATE, "MonsterAI"),
    ("pending_damage", StoreClass.MUTABLE_STATE, "Damage"),
    ("callback_registrations", StoreClass.MUTABLE_STATE, "Event"),
    ("event_work", StoreClass.MUTABLE_STATE, "Event"),
    ("activation_state", StoreClass.MUTABLE_STATE, "Progression"),
    ("scenario_runtime", StoreClass.MUTABLE_STATE, "Scenario"),
    ("global_effects", StoreClass.MUTABLE_STATE, "Scenario"),
    ("environment_mode", StoreClass.MUTABLE_STATE, "Scenario"),
    ("terminal_state", StoreClass.MUTABLE_STATE, "Scenario"),
    ("rng_streams", StoreClass.MUTABLE_STATE, "RNG"),
    ("unresolved_dependency_index", StoreClass.MUTABLE_STATE, "Kernel"),
    ("native_wait_lifecycle", StoreClass.OPAQUE_UNRESOLVED, "Invocation"),
    ("native_modifier_lifecycle", StoreClass.OPAQUE_UNRESOLVED, "Modifier"),
    ("native_target_lifecycle", StoreClass.OPAQUE_UNRESOLVED, "Target"),
    ("native_scheduler_lifecycle", StoreClass.OPAQUE_UNRESOLVED, "Scheduler"),
    ("native_ai_lifecycle", StoreClass.OPAQUE_UNRESOLVED, "MonsterAI"),
    ("native_progression_mutation", StoreClass.OPAQUE_UNRESOLVED, "Progression"),
    ("native_scenario_persistence", StoreClass.OPAQUE_UNRESOLVED, "Scenario"),
    ("unknown_extensions", StoreClass.OPAQUE_UNRESOLVED, "Kernel"),
    ("definition_indexes", StoreClass.DERIVED_CACHE, "Content"),
    ("target_query_cache", StoreClass.DERIVED_CACHE, "Target"),
    ("candidate_visibility_cache", StoreClass.DERIVED_CACHE, "Scheduler"),
    ("property_materialization_cache", StoreClass.DERIVED_CACHE, "Property"),
    ("gate_plan_cache", StoreClass.DERIVED_CACHE, "Kernel"),
)

FROZEN_FIELD_FAMILIES: tuple[str, ...] = frozen_field_families()
REVISION_FIELD_FAMILY = "revision_and_transaction_sequence"
ALLOCATOR_FIELD_FAMILY = "identity_allocators"
RNG_FIELD_FAMILY = "rng_streams"
OPAQUE_FIELD_FAMILIES: tuple[str, ...] = tuple(
    name for name, store_class, _owner in _FROZEN_OWNER_SPECS
    if store_class is StoreClass.OPAQUE_UNRESOLVED
)
DERIVED_CACHE_FIELD_FAMILIES: tuple[str, ...] = tuple(
    name for name, store_class, _owner in _FROZEN_OWNER_SPECS
    if store_class is StoreClass.DERIVED_CACHE
)

# Exactly one owner per frozen field family. Namespaces are also unique so a
# serialized aggregate cannot alias two authoritative families.
OWNERSHIP_CATALOG: tuple[StoreOwner, ...] = tuple(
    StoreOwner(
        field_family=name,
        store_class=store_class,
        namespace=f"battle.state.{name}",
        authority_owner=authority_owner,
        writable=store_class is StoreClass.MUTABLE_STATE,
        rationale=(
            f"frozen battle_state_contract assigns {name} to "
            f"{authority_owner} as {store_class.value}"
        ),
    )
    for name, store_class, authority_owner in _FROZEN_OWNER_SPECS
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
