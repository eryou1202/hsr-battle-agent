# -*- coding: utf-8 -*-
"""Dependency-obligation representation for strict preflight (G01-001).

REPRESENTATION ONLY.  This module describes *what a single dependency
obligation is*: who owns it, which contract and evidence mode it binds, the
ordered reads and writes it declares, its ordered child references, its
explicitly unresolved material, and its resolution state.  It deliberately
contains none of the machinery that acts on an obligation:

* it does **not** compute dependency closure (that is G01-002);
* it does **not** traverse child references at all -- a child is a *reference*,
  not an embedded obligation, so no traversal is even reachable from the types;
* it does **not** issue a ``GateCertificate`` (G01-004) and does not import the
  certificate producer;
* it does **not** execute anything and has no ``execute``/``apply``/``commit``
  entry point;
* it does **not** touch ``BattleState`` or allocate an identity.

Authority grounding
-------------------

``astra_semantic_freeze_v1.json`` ``step_transaction_contract.phases``:

* ``PREFLIGHT`` -- "Pure dependency closure before any battle mutation, RNG
  draw, ID allocation or queue write.";
* ``GATE_CERTIFICATE`` -- "Bind complete effect plan, allowed reads/writes,
  evidence refs and mode to input/state/contract revisions.  **Reject any
  UNKNOWN obligation**; there is no trust-the-caller-native override."

``authority.precedence[3]`` -- "A conflict not explicitly resolved here blocks
execution; **never select the more permissive label**."  This is why the
resolution vocabulary fails closed, why a non-``RESOLVED`` obligation can never
present itself as satisfied, and why the obligation's ``evidence_mode`` must be
the *exact* mode carried by its ``ContractRef`` rather than the more permissive
of the two.

``evidence_modes`` -- ``UNSUPPORTED`` is "Descriptor/inspection allowed;
execution denied", which is why ``UNSUPPORTED`` is modelled as a *known
negative disposition* distinct from an *open* ``UNKNOWN``.

Fail-closed rule
----------------

``UNKNOWN`` is the one state that means "nobody has answered this yet", so it is
given two independent guards:

* :meth:`ObligationResolution.__bool__` raises, and so does
  :meth:`DependencyObligation.__bool__` -- ``if obligation:`` can never be
  written and silently pass a gate for *any* state, resolved or not;
* :meth:`DependencyObligation.is_satisfied` is the only affirmative query, it is
  an explicit method call, and it returns ``True`` for ``RESOLVED`` alone.

This is intentionally stricter than ``EvidenceMode``, which keeps ordinary enum
truthiness because it is pure provenance.  A resolution state is gate-relevant
-- the whole point of the ``GATE_CERTIFICATE`` phase is that a truthiness
shortcut here would authorise execution -- so a truthiness shortcut is removed
rather than discouraged.

Ownership and mutation isolation
--------------------------------

(CR-G01-001-RAW-ALIAS-20260923-001)

The representation each object owns is **private**, and every public name is a
read-only property that returns a detached, revalidated copy.  This matters
because the nested representation is *not* deeply immutable: a
:class:`PresenceValue` legitimately carries a caller's list/dict payload, and an
:class:`UnknownHandle` legitimately carries an opaque payload and provenance
mapping.  ``frozen=True`` freezes the binding, a ``tuple`` freezes the sequence,
and ``MappingProxyType`` freezes a view -- none of them freezes a nested list or
dict, so none of the three is treated as proof of deep immutability here.

The earlier revision exposed the owned objects directly, so
``obligation.reads[0].extent.require_present()["items"].append(...)`` rewrote the
obligation's own future ``to_dict()``; the same held for ``writes``, and for
``unknown_handles[0].payload`` and ``unknown_handles[0].provenance``.  Now
private backing storage holds the representation and every read constructs a
fresh value through the type's own ``to_dict``/``from_dict`` round trip, so a
caller can never reach an object this module still owns.

Losslessness rules
------------------

Ordered sequences keep their order and keep repeated entries.  Nothing is
sorted, deduplicated, defaulted or flattened, and no list payload is converted
to a tuple.  Absent/null/present distinctions are carried by
:class:`PresenceValue` on the declared access extent, and key *membership* --
never truthiness -- decides them.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import (
    ContractRef,
    EvidenceMode,
    EvidenceVocabularyError,
    UnknownHandle,
    parse_evidence_mode,
)
from hsr_battle_agent.battle_ir.lossless_value import (
    PresenceValue,
    PresenceValueError,
)
from hsr_battle_agent.battle_sandbox.errors import (
    BattleSandboxError,
    StructuredRejection,
)

__all__ = [
    "CHILD_OBLIGATION_REF_SCHEMA",
    "DEPENDENCY_OBLIGATION_SCHEMA",
    "OBLIGATION_ACCESS_SCHEMA",
    "OBLIGATION_RESOLUTION_SPELLINGS",
    "PUBLIC_REPRESENTATION_NAMES",
    "PREFLIGHT_RESULT_SCHEMA",
    "SATISFIED_RESOLUTION",
    "ChildObligationRef",
    "DependencyObligation",
    "DependencyObligationError",
    "ObligationAccess",
    "ObligationResolution",
    "PreflightOutcome",
    "PreflightResult",
    "parse_obligation_resolution",
    "require_owner_code",
]

_UNSET = object()
PREFLIGHT_RESULT_SCHEMA = "preflight_result/1"


class DependencyObligationError(BattleSandboxError):
    """Raised for a lossy or inconsistent dependency-obligation representation."""


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

def require_owner_code(value: Any, *, role: str = "owner") -> str:
    """Return a stable uppercase obligation-owner code, or raise.

    The rule matches ``battle_sandbox.errors.StructuredRejection`` exactly
    (non-empty, uppercase, no surrounding whitespace) so a G01-003 rejection can
    name the obligation owner without a lossy conversion.  This is a *stable
    machine code*, not a human label and not a battle-entity identity: an owner
    code must never be interchangeable with an actor or team identity.
    """
    if not isinstance(value, str) or not value:
        raise DependencyObligationError(f"{role} must be a non-empty string")
    if value != value.strip():
        raise DependencyObligationError(
            f"{role} {value!r} must not carry surrounding whitespace"
        )
    if value.upper() != value:
        raise DependencyObligationError(
            f"{role} {value!r} must be an uppercase stable machine code"
        )
    return value


# ---------------------------------------------------------------------------
# Resolution state
# ---------------------------------------------------------------------------

class ObligationResolution(Enum):
    """Whether a dependency obligation has been discharged.

    This is a **local gate-representation vocabulary**, not a recovered
    client-native enum.  Its three states encode the fail-closed distinctions
    required by the frozen transaction/evidence contracts; they are never
    merged, and none of them is a truthiness value:

    ``RESOLVED``
        The obligation is closed by its cited contract and evidence.  This is
        the only state :meth:`is_satisfied` reports as satisfied.
    ``UNKNOWN``
        Nobody has answered this yet.  The authority's gate phase rejects any
        UNKNOWN obligation outright, so this state may never be read as success.
    ``UNSUPPORTED``
        A known negative: the material is inspectable but the authority's
        ``UNSUPPORTED`` evidence mode denies execution.  Distinct from
        ``UNKNOWN`` because the disposition is settled -- what is missing is
        support, not an answer.

    Deliberately **not** a ``str`` mixin: accidental string equality against a
    ledger spelling or a raw label is exactly the failure this vocabulary must
    not permit.  ``__bool__`` refuses, so the state can never be used as a
    boolean gate.
    """

    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"

    def __bool__(self) -> NoReturn:
        raise DependencyObligationError(
            f"ObligationResolution.{self.name} is a resolution classification, "
            "not a boolean and not a permission; call is_satisfied() explicitly"
        )

    def serialize(self) -> str:
        return str(self.value)

    @classmethod
    def spellings(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)

    def is_satisfied(self) -> bool:
        """``True`` for ``RESOLVED`` alone.  The sole affirmative query."""
        return self is ObligationResolution.RESOLVED


OBLIGATION_RESOLUTION_SPELLINGS: tuple[str, ...] = ObligationResolution.spellings()

#: The single member that counts as satisfied, named once and nowhere else.
SATISFIED_RESOLUTION = ObligationResolution.RESOLVED


def parse_obligation_resolution(value: Any) -> ObligationResolution:
    """Strictly parse a serialized resolution state; never guess a default."""
    if isinstance(value, ObligationResolution):
        return value
    if value is None:
        raise DependencyObligationError(
            "obligation resolution cannot be absent; absence is not a "
            "resolution state"
        )
    if not isinstance(value, str):
        raise DependencyObligationError(
            f"obligation resolution must be a serialized string, got "
            f"{type(value).__name__}"
        )
    if not value:
        raise DependencyObligationError(
            "obligation resolution must be a non-empty string"
        )
    try:
        return ObligationResolution(value)
    except ValueError:
        raise DependencyObligationError(
            f"unknown obligation resolution {value!r}; expected one of "
            f"{OBLIGATION_RESOLUTION_SPELLINGS}. A mapping-ledger state "
            "spelling is not an obligation resolution"
        ) from None


def _assert_resolution_round_trip() -> None:
    """Import-time guard: every spelling must parse back to its own member."""
    for member in ObligationResolution:
        if parse_obligation_resolution(member.value) is not member:
            raise DependencyObligationError(
                f"ObligationResolution.{member.name} failed identity round trip"
            )


_assert_resolution_round_trip()


# ---------------------------------------------------------------------------
# Detachment helpers
# ---------------------------------------------------------------------------
#
# Each helper takes an object this module owns and returns an independent value
# built through that type's own serialized round trip.  They are the only way
# representation leaves this module, so "can a caller mutate our storage?" has a
# single answer: no.  ``PresenceValue`` and ``ContractRef`` themselves are left
# untouched -- this is a local ownership fix, not a change to shared semantics.

def _detach_presence(value: PresenceValue) -> PresenceValue:
    return PresenceValue.from_dict(value.to_dict())


def _detach_contract(value: ContractRef) -> ContractRef:
    return ContractRef.from_dict(value.to_dict())


def _detach_access(value: "ObligationAccess") -> "ObligationAccess":
    return ObligationAccess.from_dict(value.to_dict())


def _detach_child(value: "ChildObligationRef") -> "ChildObligationRef":
    return ChildObligationRef.from_dict(value.to_dict())


def _detach_handle(value: UnknownHandle) -> UnknownHandle:
    return UnknownHandle.from_dict(value.to_dict())


def _require_target(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise DependencyObligationError(
            "ObligationAccess.target must be a non-empty string"
        )
    if value != value.strip():
        raise DependencyObligationError(
            f"ObligationAccess.target {value!r} must not carry surrounding "
            "whitespace"
        )
    return value


def _require_presence(value: Any, label: str) -> PresenceValue:
    if not isinstance(value, PresenceValue):
        raise DependencyObligationError(
            f"{label} must be a PresenceValue; absence, null and empty may "
            "never be inferred from a bare value"
        )
    return _detach_presence(value)


def _require_contract_ref(value: Any, label: str) -> ContractRef:
    if not isinstance(value, ContractRef):
        raise DependencyObligationError(
            f"{label} must be a ContractRef; a descriptor, ledger entry or "
            "unknown handle is not an obligation contract"
        )
    return _detach_contract(value)


def _require_sequence(
    value: Any,
    expected: type,
    label: str,
    detacher: Callable[[Any], Any],
) -> tuple[Any, ...]:
    """Validate an ordered sequence, preserve order/duplicates, detach copies."""
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise DependencyObligationError(
            f"{label} must be a tuple or list of {expected.__name__} values"
        )
    detached: list[Any] = []
    for index, item in enumerate(value):
        if not isinstance(item, expected):
            raise DependencyObligationError(
                f"{label}[{index}] must be a {expected.__name__}, got "
                f"{type(item).__name__}"
            )
        detached.append(detacher(item))
    # No sort, no dedupe: source order and repeated dependencies are data.
    return tuple(detached)


# ---------------------------------------------------------------------------
# Declared access (ordered read / write entry)
# ---------------------------------------------------------------------------

OBLIGATION_ACCESS_SCHEMA = "obligation_access/1"


@dataclass(frozen=True, eq=False, init=False, repr=False)
class ObligationAccess:
    """One declared read or write of a named dependency.

    ``target`` is a symbolic dependency address (the freeze binds "allowed
    reads/writes"), never a concrete state object: this module must not hold a
    reference into live battle state.

    ``extent`` is a :class:`PresenceValue`, so three genuinely different facts
    stay distinguishable:

    * ``ABSENT`` -- the access was declared at the target level only, with no
      extent stated;
    * ``NULL`` -- an extent was stated and it is explicitly null;
    * ``PRESENT(x)`` -- an extent was stated as ``x``.

    An empty extent is still ``PRESENT``; nothing here treats an empty, false or
    zero extent as absence.

    The extent is owned privately and :attr:`extent` returns a detached copy.
    ``PresenceValue.require_present()`` hands back a caller-owned payload, so
    returning the owned envelope would itself be a mutable route into this
    object's future ``to_dict()``.
    """

    _target: str
    _extent: PresenceValue

    def __init__(
        self, target: Any, extent: PresenceValue | object = _UNSET
    ) -> None:
        object.__setattr__(self, "_target", _require_target(target))
        object.__setattr__(
            self,
            "_extent",
            _require_presence(
                PresenceValue.absent() if extent is _UNSET else extent,
                "ObligationAccess.extent",
            ),
        )

    # -- public reads (detached) -------------------------------------------

    @property
    def target(self) -> str:
        """The symbolic dependency address.  A string, already immutable."""
        return self._target

    @property
    def extent(self) -> PresenceValue:
        """Return a detached, revalidated copy of the declared extent."""
        return _detach_presence(self._extent)

    def detail(self) -> PresenceValue:
        """Alias for :attr:`extent`; kept for existing callers."""
        return self.extent

    # -- serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OBLIGATION_ACCESS_SCHEMA,
            "target": self._target,
            "extent": _detach_presence(self._extent).to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ObligationAccess":
        if not isinstance(data, Mapping):
            raise DependencyObligationError(
                "obligation access document must be a mapping"
            )
        if set(data) != {"schema", "target", "extent"}:
            raise DependencyObligationError(
                "obligation access must contain exactly schema, target and extent"
            )
        if data["schema"] != OBLIGATION_ACCESS_SCHEMA:
            raise DependencyObligationError(
                f"unknown obligation access schema {data['schema']!r}"
            )
        try:
            extent = PresenceValue.from_dict(data["extent"])
        except PresenceValueError as exc:
            raise DependencyObligationError(
                f"invalid obligation access extent: {exc}"
            ) from exc
        return cls(target=data["target"], extent=extent)

    def detached_copy(self) -> "ObligationAccess":
        return ObligationAccess.from_dict(self.to_dict())

    # -- identity -----------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ObligationAccess):
            return NotImplemented
        return self._target == other._target and self._extent == other._extent

    def __hash__(self) -> int:
        return hash((self._target, self._extent))

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"ObligationAccess(target={self._target!r}, "
            f"extent={self._extent.to_dict()['presence']})"
        )


# ---------------------------------------------------------------------------
# Child reference
# ---------------------------------------------------------------------------

CHILD_OBLIGATION_REF_SCHEMA = "child_obligation_ref/1"


@dataclass(frozen=True, eq=False, init=False, repr=False)
class ChildObligationRef:
    """A *reference* to a child obligation.  Not the obligation itself.

    A reference carries the child's owner code and contract identity and stops
    there.  Because it never embeds a :class:`DependencyObligation` and this
    module exposes no traversal helper, recursive closure is structurally out of
    reach here -- which is exactly the G01-001 boundary.  Reference order and
    repeated references are preserved: two identical references are two
    dependencies, not one.

    A :class:`ContractRef` is deeply immutable (all of its leaves are strings, an
    enum and a tuple of strings), so this route was already safe; the contract is
    detached anyway so the rule is uniform rather than route-by-route.
    """

    _owner: str
    _contract_ref: ContractRef

    def __init__(self, owner: Any, contract_ref: Any) -> None:
        object.__setattr__(
            self, "_owner", require_owner_code(owner, role="child owner")
        )
        object.__setattr__(
            self,
            "_contract_ref",
            _require_contract_ref(
                contract_ref, "ChildObligationRef.contract_ref"
            ),
        )

    # -- public reads (detached) -------------------------------------------

    @property
    def owner(self) -> str:
        """The child's owner code.  A string, already immutable."""
        return self._owner

    @property
    def contract_ref(self) -> ContractRef:
        """Return a detached, revalidated copy of the child contract."""
        return _detach_contract(self._contract_ref)

    # -- serialization ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CHILD_OBLIGATION_REF_SCHEMA,
            "owner": self._owner,
            "contract_ref": _detach_contract(self._contract_ref).to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ChildObligationRef":
        if not isinstance(data, Mapping):
            raise DependencyObligationError(
                "child obligation reference document must be a mapping"
            )
        if set(data) != {"schema", "owner", "contract_ref"}:
            raise DependencyObligationError(
                "child obligation reference must contain exactly schema, owner "
                "and contract_ref"
            )
        if data["schema"] != CHILD_OBLIGATION_REF_SCHEMA:
            raise DependencyObligationError(
                f"unknown child obligation reference schema {data['schema']!r}"
            )
        try:
            contract_ref = ContractRef.from_dict(data["contract_ref"])
        except EvidenceVocabularyError as exc:
            raise DependencyObligationError(
                f"invalid child obligation contract reference: {exc}"
            ) from exc
        return cls(owner=data["owner"], contract_ref=contract_ref)

    def detached_copy(self) -> "ChildObligationRef":
        return ChildObligationRef.from_dict(self.to_dict())

    # -- identity -----------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChildObligationRef):
            return NotImplemented
        return (
            self._owner == other._owner
            and self._contract_ref == other._contract_ref
        )

    def __hash__(self) -> int:
        return hash((self._owner, self._contract_ref.identity()))

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"ChildObligationRef(owner={self._owner!r}, "
            f"contract_id={self._contract_ref.contract_id!r})"
        )


