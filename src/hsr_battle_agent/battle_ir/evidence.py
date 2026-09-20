# -*- coding: utf-8 -*-
"""Canonical evidence vocabulary for the Terra representation path.

This module is the **sole** home of the canonical ``EvidenceMode`` class.  Any
other module that needs an evidence mode must import the class object from
here; equal-valued but identity-unequal enum classes are forbidden by
``REFERENCE_QUARANTINE_DECISION`` (see
``docs/agent/terra_architecture_decisions_v1.md``).

Vocabulary is taken verbatim from the frozen Astra authority.  Nothing in this
module invents, renames, merges or reinterprets a frozen spelling, and nothing
here claims that any mode is executable.

Three vocabularies are implemented, deliberately as **three distinct types**:

``EvidenceMode``
    ``astra_semantic_freeze_v1.json`` ``evidence_modes``: how a fact or
    transition is evidenced.  The four serialized spellings are
    ``NATIVE_EVIDENCED``, ``REFERENCE_MODEL``, ``SANDBOX_EXTENSION`` and
    ``UNSUPPORTED``.

``VersionRelation``
    How a source version relates to the target version.  The freeze records
    exactly one such marker, ``CLOSE_4.4.0_TO_4.4.54`` (under the keys
    ``source_version_relation`` and ``version_relation``), and it lists
    ``SOURCE_VERSION_CLOSENESS_PROMOTED_TO_EXACT_NATIVE_PROOF`` as a strict
    rejection.  A close-version source is therefore represented as
    ``CLOSE_VERSION`` and can never compare or merge as ``EXACT_NATIVE``.

``ReadinessClass``
    ``astra_semantic_freeze_v1.json`` ``readiness_classes``: what may be
    implemented or represented.  These are *not* evidence modes; conflating the
    two vocabularies would itself be a reinterpretation.

Design rules enforced here:

* ``EvidenceMode`` is **not** an executability boolean.  It keeps ordinary
  ``Enum`` truthiness and exposes no ``executable`` / ``is_executable`` /
  ``implies_execution`` style helper.  An evidence mode describes provenance;
  callers must use an explicit gate to decide whether an operation may run.
* Serialization is strict.  ``parse_*`` rejects unknown spellings, wrong types,
  ``None`` and empty strings instead of guessing a default.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

__all__ = [
    "CONTRACT_REF_SCHEMA",
    "EVIDENCE_MODE_SPELLINGS",
    "READINESS_CLASS_SPELLINGS",
    "UNKNOWN_HANDLE_SCHEMA",
    "VERSION_RELATION_SPELLINGS",
    "ContractRef",
    "EvidenceMode",
    "EvidenceVocabularyError",
    "ReadinessClass",
    "UnknownHandle",
    "VersionRelation",
    "parse_evidence_mode",
    "parse_readiness_class",
    "parse_version_relation",
    "require_contract_ref",
]


class EvidenceVocabularyError(ValueError):
    """Raised when a serialized evidence-vocabulary value is not recognized."""


class _StrictVocabulary(Enum):
    """Base for the frozen vocabularies.

    Deliberately **not** a ``str`` mixin.  A ``str`` mixin would make
    ``mode == "NATIVE_EVIDENCED"`` succeed accidentally and would give members a
    meaningless lexicographic ordering (``mode < other_mode``), both of which the
    architecture rejects: ``REFERENCE_QUARANTINE_DECISION`` rejects string-only
    labelling precisely because equal strings cannot enforce type or enum
    identity.  Serialization therefore goes through :meth:`serialize` or
    ``.value`` explicitly, and identity is checked with ``is``.

    Ordinary ``Enum`` truthiness is intentionally left alone.  Truthiness does
    not grant execution; the absence of an executability API is the boundary.
    """

    def serialize(self) -> str:
        """Return the exact serialized spelling of this member."""
        return str(self.value)

    @classmethod
    def spellings(cls) -> tuple[str, ...]:
        """Return the frozen spellings of this vocabulary, in declaration order."""
        return tuple(member.value for member in cls)


def _parse(vocabulary: type[_StrictVocabulary], value: Any, label: str):
    """Strictly parse one serialized spelling; never guess a default."""
    if isinstance(value, vocabulary):
        return value
    if value is None:
        raise EvidenceVocabularyError(
            f"{label} cannot be absent here; absence is not a vocabulary value"
        )
    if not isinstance(value, str):
        raise EvidenceVocabularyError(
            f"{label} must be a serialized string, got {type(value).__name__}"
        )
    if not value:
        raise EvidenceVocabularyError(f"{label} must be a non-empty string")
    try:
        return vocabulary(value)
    except ValueError:
        raise EvidenceVocabularyError(
            f"unknown {label} spelling {value!r}; expected one of "
            f"{tuple(m.value for m in vocabulary)}"
        ) from None


class EvidenceMode(_StrictVocabulary):
    """How a fact or transition is evidenced (Astra freeze ``evidence_modes``).

    Only the cited bounded fact/transition and its fully closed dependencies
    belong to ``NATIVE_EVIDENCED``.  ``REFERENCE_MODEL`` and
    ``SANDBOX_EXTENSION`` are explicit caller selections and never become
    native.  ``UNSUPPORTED`` permits descriptor inspection and denies
    execution; it is still not the same thing as "no mode".

    This enum carries no executability claim and exposes no boolean helper.
    """

    NATIVE_EVIDENCED = "NATIVE_EVIDENCED"
    REFERENCE_MODEL = "REFERENCE_MODEL"
    SANDBOX_EXTENSION = "SANDBOX_EXTENSION"
    UNSUPPORTED = "UNSUPPORTED"


class VersionRelation(_StrictVocabulary):
    """How a source version relates to the target version.

    ``EXACT_NATIVE`` means the representation came from the exact native source
    version.  ``CLOSE_VERSION`` means a close but non-identical version, as the
    freeze records with ``CLOSE_4.4.0_TO_4.4.54``.  The two are separate
    members and never compare or merge as equal, which is what the frozen
    strict rejection ``SOURCE_VERSION_CLOSENESS_PROMOTED_TO_EXACT_NATIVE_PROOF``
    forbids.

    An unasserted relation is represented by an absent provenance field.  It is
    not an enum member: the freeze directly supports only exact-vs-close
    distinction, and absence must remain observable rather than acquire an
    invented serialized spelling.
    """

    EXACT_NATIVE = "EXACT_NATIVE"
    CLOSE_VERSION = "CLOSE_VERSION"


class ReadinessClass(_StrictVocabulary):
    """What may be implemented or represented (Astra freeze ``readiness_classes``).

    A distinct type from :class:`EvidenceMode` on purpose.  Readiness answers
    "what may we do", evidence answers "how do we know".  Collapsing them would
    let a reference-evidenced object claim implementation permission, or let an
    implementable object claim native evidence.
    """

    SAFE_TO_IMPLEMENT = "SAFE_TO_IMPLEMENT"
    SAFE_TO_REPRESENT_ONLY = "SAFE_TO_REPRESENT_ONLY"
    SAFE_REFERENCE_MODEL_ONLY = "SAFE_REFERENCE_MODEL_ONLY"
    STRICT_REJECT_UNTIL_NEW_EVIDENCE = "STRICT_REJECT_UNTIL_NEW_EVIDENCE"


EVIDENCE_MODE_SPELLINGS: tuple[str, ...] = EvidenceMode.spellings()
VERSION_RELATION_SPELLINGS: tuple[str, ...] = VersionRelation.spellings()
READINESS_CLASS_SPELLINGS: tuple[str, ...] = ReadinessClass.spellings()


def parse_evidence_mode(value: Any) -> EvidenceMode:
    """Strictly parse a serialized evidence mode."""
    return _parse(EvidenceMode, value, "EvidenceMode")


def parse_version_relation(value: Any) -> VersionRelation:
    """Strictly parse a serialized version relation."""
    return _parse(VersionRelation, value, "VersionRelation")


def parse_readiness_class(value: Any) -> ReadinessClass:
    """Strictly parse a serialized readiness class."""
    return _parse(ReadinessClass, value, "ReadinessClass")


def _assert_round_trip(vocabulary: Iterable[_StrictVocabulary]) -> None:
    """Import-time guard: every spelling must parse back to its own member."""
    for member in vocabulary:
        parsed = type(member)(member.value)
        if parsed is not member:
            raise EvidenceVocabularyError(
                f"{type(member).__name__}.{member.name} failed identity "
                "round trip"
            )


_assert_round_trip(EvidenceMode)
_assert_round_trip(VersionRelation)
_assert_round_trip(ReadinessClass)


# ---------------------------------------------------------------------------
# ContractRef (F01-003)
# ---------------------------------------------------------------------------

CONTRACT_REF_SCHEMA = "contract_ref/1"

_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")

#: Contract-identity fields that must be present and non-empty.
REQUIRED_CONTRACT_REF_FIELDS: tuple[str, ...] = (
    "contract_id",
    "namespace",
    "schema_version",
    "evidence_mode",
    "content_sha256",
)


def _require_token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceVocabularyError(f"{label} must be a non-empty string")
    return value


def _require_sha256(value: Any, label: str) -> str:
    text = _require_token(value, label)
    if not _SHA256_RE.match(text):
        raise EvidenceVocabularyError(
            f"{label} must be 64 lowercase hexadecimal characters, got {text!r}"
        )
    return text


@dataclass(frozen=True)
class ContractRef:
    """Identity and provenance of a semantic contract.

    A ``ContractRef`` answers "which contract is this, from where, and how is it
    evidenced".  It is **not** a permission to execute: it exposes no
    ``executable`` helper, its ``evidence_mode`` is a provenance classification,
    and an evidence mode of ``NATIVE_EVIDENCED`` still says nothing about whether
    any particular runtime request is supported.

    Required identity fields: ``contract_id``, ``namespace``, ``schema_version``,
    ``evidence_mode`` and ``content_sha256``.  ``source_refs`` may be empty, but
    it is always present as a tuple so absence and emptiness stay distinguishable
    from a missing field.
    """

    contract_id: str
    namespace: str
    schema_version: str
    evidence_mode: EvidenceMode
    content_sha256: str
    source_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_id", _require_token(self.contract_id, "contract_id")
        )
        object.__setattr__(
            self, "namespace", _require_token(self.namespace, "namespace")
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_token(self.schema_version, "schema_version"),
        )
        object.__setattr__(
            self,
            "content_sha256",
            _require_sha256(self.content_sha256, "content_sha256"),
        )
        if not isinstance(self.evidence_mode, EvidenceMode):
            object.__setattr__(
                self,
                "evidence_mode",
                parse_evidence_mode(self.evidence_mode),
            )
        if isinstance(self.source_refs, str) or not isinstance(
            self.source_refs, (tuple, list)
        ):
            raise EvidenceVocabularyError(
                "source_refs must be a tuple or list of reference strings"
            )
        object.__setattr__(
            self,
            "source_refs",
            tuple(_require_token(ref, "source_refs entry") for ref in self.source_refs),
        )

    # -- identity helpers ------------------------------------------------

    def matches_mode(self, expected: Any) -> bool:
        """True when this contract's evidence mode is exactly ``expected``."""
        return self.evidence_mode is parse_evidence_mode(expected)

    def require_mode(self, expected: Any, *, role: str = "contract") -> "ContractRef":
        """Return self only when the evidence mode matches exactly, else raise.

        This is the mode-mismatch detector: a reference-evidenced contract can
        never satisfy a native-evidenced expectation, and vice versa.
        """
        wanted = parse_evidence_mode(expected)
        if self.evidence_mode is not wanted:
            raise EvidenceVocabularyError(
                f"{role} {self.contract_id!r} ({self.namespace}) carries evidence "
                f"mode {self.evidence_mode.value}, expected {wanted.value}"
            )
        return self

    def identity(self) -> str:
        """Stable contract identity string (audit only, never dispatch)."""
        return (
            f"{self.namespace}:{self.contract_id}@{self.schema_version}"
            f"#{self.content_sha256}"
        )

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CONTRACT_REF_SCHEMA,
            "contract_id": self.contract_id,
            "namespace": self.namespace,
            "schema_version": self.schema_version,
            "evidence_mode": self.evidence_mode.value,
            "content_sha256": self.content_sha256,
            "source_refs": list(self.source_refs),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ContractRef":
        if not isinstance(data, Mapping):
            raise EvidenceVocabularyError(
                f"ContractRef document must be a mapping, got {type(data).__name__}"
            )
        schema = data.get("schema", CONTRACT_REF_SCHEMA)
        if schema != CONTRACT_REF_SCHEMA:
            raise EvidenceVocabularyError(
                f"unknown ContractRef schema {schema!r}; expected "
                f"{CONTRACT_REF_SCHEMA!r}"
            )
        missing = [
            name for name in REQUIRED_CONTRACT_REF_FIELDS if name not in data
        ]
        if missing:
            raise EvidenceVocabularyError(
                f"ContractRef is missing required fields {missing}"
            )
        source_refs = data.get("source_refs", ())
        if isinstance(source_refs, str) or not isinstance(
            source_refs, (tuple, list)
        ):
            raise EvidenceVocabularyError(
                "ContractRef.source_refs must be a tuple or list of strings"
            )
        return cls(
            contract_id=data["contract_id"],
            namespace=data["namespace"],
            schema_version=data["schema_version"],
            evidence_mode=data["evidence_mode"],
            content_sha256=data["content_sha256"],
            source_refs=tuple(source_refs),
        )


