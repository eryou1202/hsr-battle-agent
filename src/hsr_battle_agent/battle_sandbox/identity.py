# -*- coding: utf-8 -*-
"""Typed identity base for the Terra local state path.

TERRA F02-001.  This module is local typed-state infrastructure.  It creates
**family-tagged, immutable** identity values and records, for every identity, the
five facts the F02 contract requires:

``family``
    which identity family the value belongs to (a declared family tag);
``namespace``
    the namespace the identity is scoped to;
``generation``
    the generation counter the identity was minted in;
``value``
    the identity value, held exactly;
``authority``
    where the identity's authority comes from.

Hard rules enforced here
------------------------

* **No cross-family equality.**  Two identities from different families are
  never equal, even when their namespace, generation and value are identical.
  Family distinctions are preserved; no alias is invented because two values
  happen to match.
* **Never float-normalize an identifier.**  A float is refused outright, and an
  integer value is held as an exact Python ``int``, so values above 2**53 survive
  exactly.
* **No implicit int coercion.**  A string identity stays a string; an integer
  identity stays an integer.  Nothing is parsed into the other.
* **``LOCAL_DESIGN_IDENTITY`` is explicit.**  It is a declared authority, not a
  default, and it is never presented as native client identity.
  ``NATIVE_CLIENT_IDENTITY`` cannot be asserted by this local infrastructure at
  all: :meth:`TypedIdentity.certify_native_identity` refuses, so local runtime
  identity can never be passed off as a native client identity.
* **Family conversion is explicit and named.**  :meth:`TypedIdentity.convert_family`
  requires a non-empty named contract; nothing converts implicitly.

Families are *declared*, never inferred.  F02-002 and F02-003 add the domain
families additively as module-level constants; their behaviour is unchanged by
this module and this module's behaviour is unchanged by them.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, NoReturn

__all__ = [
    "ACTOR",
    "AllocationTicket",
    "CASTER",
    "DAMAGE_COMPONENT",
    "DAMAGE_HIT",
    "DAMAGE_ROOT",
    "ENTITY",
    "EQUIPMENT_INSTANCE",
    "FAMILY_A",
    "FAMILY_A_NAMES",
    "FAMILY_B",
    "FAMILY_B_NAMES",
    "FORMATION_SLOT",
    "GLOBAL_SERVICE",
    "IDENTITY_SCHEMA",
    "IDENTITY_ALLOCATOR_SCHEMA",
    "IdentityAllocator",
    "IdentityAuthority",
    "IdentityFamily",
    "MODIFIER",
    "NamespaceState",
    "OWNER",
    "PROVIDER",
    "RECEIVER",
    "ROLE_FAMILIES",
    "RoleBundle",
    "SourcedIdentity",
    "TARGET_CONTEXT",
    "TASK",
    "TEAM",
    "TOPOLOGY_NODE",
    "TypedIdentity",
    "TypedIdentityError",
    "declare_identity_family",
    "declared_identity_families",
    "require_declared_family",
    "require_family_a",
    "require_family_b",
]

IDENTITY_SCHEMA = "typed_identity/1"
IDENTITY_ALLOCATOR_SCHEMA = "identity_allocator/1"

_MACHINE_CODE_RE = re.compile(r"\A[A-Z][A-Z0-9_]*\Z")


class TypedIdentityError(ValueError):
    """Raised for a malformed identity or an illegal identity operation."""


class IdentityAuthority(Enum):
    """Where an identity's authority comes from.

    Deliberately not a ``str`` mixin, and ``__bool__`` refuses, so an authority
    can never be used as a truthy native-evidence shortcut.

    ``LOCAL_DESIGN_IDENTITY``
        An identity designed locally by this project.  It carries no native
        client claim whatsoever.
    ``SOURCE_RECORDED_IDENTITY``
        An identity copied verbatim from a source document, retaining that
        document's provenance.
    ``NATIVE_CLIENT_IDENTITY``
        A native client identity.  No local infrastructure may assert this:
        see :meth:`TypedIdentity.certify_native_identity`.
    """

    LOCAL_DESIGN_IDENTITY = "LOCAL_DESIGN_IDENTITY"
    SOURCE_RECORDED_IDENTITY = "SOURCE_RECORDED_IDENTITY"
    NATIVE_CLIENT_IDENTITY = "NATIVE_CLIENT_IDENTITY"

    def __bool__(self) -> NoReturn:
        raise TypedIdentityError(
            f"IdentityAuthority.{self.name} is a classification, not a boolean; "
            "compare it with is"
        )

    def serialize(self) -> str:
        return str(self.value)

    @classmethod
    def spellings(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)


def _parse_authority(value: Any) -> IdentityAuthority:
    if isinstance(value, IdentityAuthority):
        return value
    if value is None or not isinstance(value, str):
        raise TypedIdentityError(
            f"identity authority must be a serialized string, got "
            f"{type(value).__name__}"
        )
    try:
        return IdentityAuthority(value)
    except ValueError:
        raise TypedIdentityError(
            f"unknown identity authority {value!r}; expected one of "
            f"{IdentityAuthority.spellings()}"
        ) from None


# ---------------------------------------------------------------------------
# Family declaration registry
# ---------------------------------------------------------------------------
#
# Families are declared explicitly and never inferred.  The registry is a
# declaration-time structure only: it is append-only, idempotent and
# deterministic, and it holds no identity state.

_DECLARED_FAMILIES: dict[str, "IdentityFamily"] = {}


@dataclass(frozen=True)
class IdentityFamily:
    """A declared identity family tag.

    The tag is an uppercase machine code.  Two tags with the same name are the
    same family; two tags with different names are different families and can
    never be equal or interchangeable.
    """

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise TypedIdentityError(
                "IdentityFamily.name must be a non-empty string"
            )
        if not _MACHINE_CODE_RE.match(self.name):
            raise TypedIdentityError(
                f"{self.name!r} is not a valid family tag; expected an uppercase "
                "machine code such as ENTITY"
            )

    def is_declared(self) -> bool:
        return _DECLARED_FAMILIES.get(self.name) is self

    def serialize(self) -> str:
        return self.name

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IdentityFamily":
        if not isinstance(data, Mapping):
            raise TypedIdentityError(
                "IdentityFamily document must be a mapping"
            )
        if "name" not in data:
            raise TypedIdentityError(
                "IdentityFamily document is missing the 'name' key"
            )
        return require_declared_family(data["name"])


def declare_identity_family(name: str) -> IdentityFamily:
    """Declare a family tag, idempotently, and return the canonical instance.

    Declaring is the only way to create a usable family, so a family can never
    appear by accident.  F02-002 and F02-003 call this at import time for the
    domain families.
    """
    if not isinstance(name, str) or not name:
        raise TypedIdentityError(
            "declare_identity_family requires a non-empty string tag"
        )
    if not _MACHINE_CODE_RE.match(name):
        raise TypedIdentityError(
            f"{name!r} is not a valid family tag; expected an uppercase machine "
            "code such as ENTITY"
        )
    existing = _DECLARED_FAMILIES.get(name)
    if existing is not None:
        return existing
    family = IdentityFamily(name=name)
    _DECLARED_FAMILIES[name] = family
    return family


def declared_identity_families() -> tuple[IdentityFamily, ...]:
    """The declared families, in declaration order."""
    return tuple(_DECLARED_FAMILIES.values())


def require_declared_family(value: Any) -> IdentityFamily:
    """Return the declared family for ``value``, or raise.

    Accepts an :class:`IdentityFamily` or its serialized tag.  An undeclared tag
    is refused rather than silently created.
    """
    if isinstance(value, IdentityFamily):
        family = _DECLARED_FAMILIES.get(value.name)
        if family is None or family is not value:
            raise TypedIdentityError(
                f"identity family {value.name!r} is not the declared instance; "
                "use declare_identity_family()"
            )
        return family
    if not isinstance(value, str) or not value:
        raise TypedIdentityError(
            "identity family must be a declared family or its serialized tag"
        )
    family = _DECLARED_FAMILIES.get(value)
    if family is None:
        raise TypedIdentityError(
            f"identity family {value!r} has not been declared; families are "
            "declared explicitly and never inferred"
        )
    return family


# ---------------------------------------------------------------------------
# Typed identity
# ---------------------------------------------------------------------------


def _validate_value(value: Any) -> int | str:
    """Validate an identity value, refusing float normalization and coercion."""
    if isinstance(value, bool):
        raise TypedIdentityError(
            "an identity value must be an int or a string; a bool is not an "
            "identity value"
        )
    if isinstance(value, float):
        raise TypedIdentityError(
            f"refusing the float {value!r} as an identity value: float "
            "normalization loses exactness above 2**53"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if not value:
            raise TypedIdentityError(
                "a string identity value must be non-empty"
            )
        return value
    raise TypedIdentityError(
        f"an identity value must be an int or a string, got "
        f"{type(value).__name__}"
    )


def _validate_generation(generation: Any) -> int:
    if isinstance(generation, bool) or not isinstance(generation, int):
        raise TypedIdentityError(
            f"generation must be an int, got {type(generation).__name__}"
        )
    if generation < 0:
        raise TypedIdentityError("generation must be >= 0")
    return generation


@dataclass(frozen=True)
class TypedIdentity:
    """An immutable, family-tagged identity value.

    Equality includes the family, so two identities from different families are
    never equal even when every other field matches.
    """

    family: IdentityFamily
    namespace: str
    generation: int
    value: int | str
    authority: IdentityAuthority

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "family", require_declared_family(self.family)
        )
        if not isinstance(self.namespace, str) or not self.namespace:
            raise TypedIdentityError("namespace must be a non-empty string")
        object.__setattr__(
            self, "generation", _validate_generation(self.generation)
        )
        object.__setattr__(self, "value", _validate_value(self.value))
        authority = _parse_authority(self.authority)
        if authority is IdentityAuthority.NATIVE_CLIENT_IDENTITY:
            raise TypedIdentityError(
                "NATIVE_CLIENT_IDENTITY cannot be asserted by the local identity "
                "path; no local runtime identity may be presented as native "
                "client identity"
            )
        object.__setattr__(self, "authority", authority)

    # -- constructors ----------------------------------------------------

    @classmethod
    def local(
        cls,
        family: Any,
        namespace: str,
        value: int | str,
        *,
        generation: int = 0,
    ) -> "TypedIdentity":
        """Mint a locally designed identity (``LOCAL_DESIGN_IDENTITY``)."""
        return cls(
            family=family,
            namespace=namespace,
            generation=generation,
            value=value,
            authority=IdentityAuthority.LOCAL_DESIGN_IDENTITY,
        )

    @classmethod
    def from_source_record(
        cls,
        family: Any,
        namespace: str,
        value: int | str,
        *,
        generation: int = 0,
    ) -> "TypedIdentity":
        """Wrap an identity recorded verbatim from a source document."""
        return cls(
            family=family,
            namespace=namespace,
            generation=generation,
            value=value,
            authority=IdentityAuthority.SOURCE_RECORDED_IDENTITY,
        )

    # -- queries ---------------------------------------------------------

    def is_local_design(self) -> bool:
        return self.authority is IdentityAuthority.LOCAL_DESIGN_IDENTITY

    def is_source_recorded(self) -> bool:
        return self.authority is IdentityAuthority.SOURCE_RECORDED_IDENTITY

    def same_family(self, other: Any) -> bool:
        return (
            isinstance(other, TypedIdentity)
            and self.family.name == other.family.name
        )

    def value_is_int(self) -> bool:
        return isinstance(self.value, int) and not isinstance(self.value, bool)

    def value_is_str(self) -> bool:
        return isinstance(self.value, str)

    def require_int_value(self) -> int:
        """Exact integer identity, or raise.  Never coerces and never floats."""
        if not self.value_is_int():
            raise TypedIdentityError(
                f"identity value {self.value!r} is not an integer; refusing to "
                "coerce it"
            )
        assert isinstance(self.value, int)
        return self.value

    def __bool__(self) -> NoReturn:
        raise TypedIdentityError(
            "TypedIdentity has no truthiness; compare it explicitly"
        )

    # -- explicit, named conversions --------------------------------------

    def convert_family(self, family: Any, *, contract: str) -> "TypedIdentity":
        """Convert to another family under an explicit named contract.

        No conversion is implicit and no alias is created: the caller must name
        the contract that justifies treating the value as another family.
        """
        if not isinstance(contract, str) or not contract:
            raise TypedIdentityError(
                "convert_family requires a non-empty named contract; family "
                "conversion is never implicit"
            )
        target = require_declared_family(family)
        if target.name == self.family.name:
            raise TypedIdentityError(
                f"convert_family to the same family {target.name!r} is a no-op; "
                "family conversions must change the family"
            )
        return TypedIdentity(
            family=target,
            namespace=self.namespace,
            generation=self.generation,
            value=self.value,
            authority=self.authority,
        )

    def advance_generation(self, *, contract: str) -> "TypedIdentity":
        """Advance the generation under an explicit named contract."""
        if not isinstance(contract, str) or not contract:
            raise TypedIdentityError(
                "advance_generation requires a non-empty named contract"
            )
        return TypedIdentity(
            family=self.family,
            namespace=self.namespace,
            generation=self.generation + 1,
            value=self.value,
            authority=self.authority,
        )

    def certify_native_identity(self) -> NoReturn:
        """Refuse: local identity is never native client identity."""
        raise TypedIdentityError(
            f"identity {self.family.name}:{self.namespace}:{self.value!r} carries "
            f"{self.authority.value}; it cannot be certified as native client "
            "identity by local infrastructure"
        )

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": IDENTITY_SCHEMA,
            "family": self.family.serialize(),
            "namespace": self.namespace,
            "generation": self.generation,
            "value": copy.deepcopy(self.value),
            "authority": self.authority.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TypedIdentity":
        if not isinstance(data, Mapping):
            raise TypedIdentityError(
                f"identity document must be a mapping, got {type(data).__name__}"
            )
        schema = data["schema"] if "schema" in data else IDENTITY_SCHEMA
        if schema != IDENTITY_SCHEMA:
            raise TypedIdentityError(
                f"unknown identity schema {schema!r}; expected {IDENTITY_SCHEMA!r}"
            )
        for name in ("family", "namespace", "generation", "value", "authority"):
            if name not in data:
                raise TypedIdentityError(
                    f"identity document is missing required field {name!r}"
                )
        return cls(
            family=require_declared_family(data["family"]),
            namespace=data["namespace"],
            generation=data["generation"],
            value=copy.deepcopy(data["value"]),
            authority=data["authority"],
        )


# ---------------------------------------------------------------------------
# Family A: entity / actor / team / formation / topology (F02-002)
# ---------------------------------------------------------------------------
#
# These five families are declared, not inferred.  They are deliberately
# separate tags: a matching value never makes two of them interchangeable, and
# no alias between them exists.

ENTITY = declare_identity_family("ENTITY")
ACTOR = declare_identity_family("ACTOR")
TEAM = declare_identity_family("TEAM")
FORMATION_SLOT = declare_identity_family("FORMATION_SLOT")
TOPOLOGY_NODE = declare_identity_family("TOPOLOGY_NODE")

FAMILY_A: tuple[IdentityFamily, ...] = (
    ENTITY,
    ACTOR,
    TEAM,
    FORMATION_SLOT,
    TOPOLOGY_NODE,
)

FAMILY_A_NAMES: tuple[str, ...] = tuple(family.name for family in FAMILY_A)

_SOURCE_IDENTITY_SCHEMA = "sourced_identity/1"


def require_family_a(value: Any) -> IdentityFamily:
    """Return a family from the F02-002 set, or raise."""
    family = require_declared_family(value)
    if family.name not in FAMILY_A_NAMES:
        raise TypedIdentityError(
            f"{family.name!r} is not one of the F02-002 families "
            f"{FAMILY_A_NAMES}"
        )
    return family


@dataclass(frozen=True)
class SourcedIdentity:
    """A runtime identity with its source identity preserved separately.

    Source identity and runtime identity are **different things** and are kept
    in different fields on purpose.  They are never merged, never compared as
    equal and never substituted for one another: identical values across the two
    still mean two different facts, and one may be absent while the other is
    present.

    ``runtime`` always carries ``LOCAL_DESIGN_IDENTITY`` authority; a ``source``
    identity, when present, always carries ``SOURCE_RECORDED_IDENTITY``.
    """

    runtime: TypedIdentity
    source: TypedIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, TypedIdentity):
            raise TypedIdentityError(
                "SourcedIdentity.runtime must be a TypedIdentity"
            )
        if self.runtime.authority is not IdentityAuthority.LOCAL_DESIGN_IDENTITY:
            raise TypedIdentityError(
                "SourcedIdentity.runtime must carry LOCAL_DESIGN_IDENTITY; the "
                "runtime identity is local design, not source or native identity"
            )
        if self.source is not None:
            if not isinstance(self.source, TypedIdentity):
                raise TypedIdentityError(
                    "SourcedIdentity.source must be a TypedIdentity or absent"
                )
            if (
                self.source.authority
                is not IdentityAuthority.SOURCE_RECORDED_IDENTITY
            ):
                raise TypedIdentityError(
                    "SourcedIdentity.source must carry SOURCE_RECORDED_IDENTITY"
                )

    def has_source(self) -> bool:
        return self.source is not None

    def require_source(self) -> TypedIdentity:
        """Return the source identity, or raise.  Never falls back to runtime."""
        if self.source is None:
            raise TypedIdentityError(
                "this identity has no recorded source identity; the runtime "
                "identity is not a substitute for it"
            )
        return self.source

    def assume_source_equals_runtime(self) -> NoReturn:
        """Refuse: source identity is never assumed equal to runtime identity."""
        raise TypedIdentityError(
            "source identity must not be assumed equal to runtime identity; "
            f"runtime {self.runtime.family.name}:{self.runtime.value!r} and "
            "source identity are separate facts"
        )

    def same_family(self) -> bool:
        """True only when both are present and their families match exactly."""
        if self.source is None:
            return False
        return self.runtime.family.name == self.source.family.name

    def __bool__(self) -> NoReturn:
        raise TypedIdentityError(
            "SourcedIdentity has no truthiness; use has_source()"
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": _SOURCE_IDENTITY_SCHEMA,
            "runtime": self.runtime.to_dict(),
        }
        if self.source is not None:
            payload["source"] = self.source.to_dict()
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourcedIdentity":
        if not isinstance(data, Mapping):
            raise TypedIdentityError(
                f"sourced identity document must be a mapping, got "
                f"{type(data).__name__}"
            )
        schema = (
            data["schema"] if "schema" in data else _SOURCE_IDENTITY_SCHEMA
        )
        if schema != _SOURCE_IDENTITY_SCHEMA:
            raise TypedIdentityError(
                f"unknown sourced identity schema {schema!r}; expected "
                f"{_SOURCE_IDENTITY_SCHEMA!r}"
            )
        if "runtime" not in data:
            raise TypedIdentityError(
                "sourced identity document is missing the 'runtime' identity"
            )
        source = None
        if "source" in data and data["source"] is not None:
            source = TypedIdentity.from_dict(data["source"])
        return cls(
            runtime=TypedIdentity.from_dict(data["runtime"]), source=source
        )


# ---------------------------------------------------------------------------
# Family B: roles, context, services and damage families (F02-003)
# ---------------------------------------------------------------------------
#
# Every one of these is a separate declared family.  In particular provider and
# caster are different families: a matching value never makes them the same, and
# there is no shortcut between any pair.

OWNER = declare_identity_family("OWNER")
CASTER = declare_identity_family("CASTER")
PROVIDER = declare_identity_family("PROVIDER")
RECEIVER = declare_identity_family("RECEIVER")
EQUIPMENT_INSTANCE = declare_identity_family("EQUIPMENT_INSTANCE")
TARGET_CONTEXT = declare_identity_family("TARGET_CONTEXT")
GLOBAL_SERVICE = declare_identity_family("GLOBAL_SERVICE")
TASK = declare_identity_family("TASK")
MODIFIER = declare_identity_family("MODIFIER")
DAMAGE_ROOT = declare_identity_family("DAMAGE_ROOT")
DAMAGE_HIT = declare_identity_family("DAMAGE_HIT")
DAMAGE_COMPONENT = declare_identity_family("DAMAGE_COMPONENT")

FAMILY_B: tuple[IdentityFamily, ...] = (
    OWNER,
    CASTER,
    PROVIDER,
    RECEIVER,
    EQUIPMENT_INSTANCE,
    TARGET_CONTEXT,
    GLOBAL_SERVICE,
    TASK,
    MODIFIER,
    DAMAGE_ROOT,
    DAMAGE_HIT,
    DAMAGE_COMPONENT,
)

FAMILY_B_NAMES: tuple[str, ...] = tuple(family.name for family in FAMILY_B)

#: The four source/role families that are most often wrongly assumed equal.
ROLE_FAMILIES: tuple[IdentityFamily, ...] = (OWNER, CASTER, PROVIDER, RECEIVER)

_ROLE_BUNDLE_SCHEMA = "role_bundle/1"

#: Role attribute -> required family.  Module level on purpose: an annotated
#: class attribute inside a dataclass would become a constructor field.
_ROLE_FAMILY_FIELDS: tuple[tuple[str, IdentityFamily], ...] = (
    ("owner", OWNER),
    ("caster", CASTER),
    ("provider", PROVIDER),
)


def require_family_b(value: Any) -> IdentityFamily:
    """Return a family from the F02-003 set, or raise."""
    family = require_declared_family(value)
    if family.name not in FAMILY_B_NAMES:
        raise TypedIdentityError(
            f"{family.name!r} is not one of the F02-003 families "
            f"{FAMILY_B_NAMES}"
        )
    return family


@dataclass(frozen=True)
class RoleBundle:
    """Owner, caster, provider and receiver as four separate identities.

    They are stored in four separate fields and are never derived from one
    another.  Two roles may legitimately carry the same value while remaining
    different facts, so no equivalence between them is ever assumed.
    """

    owner: TypedIdentity
    caster: TypedIdentity
    provider: TypedIdentity
    receiver: TypedIdentity | None = None

    def __post_init__(self) -> None:
        for attribute, family in _ROLE_FAMILY_FIELDS:
            value = getattr(self, attribute)
            if not isinstance(value, TypedIdentity):
                raise TypedIdentityError(
                    f"RoleBundle.{attribute} must be a TypedIdentity"
                )
            if value.family.name != family.name:
                raise TypedIdentityError(
                    f"RoleBundle.{attribute} must belong to family "
                    f"{family.name}, got {value.family.name}"
                )
        if self.receiver is not None:
            if not isinstance(self.receiver, TypedIdentity):
                raise TypedIdentityError(
                    "RoleBundle.receiver must be a TypedIdentity or absent"
                )
            if self.receiver.family.name != RECEIVER.name:
                raise TypedIdentityError(
                    f"RoleBundle.receiver must belong to family {RECEIVER.name}"
                )

    def roles(self) -> tuple[str, ...]:
        names = ["owner", "caster", "provider"]
        if self.receiver is not None:
            names.append("receiver")
        return tuple(names)

    def values_coincide(self) -> bool:
        """True when at least two roles carry the same value.

        Coincidence of values is recorded as a fact; it never merges the roles.
        """
        values = [self.owner.value, self.caster.value, self.provider.value]
        if self.receiver is not None:
            values.append(self.receiver.value)
        return len(set(values)) < len(values)

    def assume_provider_is_caster(self) -> NoReturn:
        """Refuse: provider and caster are different families."""
        raise TypedIdentityError(
            "provider must not be assumed to be caster; they are separate "
            "identity families and any conversion needs its own named contract"
        )

    def assume_owner_is_actor(self) -> NoReturn:
        """Refuse: owner and actor are different families."""
        raise TypedIdentityError(
            "owner must not be assumed to be an actor; they are separate "
            "identity families"
        )

    def assume_team_is_formation(self) -> NoReturn:
        """Refuse: team and formation slot are different families."""
        raise TypedIdentityError(
            "team must not be assumed to be formation; they are separate "
            "identity families"
        )

    def __bool__(self) -> NoReturn:
        raise TypedIdentityError(
            "RoleBundle has no truthiness; inspect its roles explicitly"
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": _ROLE_BUNDLE_SCHEMA,
            "owner": self.owner.to_dict(),
            "caster": self.caster.to_dict(),
            "provider": self.provider.to_dict(),
        }
        if self.receiver is not None:
            payload["receiver"] = self.receiver.to_dict()
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoleBundle":
        if not isinstance(data, Mapping):
            raise TypedIdentityError(
                f"role bundle document must be a mapping, got "
                f"{type(data).__name__}"
            )
        schema = data["schema"] if "schema" in data else _ROLE_BUNDLE_SCHEMA
        if schema != _ROLE_BUNDLE_SCHEMA:
            raise TypedIdentityError(
                f"unknown role bundle schema {schema!r}; expected "
                f"{_ROLE_BUNDLE_SCHEMA!r}"
            )
        for name in ("owner", "caster", "provider"):
            if name not in data:
                raise TypedIdentityError(
                    f"role bundle document is missing the {name!r} role"
                )
        receiver = None
        if "receiver" in data and data["receiver"] is not None:
            receiver = TypedIdentity.from_dict(data["receiver"])
        return cls(
            owner=TypedIdentity.from_dict(data["owner"]),
            caster=TypedIdentity.from_dict(data["caster"]),
            provider=TypedIdentity.from_dict(data["provider"]),
            receiver=receiver,
        )


# ---------------------------------------------------------------------------
# Deterministic, non-reusing allocator (F02-004)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NamespaceState:
    """The published allocation state of one namespace."""

    namespace: str
    generation: int
    next_value: int
    issued: tuple[int, ...] = field(default_factory=tuple)
    tombstones: tuple[int, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not self.namespace:
            raise TypedIdentityError("namespace must be a non-empty string")
        object.__setattr__(self, "generation", _validate_generation(self.generation))
        for label, value in (("next_value", self.next_value),):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise TypedIdentityError(f"{label} must be an int >= 0")
        for label, values in (("issued", self.issued), ("tombstones", self.tombstones)):
            if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
                raise TypedIdentityError(f"{label} must be a tuple or list")
            normalized = tuple(values)
            if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in normalized):
                raise TypedIdentityError(f"{label} entries must be ints >= 0")
            if len(set(normalized)) != len(normalized):
                raise TypedIdentityError(f"{label} entries must be unique")
            object.__setattr__(self, label, normalized)
        if set(self.issued) & set(self.tombstones):
            raise TypedIdentityError("issued values and tombstones must not overlap")
        if any(value >= self.next_value for value in self.issued + self.tombstones):
            raise TypedIdentityError("issued/tombstoned values must be below next_value")

    def is_live(self, value: int) -> bool:
        return value in self.issued

    def is_tombstoned(self, value: int) -> bool:
        return value in self.tombstones

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "generation": self.generation,
            "next_value": self.next_value,
            "issued": list(self.issued),
            "tombstones": list(self.tombstones),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NamespaceState":
        if not isinstance(data, Mapping):
            raise TypedIdentityError("namespace state must be a mapping")
        required = {"namespace", "generation", "next_value", "issued", "tombstones"}
        if set(data) != required:
            raise TypedIdentityError(
                f"namespace state fields must be exactly {tuple(sorted(required))}"
            )
        return cls(
            namespace=data["namespace"],
            generation=data["generation"],
            next_value=data["next_value"],
            issued=tuple(data["issued"]),
            tombstones=tuple(data["tombstones"]),
        )


@dataclass(frozen=True)
class AllocationTicket:
    """A private reservation.  It is not published until it is committed.

    Holding a ticket changes nothing: an aborted ticket leaves the allocator
    byte-identical, and a failed construction never reaches commit, so no ID is
    consumed.
    """

    namespace: str
    generation: int
    value: int
    family: IdentityFamily
    committed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "generation": self.generation,
            "value": self.value,
            "family": self.family.serialize(),
            "committed": self.committed,
        }


class IdentityAllocator:
    """Deterministic, non-reusing, per-namespace, generation-aware allocator.

    Properties, all enforced by tests:

    * **Deterministic.**  Allocation depends only on the allocator's own
      published state, never on a clock, an address or a random source.
    * **Non-reusing.**  A retired value is tombstoned and is never handed out
      again, even though its slot is free.
    * **Per-namespace.**  Each namespace has its own independent counter.
    * **Generation-aware.**  Advancing a generation starts a fresh value space
      and invalidates outstanding tickets from the previous generation.
    * **Private until commit.**  ``reserve`` publishes nothing, ``abort`` leaves
      the allocator identical, and only ``commit`` consumes an ID.
    """

    def __init__(self) -> None:
        self._published: dict[str, NamespaceState] = {}

    # -- state -----------------------------------------------------------

    def state_for(self, namespace: str) -> NamespaceState:
        """The published state of a namespace, creating an empty one if needed."""
        state = self._peek(namespace)
        if namespace not in self._published:
            self._published[namespace] = state
        return state

    def _peek(self, namespace: str) -> NamespaceState:
        """Read a namespace's state without publishing anything."""
        if not isinstance(namespace, str) or not namespace:
            raise TypedIdentityError("namespace must be a non-empty string")
        existing = self._published.get(namespace)
        if existing is None:
            return NamespaceState(
                namespace=namespace, generation=0, next_value=0
            )
        return existing

    def namespaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._published))

    def snapshot(self) -> dict[str, Any]:
        """A serializable view of the published state, for abort/commit checks."""
        return {
            name: state.to_dict()
            for name, state in sorted(self._published.items())
        }

    # -- allocation ------------------------------------------------------

    def reserve(
        self,
        family: Any,
        namespace: str,
        *,
        generation: int | None = None,
    ) -> AllocationTicket:
        """Return a private reservation.  Publishes nothing."""
        resolved_family = require_declared_family(family)
        # _peek (not state_for) so that reserving in a brand-new namespace does
        # not publish a namespace entry either.
        state = self._peek(namespace)
        wanted_generation = (
            state.generation
            if generation is None
            else _validate_generation(generation)
        )
        if wanted_generation != state.generation:
            raise TypedIdentityError(
                f"generation {wanted_generation} is not the published generation "
                f"{state.generation} of namespace {namespace!r}"
            )
        return AllocationTicket(
            namespace=namespace,
            generation=wanted_generation,
            value=state.next_value,
            family=resolved_family,
        )

    def commit(self, ticket: AllocationTicket) -> TypedIdentity:
        """Publish a reservation and return the resulting identity."""
        if not isinstance(ticket, AllocationTicket):
            raise TypedIdentityError(
                f"commit() requires an AllocationTicket, got "
                f"{type(ticket).__name__}"
            )
        if ticket.committed:
            raise TypedIdentityError(
                f"ticket for {ticket.namespace!r} value {ticket.value} was "
                "already committed; a ticket is committed at most once"
            )
        state = self.state_for(ticket.namespace)
        if ticket.generation != state.generation:
            raise TypedIdentityError(
                f"ticket generation {ticket.generation} is stale; namespace "
                f"{ticket.namespace!r} is at generation {state.generation}"
            )
        if ticket.value != state.next_value:
            raise TypedIdentityError(
                f"ticket value {ticket.value} is not the next value "
                f"{state.next_value} of namespace {ticket.namespace!r}"
            )
        if state.is_tombstoned(ticket.value):
            raise TypedIdentityError(
                f"value {ticket.value} is tombstoned in {ticket.namespace!r} and "
                "must never be reused"
            )
        self._published[ticket.namespace] = NamespaceState(
            namespace=state.namespace,
            generation=state.generation,
            next_value=state.next_value + 1,
            issued=state.issued + (ticket.value,),
            tombstones=state.tombstones,
        )
        return TypedIdentity.local(
            ticket.family,
            ticket.namespace,
            ticket.value,
            generation=ticket.generation,
        )

    def allocate(self, family: Any, namespace: str) -> TypedIdentity:
        """Reserve and commit in one step, for callers with no transaction."""
        return self.commit(self.reserve(family, namespace))

    def abort(self, ticket: AllocationTicket) -> None:
        """Discard a reservation.  The allocator is left identical."""
        if not isinstance(ticket, AllocationTicket):
            raise TypedIdentityError(
                f"abort() requires an AllocationTicket, got "
                f"{type(ticket).__name__}"
            )
        # Deliberately does nothing to the published state: no ID was consumed.

    # -- retirement ------------------------------------------------------

    def retire(self, identity: TypedIdentity) -> NamespaceState:
        """Tombstone a live identity's value so it is never reused."""
        if not isinstance(identity, TypedIdentity):
            raise TypedIdentityError(
                f"retire() requires a TypedIdentity, got {type(identity).__name__}"
            )
        if not identity.value_is_int():
            raise TypedIdentityError(
                f"only integer identities are allocated; {identity.value!r} was "
                "not allocated by this allocator"
            )
        state = self.state_for(identity.namespace)
        value = identity.require_int_value()
        if identity.generation != state.generation:
            raise TypedIdentityError(
                f"identity generation {identity.generation} is stale; namespace "
                f"{identity.namespace!r} is at generation {state.generation}"
            )
        if not state.is_live(value):
            raise TypedIdentityError(
                f"value {value} is not live in {identity.namespace!r}"
            )
        self._published[identity.namespace] = NamespaceState(
            namespace=state.namespace,
            generation=state.generation,
            next_value=state.next_value,
            issued=tuple(v for v in state.issued if v != value),
            tombstones=state.tombstones + (value,),
        )
        return self._published[identity.namespace]

    # -- generations -----------------------------------------------------

    def begin_generation(self, namespace: str) -> NamespaceState:
        """Advance the namespace generation without reusing a raw token.

        Outstanding tickets from the previous generation become stale.
        """
        state = self.state_for(namespace)
        self._published[namespace] = NamespaceState(
            namespace=state.namespace,
            generation=state.generation + 1,
            next_value=state.next_value,
            issued=(),
            tombstones=state.tombstones,
        )
        return self._published[namespace]

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Lossless deterministic allocator state for clone/snapshot/hash."""
        return {
            "schema": IDENTITY_ALLOCATOR_SCHEMA,
            "namespaces": [
                self._published[name].to_dict() for name in sorted(self._published)
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IdentityAllocator":
        if not isinstance(data, Mapping):
            raise TypedIdentityError("allocator document must be a mapping")
        if set(data) != {"schema", "namespaces"}:
            raise TypedIdentityError(
                "allocator document must contain exactly 'schema' and 'namespaces'"
            )
        if data["schema"] != IDENTITY_ALLOCATOR_SCHEMA:
            raise TypedIdentityError(
                f"unknown allocator schema {data['schema']!r}"
            )
        raw = data["namespaces"]
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
            raise TypedIdentityError("allocator namespaces must be a list")
        allocator = cls()
        previous: str | None = None
        for item in raw:
            state = NamespaceState.from_dict(item)
            if previous is not None and state.namespace <= previous:
                raise TypedIdentityError(
                    "allocator namespaces must be unique and sorted"
                )
            allocator._published[state.namespace] = state
            previous = state.namespace
        return allocator

    def clone(self) -> "IdentityAllocator":
        return type(self).from_dict(self.to_dict())