# ---------------------------------------------------------------------------
# DependencyObligation
# ---------------------------------------------------------------------------

DEPENDENCY_OBLIGATION_SCHEMA = "dependency_obligation/1"

#: The complete declared serialized field set.
_OBLIGATION_FIELDS = frozenset(
    {
        "schema",
        "owner",
        "contract_ref",
        "evidence_mode",
        "resolution",
        "reads",
        "writes",
        "children",
        "unknown_handles",
    }
)

#: The public read names, all of which must be properties (never plain fields).
PUBLIC_REPRESENTATION_NAMES: tuple[str, ...] = (
    "owner",
    "contract_ref",
    "evidence_mode",
    "resolution",
    "reads",
    "writes",
    "children",
    "unknown_handles",
)


@dataclass(frozen=True, eq=False, init=False, repr=False)
class DependencyObligation:
    """One dependency obligation, represented and nothing more.

    Equality is the complete serialized representation.  Hashing is disabled
    because nested unresolved payloads may hold mappings/lists, so an
    object-identity hash would contradict representation equality.

    Every public name in :data:`PUBLIC_REPRESENTATION_NAMES` is a read-only
    property over private storage, so there is no public dataclass field to
    reach through.  The nested representation is not deeply immutable -- a
    :class:`PresenceValue` payload and an :class:`UnknownHandle` payload are
    deliberately arbitrary caller values -- which is exactly why the owned
    objects are never handed out.

    There is deliberately **no** ``execution_permitted`` and no gate method: this
    type cannot authorise anything.  :meth:`is_satisfied` reports the
    representation's own state and is not a permission.
    """

    _owner: str
    _contract_ref: ContractRef
    _evidence_mode: EvidenceMode
    _resolution: ObligationResolution
    _reads: tuple[ObligationAccess, ...]
    _writes: tuple[ObligationAccess, ...]
    _children: tuple[ChildObligationRef, ...]
    _unknown_handles: tuple[UnknownHandle, ...]

    __hash__ = None

    def __init__(
        self,
        owner: Any,
        contract_ref: Any,
        evidence_mode: Any,
        resolution: Any,
        reads: Any = (),
        writes: Any = (),
        children: Any = (),
        unknown_handles: Any = (),
    ) -> None:
        object.__setattr__(self, "_owner", require_owner_code(owner))
        contract = _require_contract_ref(contract_ref, "contract_ref")
        object.__setattr__(self, "_contract_ref", contract)
        try:
            mode = parse_evidence_mode(evidence_mode)
        except EvidenceVocabularyError as exc:
            raise DependencyObligationError(str(exc)) from exc
        # Fail closed on a mode disagreement rather than picking the more
        # permissive label (authority precedence[3]).
        if mode is not contract.evidence_mode:
            raise DependencyObligationError(
                "obligation evidence_mode must be the exact mode carried by its "
                f"ContractRef ({contract.evidence_mode.value}); got {mode.value}"
            )
        object.__setattr__(self, "_evidence_mode", mode)
        object.__setattr__(
            self, "_resolution", parse_obligation_resolution(resolution)
        )
        object.__setattr__(
            self,
            "_reads",
            _require_sequence(reads, ObligationAccess, "reads", _detach_access),
        )
        object.__setattr__(
            self,
            "_writes",
            _require_sequence(writes, ObligationAccess, "writes", _detach_access),
        )
        object.__setattr__(
            self,
            "_children",
            _require_sequence(
                children, ChildObligationRef, "children", _detach_child
            ),
        )
        object.__setattr__(
            self,
            "_unknown_handles",
            _require_sequence(
                unknown_handles, UnknownHandle, "unknown_handles", _detach_handle
            ),
        )
        self._enforce_resolution_coherence()

    def _enforce_resolution_coherence(self) -> None:
        """Keep the resolution state and the unresolved material consistent.

        Three distinct disciplines, each grounded in the gate phase's
        requirement to bind and reject explicitly:

        * ``RESOLVED`` must carry **no** unresolved material.  A closed
          obligation with an open question is a contradiction, and accepting it
          would let an open question ride along behind a satisfied state.
        * ``UNKNOWN`` must carry **at least one** handle.  The gate cannot
          request what the obligation never states, and every other unresolved
          representation in this codebase is required to name its blocker.
        * ``UNSUPPORTED`` is a settled negative, so what it lacks is support
          rather than an answer; citing a reason is permitted, not required.
        """
        if self._resolution is ObligationResolution.RESOLVED:
            if self._unknown_handles:
                raise DependencyObligationError(
                    "a RESOLVED obligation must not carry unresolved handles; "
                    "an open question cannot hide behind a satisfied state"
                )
        elif self._resolution is ObligationResolution.UNKNOWN:
            if not self._unknown_handles:
                raise DependencyObligationError(
                    "an UNKNOWN obligation must state at least one UnknownHandle; "
                    "the gate cannot request evidence the obligation never names"
                )

    # -- explicit queries (never truthiness) ------------------------------

    def __bool__(self) -> NoReturn:
        raise DependencyObligationError(
            "DependencyObligation has no truthiness; a dependency obligation is "
            "representation, not a permission -- call is_satisfied() explicitly"
        )

    def is_satisfied(self) -> bool:
        """``True`` only for a ``RESOLVED`` obligation.

        Representation state only.  A ``True`` here means the obligation records
        itself as closed; it grants no execution, satisfies no native gate and
        produces no certificate.
        """
        return self._resolution.is_satisfied()

    def resolution_state(self) -> ObligationResolution:
        """Return the resolution classification explicitly."""
        return self._resolution

    # -- public reads (all detached) --------------------------------------

    @property
    def owner(self) -> str:
        """The obligation owner code.  A string, already immutable."""
        return self._owner

    @property
    def contract_ref(self) -> ContractRef:
        """Return a detached, revalidated copy of the obligation contract."""
        return _detach_contract(self._contract_ref)

    @property
    def evidence_mode(self) -> EvidenceMode:
        """The evidence mode.  An enum member, already immutable."""
        return self._evidence_mode

    @property
    def resolution(self) -> ObligationResolution:
        """The resolution state.  An enum member, already immutable."""
        return self._resolution

    @property
    def reads(self) -> tuple[ObligationAccess, ...]:
        """Detached ordered reads.  Order and repeats preserved."""
        return tuple(_detach_access(item) for item in self._reads)

    @property
    def writes(self) -> tuple[ObligationAccess, ...]:
        """Detached ordered writes.  Order and repeats preserved."""
        return tuple(_detach_access(item) for item in self._writes)

    @property
    def children(self) -> tuple[ChildObligationRef, ...]:
        """Detached ordered child references.  Not traversed, not resolved."""
        return tuple(_detach_child(item) for item in self._children)

    @property
    def unknown_handles(self) -> tuple[UnknownHandle, ...]:
        """Detached ordered unresolved handles, verbatim and undeduplicated."""
        return tuple(_detach_handle(item) for item in self._unknown_handles)

    # -- alias reads, kept for existing callers ---------------------------

    @property
    def read_targets(self) -> tuple[ObligationAccess, ...]:
        """Alias for :attr:`reads`."""
        return self.reads

    @property
    def write_targets(self) -> tuple[ObligationAccess, ...]:
        """Alias for :attr:`writes`."""
        return self.writes

    @property
    def child_references(self) -> tuple[ChildObligationRef, ...]:
        """Alias for :attr:`children`."""
        return self.children

    @property
    def unresolved_material(self) -> tuple[UnknownHandle, ...]:
        """Alias for :attr:`unknown_handles`."""
        return self.unknown_handles

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        # Built from private storage; every leaf document is freshly created by
        # its own type, so the returned document never aliases owned state.
        return {
            "schema": DEPENDENCY_OBLIGATION_SCHEMA,
            "owner": self._owner,
            "contract_ref": _detach_contract(self._contract_ref).to_dict(),
            "evidence_mode": self._evidence_mode.serialize(),
            "resolution": self._resolution.serialize(),
            "reads": [item.to_dict() for item in self._reads],
            "writes": [item.to_dict() for item in self._writes],
            "children": [item.to_dict() for item in self._children],
            "unknown_handles": [item.to_dict() for item in self._unknown_handles],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DependencyObligation":
        if not isinstance(data, Mapping):
            raise DependencyObligationError(
                "dependency obligation document must be a mapping"
            )
        if set(data) != _OBLIGATION_FIELDS:
            raise DependencyObligationError(
                "dependency obligation must contain exactly the declared schema "
                "fields; missing and extra fields are both rejected"
            )
        if data["schema"] != DEPENDENCY_OBLIGATION_SCHEMA:
            raise DependencyObligationError(
                f"unknown dependency obligation schema {data['schema']!r}"
            )
        for name in ("reads", "writes", "children", "unknown_handles"):
            value = data[name]
            if isinstance(value, (str, bytes)) or not isinstance(
                value, (tuple, list)
            ):
                raise DependencyObligationError(f"{name} must be a list")
        try:
            contract_ref = ContractRef.from_dict(data["contract_ref"])
        except EvidenceVocabularyError as exc:
            raise DependencyObligationError(
                f"invalid obligation contract reference: {exc}"
            ) from exc
        try:
            reads = tuple(ObligationAccess.from_dict(item) for item in data["reads"])
            writes = tuple(
                ObligationAccess.from_dict(item) for item in data["writes"]
            )
            children = tuple(
                ChildObligationRef.from_dict(item) for item in data["children"]
            )
            handles = tuple(
                UnknownHandle.from_dict(item) for item in data["unknown_handles"]
            )
        except EvidenceVocabularyError as exc:
            raise DependencyObligationError(
                f"invalid obligation unresolved material: {exc}"
            ) from exc
        return cls(
            owner=data["owner"],
            contract_ref=contract_ref,
            evidence_mode=data["evidence_mode"],
            resolution=data["resolution"],
            reads=reads,
            writes=writes,
            children=children,
            unknown_handles=handles,
        )

    def detached_copy(self) -> "DependencyObligation":
        """Revalidate a detached copy through its own serialized form."""
        return type(self).from_dict(self.to_dict())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DependencyObligation):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"DependencyObligation(owner={self._owner!r}, "
            f"resolution={self._resolution.name}, reads={len(self._reads)}, "
            f"writes={len(self._writes)}, children={len(self._children)}, "
            f"unknown_handles={len(self._unknown_handles)})"
        )