# ---------------------------------------------------------------------------
# UnknownHandle (F01-004)
# ---------------------------------------------------------------------------

UNKNOWN_HANDLE_SCHEMA = "unknown_handle/1"

#: Everything an unknown handle must state.  ``provenance`` may be a mapping or
#: a provenance-like object that exposes a mapping ``to_dict()``.
REQUIRED_UNKNOWN_HANDLE_FIELDS: tuple[str, ...] = (
    "blocker_id",
    "owner_family",
    "payload",
    "provenance",
    "required_evidence",
)


def _lossless_identity_node(value: Any, *, label: str) -> Any:
    """Type-tag a supported opaque value without normalizing its identity."""
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceVocabularyError(f"{label} contains a non-finite float")
        return ["float", value.hex()]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, list):
        return [
            "list",
            [
                _lossless_identity_node(item, label=f"{label}[{index}]")
                for index, item in enumerate(value)
            ],
        ]
    if isinstance(value, tuple):
        return [
            "tuple",
            [
                _lossless_identity_node(item, label=f"{label}[{index}]")
                for index, item in enumerate(value)
            ],
        ]
    if isinstance(value, Mapping):
        items: list[list[Any]] = []
        keys = list(value)
        for key in keys:
            if not isinstance(key, str):
                raise EvidenceVocabularyError(
                    f"{label} mapping keys must be strings, got "
                    f"{type(key).__name__}"
                )
        for key in sorted(keys):
            items.append(
                [key, _lossless_identity_node(value[key], label=f"{label}.{key}")]
            )
        return ["mapping", items]
    raise EvidenceVocabularyError(
        f"{label} contains unsupported {type(value).__name__}; expected "
        "None/bool/int/finite float/str/list/tuple/mapping with string keys"
    )


