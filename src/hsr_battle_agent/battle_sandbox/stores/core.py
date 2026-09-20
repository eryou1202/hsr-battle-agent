# -*- coding: utf-8 -*-
"""Typed empty stores for the Terra state families.

TERRA F02-007.  This module implements the *containers* only: an ordered,
duplicate-preserving, presence-preserving store per state family, starting
empty.  It implements **no lifecycle behaviour** — no creation rules, no
destruction rules, no ordering semantics beyond insertion order, and no
transition logic.  Those belong to later tasks.

Family names are taken from families the repository already records (the frozen
``BattleState`` fields and the recorded scheduler packet families), so no new
semantic family is invented here.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.lossless_value import (
    LosslessValueError,
    PresenceValue,
    PresenceValueError,
)
from hsr_battle_agent.battle_sandbox.stores.protocols import (
    StoreClass,
    StoreOwnershipError,
)

__all__ = [
    "CORE_STORE_SCHEMA",
    "STORE_FAMILIES",
    "STORE_FAMILY_NAMES",
    "StoreDefinition",
    "StoreEntry",
    "TypedStore",
    "TypedStoreError",
    "empty_stores",
    "require_store_family",
    "scheduler_store_family_names",
]


class TypedStoreError(ValueError):
    """Raised for a malformed store or an illegal store operation."""


CORE_STORE_SCHEMA = "typed_store/1"


@dataclass(frozen=True)
class StoreDefinition:
    """The declared definition of one store family."""

    name: str
    namespace: str
    store_class: StoreClass
    #: Which frozen state field family this store belongs to, when it maps to one.
    state_field_family: str | None = None
    rationale: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("name", self.name),
            ("namespace", self.namespace),
            ("rationale", self.rationale),
        ):
            if not isinstance(value, str) or not value:
                raise TypedStoreError(f"StoreDefinition.{label} must be non-empty")
        if not isinstance(self.store_class, StoreClass):
            try:
                object.__setattr__(
                    self, "store_class", StoreClass(self.store_class)
                )
            except (ValueError, TypeError):
                raise TypedStoreError(
                    f"unknown store class {self.store_class!r}"
                ) from None
        if self.state_field_family is not None:
            if not isinstance(self.state_field_family, str) or not self.state_field_family:
                raise TypedStoreError(
                    "StoreDefinition.state_field_family must be a non-empty "
                    "string or absent"
                )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "namespace": self.namespace,
            "store_class": self.store_class.value,
        }
        if self.state_field_family is not None:
            payload["state_field_family"] = self.state_field_family
        payload["rationale"] = self.rationale
        return payload


#: Every store family.  The scheduler is deliberately split into separate
#: stores rather than one blob; the three scheduler families below correspond to
#: the recorded scheduler packet families (timeline composition, action-delay
#: add/set/reset, and ability-queue insertion).
STORE_FAMILIES: tuple[StoreDefinition, ...] = (
    StoreDefinition(
        name="definitions",
        namespace="battle.definition",
        store_class=StoreClass.IMMUTABLE_INPUT,
        state_field_family="schema_version",
        rationale="fixed content definitions; immutable during a transaction",
    ),
    StoreDefinition(
        name="entities",
        namespace="battle.entity",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live entities",
    ),
    StoreDefinition(
        name="teams",
        namespace="battle.team",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live teams",
    ),
    StoreDefinition(
        name="topology",
        namespace="battle.topology",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live formation/topology nodes",
    ),
    StoreDefinition(
        name="invocation",
        namespace="battle.invocation",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live ability invocation state",
    ),
    StoreDefinition(
        name="modifiers",
        namespace="battle.modifier",
        store_class=StoreClass.MUTABLE_STATE,
        state_field_family="modifier_state_by_entity",
        rationale="live modifier instances",
    ),
    StoreDefinition(
        name="properties",
        namespace="battle.property",
        store_class=StoreClass.MUTABLE_STATE,
        state_field_family="entity_property_entries",
        rationale="live property entries",
    ),
    StoreDefinition(
        name="property_contributions",
        namespace="battle.property.contribution",
        store_class=StoreClass.MUTABLE_STATE,
        state_field_family="modifier_property_contributions",
        rationale="live modifier property contributions",
    ),
    StoreDefinition(
        name="component_locks",
        namespace="battle.component.lock_hp",
        store_class=StoreClass.MUTABLE_STATE,
        state_field_family="component_lock_hp_records",
        rationale="live component lock records",
    ),
    StoreDefinition(
        name="targets",
        namespace="battle.target",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live target/selection state",
    ),
    StoreDefinition(
        name="scheduler_timeline",
        namespace="battle.scheduler.timeline",
        store_class=StoreClass.MUTABLE_STATE,
        state_field_family="turn_timeline",
        rationale="live turn timeline",
    ),
    StoreDefinition(
        name="scheduler_action_delay",
        namespace="battle.scheduler.action_delay",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live action-delay state kept separate from the timeline",
    ),
    StoreDefinition(
        name="scheduler_insert_queue",
        namespace="battle.scheduler.insert_queue",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live ability-queue insertion records, separate from both above",
    ),
    StoreDefinition(
        name="ai",
        namespace="battle.ai",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live AI decision state",
    ),
    StoreDefinition(
        name="damage",
        namespace="battle.damage",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live damage records",
    ),
    StoreDefinition(
        name="resources",
        namespace="battle.resource",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live shared resources such as skill points",
    ),
    StoreDefinition(
        name="events",
        namespace="battle.event",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live event records",
    ),
    StoreDefinition(
        name="scenario",
        namespace="battle.scenario",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live scenario state",
    ),
    StoreDefinition(
        name="mode",
        namespace="battle.mode",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live environment/mode state",
    ),
    StoreDefinition(
        name="terminal",
        namespace="battle.terminal",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="live terminal-condition state",
    ),
    StoreDefinition(
        name="allocator",
        namespace="battle.allocator",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="identity allocation state",
    ),
    StoreDefinition(
        name="rng",
        namespace="battle.rng",
        store_class=StoreClass.MUTABLE_STATE,
        rationale="state-owned RNG; transaction-private until atomic commit",
    ),
    StoreDefinition(
        name="opaque_handles",
        namespace="battle.opaque",
        store_class=StoreClass.OPAQUE_UNRESOLVED,
        state_field_family="extensions",
        rationale="unresolved material carried losslessly and never interpreted",
    ),
)

STORE_FAMILY_NAMES: tuple[str, ...] = tuple(
    definition.name for definition in STORE_FAMILIES
)


def require_store_family(name: Any) -> StoreDefinition:
    """The declared definition of a store family, or raise."""
    if not isinstance(name, str) or not name:
        raise TypedStoreError("store family name must be a non-empty string")
    for definition in STORE_FAMILIES:
        if definition.name == name:
            return definition
    raise TypedStoreError(
        f"unknown store family {name!r}; expected one of {STORE_FAMILY_NAMES}"
    )


def scheduler_store_family_names() -> tuple[str, ...]:
    """The separate scheduler store families."""
    return tuple(
        definition.name
        for definition in STORE_FAMILIES
        if definition.namespace.startswith("battle.scheduler.")
    )


@dataclass(frozen=True)
class StoreEntry:
    """One entry in a store.

    The value is a :class:`PresenceValue`, so a null, a false, a zero, an empty
    list and an absent value all stay distinguishable.  ``occurrence`` numbers
    duplicate keys so an ordered store can hold the same key more than once.
    """

    key: str
    value: PresenceValue
    occurrence: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key:
            raise TypedStoreError("StoreEntry.key must be a non-empty string")
        if not isinstance(self.value, PresenceValue):
            raise TypedStoreError(
                "StoreEntry.value must be a PresenceValue, so that absence and "
                "null stay distinguishable"
            )
        if isinstance(self.occurrence, bool) or not isinstance(self.occurrence, int):
            raise TypedStoreError("StoreEntry.occurrence must be an int")
        if self.occurrence < 0:
            raise TypedStoreError("StoreEntry.occurrence must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "occurrence": self.occurrence,
            "value": self.value.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StoreEntry":
        if not isinstance(data, Mapping):
            raise TypedStoreError("StoreEntry document must be a mapping")
        for name in ("key", "value"):
            if name not in data:
                raise TypedStoreError(
                    f"StoreEntry document is missing required field {name!r}"
                )
        try:
            value = PresenceValue.from_dict(data["value"])
        except PresenceValueError as exc:
            raise TypedStoreError(f"invalid presence value: {exc}") from exc
        return cls(
            key=data["key"],
            value=value,
            occurrence=data["occurrence"] if "occurrence" in data else 0,
        )


@dataclass(frozen=True)
class TypedStore:
    """An ordered, duplicate-preserving store for one family.

    Starts empty and grows only through :meth:`append`, which returns a new
    store.  Insertion order is preserved, duplicate keys are preserved as
    separate entries, and nothing is deduplicated or reordered.
    """

    definition: StoreDefinition
    entries: tuple[StoreEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.definition, StoreDefinition):
            raise TypedStoreError("TypedStore.definition must be a StoreDefinition")
        if isinstance(self.entries, (str, bytes)) or not isinstance(
            self.entries, (tuple, list)
        ):
            raise TypedStoreError("TypedStore.entries must be a tuple or list")
        for entry in self.entries:
            if not isinstance(entry, StoreEntry):
                raise TypedStoreError(
                    f"entries must be StoreEntry instances, got "
                    f"{type(entry).__name__}"
                )
        object.__setattr__(self, "entries", tuple(self.entries))

    # -- declarative surface ---------------------------------------------

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def namespace(self) -> str:
        return self.definition.namespace

    @property
    def store_class(self) -> StoreClass:
        return self.definition.store_class

    def is_empty(self) -> bool:
        return len(self.entries) == 0

    def is_writable(self) -> bool:
        """True only for a mutable-state store.

        An immutable-input store is fixed, and an opaque-unresolved store must
        never accept a *generic* write: it is populated only through its own
        dedicated construction path so that unresolved material is explicitly
        labelled rather than smuggled in through a dictionary.
        """
        return self.store_class is StoreClass.MUTABLE_STATE

    def __len__(self) -> int:
        return len(self.entries)

    # -- mutation by replacement -----------------------------------------

    def append(
        self, key: str, value: PresenceValue | Any, *, occurrence: int | None = None
    ) -> "TypedStore":
        """Return a new store with one entry appended.  No lifecycle logic."""
        if not self.is_writable():
            raise TypedStoreError(
                f"store family {self.name!r} is {self.store_class.value} and "
                "does not accept writes"
            )
        presence = (
            value
            if isinstance(value, PresenceValue)
            else PresenceValue.present(value)
        )
        if occurrence is None:
            occurrence = sum(1 for entry in self.entries if entry.key == key)
        return TypedStore(
            definition=self.definition,
            entries=self.entries
            + (StoreEntry(key=key, value=presence, occurrence=occurrence),),
        )

    def extend(self, entries: Any) -> "TypedStore":
        """Return a new store with several entries appended in order."""
        if isinstance(entries, (str, bytes)) or not isinstance(
            entries, (tuple, list)
        ):
            raise TypedStoreError("extend() requires a tuple or list of entries")
        store = self
        for entry in entries:
            if isinstance(entry, StoreEntry):
                store = store.append(entry.key, entry.value, occurrence=entry.occurrence)
            elif isinstance(entry, (tuple, list)) and len(entry) == 2:
                store = store.append(entry[0], entry[1])
            else:
                raise TypedStoreError(
                    f"cannot extend with {type(entry).__name__}; expected "
                    "StoreEntry or (key, value)"
                )
        return store

    def keys(self) -> tuple[str, ...]:
        """Keys in insertion order, duplicates included."""
        return tuple(entry.key for entry in self.entries)

    def values_for(self, key: str) -> tuple[PresenceValue, ...]:
        """Every value recorded for a key, in insertion order."""
        return tuple(entry.value for entry in self.entries if entry.key == key)

    # -- identity and serialization --------------------------------------

    def identity(self) -> str:
        """Stable digest over the family and its ordered contents."""
        text = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CORE_STORE_SCHEMA,
            "definition": self.definition.to_dict(),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TypedStore":
        if not isinstance(data, Mapping):
            raise TypedStoreError(
                f"store document must be a mapping, got {type(data).__name__}"
            )
        schema = data["schema"] if "schema" in data else CORE_STORE_SCHEMA
        if schema != CORE_STORE_SCHEMA:
            raise TypedStoreError(
                f"unknown store schema {schema!r}; expected {CORE_STORE_SCHEMA!r}"
            )
        if "definition" not in data:
            raise TypedStoreError("store document is missing its definition")
        raw = data["entries"] if "entries" in data else []
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
            raise TypedStoreError("store entries must be a list")
        definition_data = data["definition"]
        if not isinstance(definition_data, Mapping):
            raise TypedStoreError("store definition must be a mapping")
        definition = StoreDefinition(
            name=definition_data["name"],
            namespace=definition_data["namespace"],
            store_class=definition_data["store_class"],
            state_field_family=(
                definition_data["state_field_family"]
                if "state_field_family" in definition_data
                else None
            ),
            rationale=definition_data["rationale"]
            if "rationale" in definition_data
            else "restored",
        )
        return cls(
            definition=definition,
            entries=tuple(StoreEntry.from_dict(item) for item in raw),
        )

    def empty_copy(self) -> "TypedStore":
        """This family's store with no entries."""
        return TypedStore(definition=self.definition)


def empty_stores() -> dict[str, TypedStore]:
    """A fresh, empty store for every declared family, in declaration order."""
    return {
        definition.name: TypedStore(definition=definition)
        for definition in STORE_FAMILIES
    }