# ---------------------------------------------------------------------------
# Complete preflight result (G01-003)
# ---------------------------------------------------------------------------

class PreflightOutcome(Enum):
    """The two local top-level preflight outcomes."""

    CLOSED = "CLOSED"
    REJECTED = "REJECTED"

    def __bool__(self) -> NoReturn:
        raise DependencyObligationError(
            "PreflightOutcome has no truthiness; inspect the result explicitly"
        )

    @classmethod
    def parse(cls, value: Any) -> "PreflightOutcome":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise DependencyObligationError("preflight outcome must be a string")
        try:
            return cls(value)
        except ValueError:
            raise DependencyObligationError(
                f"unknown preflight outcome {value!r}"
            ) from None


def _detach_rejection(value: StructuredRejection) -> StructuredRejection:
    if not isinstance(value, StructuredRejection):
        raise DependencyObligationError(
            "preflight rejections must be StructuredRejection values"
        )
    return StructuredRejection.from_dict(value.to_dict())


def _rejection_for_blocker(blocker: Any) -> StructuredRejection:
    """Bind one closure blocker without inventing a diagnostic priority."""
    return StructuredRejection(
        reason_code=f"PREFLIGHT_{blocker.status.value}",
        obligation_owner=blocker.owner,
        evidence_request=blocker.evidence_request,
        contract_refs=(blocker.contract_ref,),
        unknown_handles=blocker.unknown_handles,
        diagnostics={
            "closure_status": blocker.status.value,
            "occurrence_path": list(blocker.occurrence_path),
        },
    )