def _canonical_payload_text(value: Any, *, label: str) -> str:
    """Canonical type-tagged text for identity hashing and validation."""
    try:
        return json.dumps(
            _lossless_identity_node(value, label=label),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise EvidenceVocabularyError(
            f"{label} must be losslessly serializable for identity hashing: {exc}"
        ) from exc


@dataclass(frozen=True)
class UnknownHandle:
    """An explicitly unresolved blocker, carried without resolution.

    The handle states *what* is unknown (``blocker_id``), *who owns* resolving it
    (``owner_family``), *where it came from* (``provenance``), *what evidence
    would close it* (``required_evidence``), and it preserves the
    ``payload`` byte-for-byte so no information is lost by carrying it.

    UNKNOWN stays UNKNOWN.  A handle deliberately provides:

    * no ``is_executable`` / ``can_execute`` / truthiness shortcut;
    * no fallback value, default or guessed semantics;
    * no conversion into a :class:`ContractRef` — :meth:`as_contract_ref` refuses
      and :func:`require_contract_ref` rejects a handle outright.

    ``provenance`` is typed structurally rather than importing
    ``battle_ir.provenance``, because that module imports from this one.
    """

    blocker_id: str
    owner_family: str
    payload: Any
    provenance: Any
    required_evidence: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "blocker_id", _require_token(self.blocker_id, "blocker_id")
        )
        object.__setattr__(
            self, "owner_family", _require_token(self.owner_family, "owner_family")
        )
        if self.provenance is None:
            raise EvidenceVocabularyError(
                "UnknownHandle.provenance must be present; a handle must state "
                "where the unresolved material came from"
            )
        if not self._is_provenance_like(self.provenance):
            raise EvidenceVocabularyError(
                "UnknownHandle.provenance must be a mapping or expose a "
                "mapping to_dict()"
            )
        # Store one stable serialized provenance representation.  This is a
        # lossless boundary operation, not an equality convenience: keys are
        # never coerced and nested values are copied and type-validated.
        to_dict = getattr(self.provenance, "to_dict", None)
        if callable(to_dict):
            serialized_provenance = to_dict()
        else:
            serialized_provenance = self.provenance
        if not isinstance(serialized_provenance, Mapping):
            raise EvidenceVocabularyError(
                "UnknownHandle.provenance.to_dict() must return a mapping"
            )
        _canonical_payload_text(
            serialized_provenance, label="UnknownHandle.provenance"
        )
        object.__setattr__(
            self, "provenance", copy.deepcopy(dict(serialized_provenance))
        )
        if isinstance(self.required_evidence, str) or not isinstance(
            self.required_evidence, (tuple, list)
        ):
            raise EvidenceVocabularyError(
                "required_evidence must be a tuple or list of evidence requests"
            )
        object.__setattr__(
            self,
            "required_evidence",
            tuple(
                _require_token(item, "required_evidence entry")
                for item in self.required_evidence
            ),
        )
        # The payload is validated for lossless encodability but never coerced,
        # defaulted or interpreted.  It is deep-copied so the model never shares
        # mutable state with its caller.
        _canonical_payload_text(self.payload, label="UnknownHandle.payload")
        object.__setattr__(self, "payload", copy.deepcopy(self.payload))

    @staticmethod
    def _is_provenance_like(value: Any) -> bool:
        return isinstance(value, Mapping) or callable(getattr(value, "to_dict", None))

    # -- identity --------------------------------------------------------

    def identity_hash(self) -> str:
        """Stable hash of every decision-relevant unresolved identity field."""
        document = {
            "blocker_id": self.blocker_id,
            "owner_family": self.owner_family,
            "payload": self.payload,
            "provenance": self.provenance,
            "required_evidence": list(self.required_evidence),
        }
        text = _canonical_payload_text(document, label="UnknownHandle identity")
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # -- explicit refusal -------------------------------------------------

    def as_contract_ref(self) -> "ContractRef":
        """Refuse: an unresolved handle is not a contract."""
        raise EvidenceVocabularyError(
            f"UnknownHandle {self.blocker_id!r} is unresolved and can never "
            "satisfy a ContractRef; resolve the required evidence first"
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": UNKNOWN_HANDLE_SCHEMA,
            "blocker_id": self.blocker_id,
            "owner_family": self.owner_family,
            "payload": copy.deepcopy(self.payload),
            "provenance": self._serialize_provenance(),
            "required_evidence": list(self.required_evidence),
        }

    def _serialize_provenance(self) -> Any:
        to_dict = getattr(self.provenance, "to_dict", None)
        if callable(to_dict):
            return copy.deepcopy(to_dict())
        return copy.deepcopy(self.provenance)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "UnknownHandle":
        if not isinstance(data, Mapping):
            raise EvidenceVocabularyError(
                f"UnknownHandle document must be a mapping, got "
                f"{type(data).__name__}"
            )
        schema = data.get("schema", UNKNOWN_HANDLE_SCHEMA)
        if schema != UNKNOWN_HANDLE_SCHEMA:
            raise EvidenceVocabularyError(
                f"unknown UnknownHandle schema {schema!r}; expected "
                f"{UNKNOWN_HANDLE_SCHEMA!r}"
            )
        missing = [
            name for name in REQUIRED_UNKNOWN_HANDLE_FIELDS if name not in data
        ]
        if missing:
            raise EvidenceVocabularyError(
                f"UnknownHandle is missing required fields {missing}"
            )
        required_evidence = data.get("required_evidence", ())
        if isinstance(required_evidence, str) or not isinstance(
            required_evidence, (tuple, list)
        ):
            raise EvidenceVocabularyError(
                "UnknownHandle.required_evidence must be a tuple or list"
            )
        return cls(
            blocker_id=data["blocker_id"],
            owner_family=data["owner_family"],
            payload=copy.deepcopy(data["payload"]),
            provenance=copy.deepcopy(data["provenance"]),
            required_evidence=tuple(required_evidence),
        )


def require_contract_ref(value: Any, *, role: str = "value") -> ContractRef:
    """Return ``value`` only when it is a genuine :class:`ContractRef`.

    An :class:`UnknownHandle` is always rejected: an unresolved blocker must
    never be mistaken for a resolved contract.
    """
    if isinstance(value, UnknownHandle):
        raise EvidenceVocabularyError(
            f"{role}: UnknownHandle {value.blocker_id!r} is unresolved and "
            "cannot satisfy a ContractRef"
        )
    if not isinstance(value, ContractRef):
        raise EvidenceVocabularyError(
            f"{role}: expected a ContractRef, got {type(value).__name__}"
        )
    return value