@dataclass(frozen=True, init=False, eq=False, repr=False)
class PreflightResult:
    """Complete closure plus either no blockers or every structured rejection.

    A result is still not permission.  The only construction path validates a
    complete :class:`DependencyClosure`; a caller cannot label a partial or
    blocked closure ``CLOSED`` and cannot omit a later blocker from a rejected
    result.
    """

    _outcome: PreflightOutcome
    _closure: Any
    _rejections: tuple[StructuredRejection, ...]

    def __init__(
        self,
        *,
        outcome: PreflightOutcome | str,
        closure: Any,
        rejections: tuple[StructuredRejection, ...] | list[StructuredRejection],
    ) -> None:
        # Local import avoids making the G01-001 representation depend on its
        # downstream graph module at import time.
        from hsr_battle_agent.battle_sandbox.dependency_graph import (
            DependencyClosure,
        )

        resolved_outcome = PreflightOutcome.parse(outcome)
        if not isinstance(closure, DependencyClosure):
            raise DependencyObligationError(
                "PreflightResult requires a complete DependencyClosure"
            )
        if isinstance(rejections, (str, bytes)) or not isinstance(
            rejections, (tuple, list)
        ):
            raise DependencyObligationError("rejections must be a tuple or list")
        owned_closure = closure.detached_copy()
        owned_rejections = tuple(_detach_rejection(item) for item in rejections)
        expected_rejections = tuple(
            _rejection_for_blocker(item) for item in owned_closure.blockers
        )

        if resolved_outcome is PreflightOutcome.CLOSED:
            if not owned_closure.is_closed() or owned_rejections:
                raise DependencyObligationError(
                    "CLOSED requires a fully CLOSED closure and zero rejections"
                )
        else:
            if owned_closure.is_closed():
                raise DependencyObligationError(
                    "REJECTED cannot wrap a CLOSED dependency closure"
                )
            if not owned_rejections:
                raise DependencyObligationError(
                    "REJECTED must retain every blocking rejection"
                )
            if [item.to_dict() for item in owned_rejections] != [
                item.to_dict() for item in expected_rejections
            ]:
                raise DependencyObligationError(
                    "REJECTED rejections must exactly bind every closure blocker "
                    "in traversal order"
                )

        object.__setattr__(self, "_outcome", resolved_outcome)
        object.__setattr__(self, "_closure", owned_closure)
        object.__setattr__(self, "_rejections", owned_rejections)

    @classmethod
    def from_closure(cls, closure: Any) -> "PreflightResult":
        from hsr_battle_agent.battle_sandbox.dependency_graph import (
            DependencyClosure,
        )

        if not isinstance(closure, DependencyClosure):
            raise DependencyObligationError(
                "from_closure requires a DependencyClosure"
            )
        detached = closure.detached_copy()
        if detached.is_closed():
            return cls(
                outcome=PreflightOutcome.CLOSED,
                closure=detached,
                rejections=(),
            )
        return cls(
            outcome=PreflightOutcome.REJECTED,
            closure=detached,
            rejections=tuple(
                _rejection_for_blocker(item) for item in detached.blockers
            ),
        )

    def __bool__(self) -> NoReturn:
        raise DependencyObligationError(
            "PreflightResult has no truthiness and is not permission"
        )

    def is_closed(self) -> bool:
        return self._outcome is PreflightOutcome.CLOSED

    def is_rejected(self) -> bool:
        return self._outcome is PreflightOutcome.REJECTED

    @property
    def outcome(self) -> PreflightOutcome:
        return self._outcome

    @property
    def closure(self) -> Any:
        return self._closure.detached_copy()

    @property
    def rejections(self) -> tuple[StructuredRejection, ...]:
        return tuple(_detach_rejection(item) for item in self._rejections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PREFLIGHT_RESULT_SCHEMA,
            "outcome": self._outcome.value,
            "closure": self._closure.to_dict(),
            "rejections": [item.to_dict() for item in self._rejections],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PreflightResult":
        from hsr_battle_agent.battle_sandbox.dependency_graph import (
            DependencyClosure,
        )

        expected = {"schema", "outcome", "closure", "rejections"}
        if not isinstance(data, Mapping) or set(data) != expected:
            raise DependencyObligationError(
                "preflight result must contain every declared field exactly"
            )
        if data["schema"] != PREFLIGHT_RESULT_SCHEMA:
            raise DependencyObligationError("unknown preflight result schema")
        if isinstance(data["rejections"], (str, bytes)) or not isinstance(
            data["rejections"], (tuple, list)
        ):
            raise DependencyObligationError("rejections must be a list")
        return cls(
            outcome=data["outcome"],
            closure=DependencyClosure.from_dict(data["closure"]),
            rejections=tuple(
                StructuredRejection.from_dict(item) for item in data["rejections"]
            ),
        )

    def detached_copy(self) -> "PreflightResult":
        return PreflightResult.from_dict(self.to_dict())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PreflightResult):
            return NotImplemented
        return self.to_dict() == other.to_dict()
