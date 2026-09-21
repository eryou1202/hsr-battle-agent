# -*- coding: utf-8 -*-
"""Resolution ledger: explicit EXACT / MISSING / AMBIGUOUS / BLOCKED states.

TERRA R01-001.  This module is **representation only**.  It consumes the already
published content/behavior mapping report and turns each entry's recorded static
link into an explicit resolution state with a provenance record.  It does not
re-derive, re-join or re-interpret any mapping: every fact below comes verbatim
from the mapping document.

Input contract
--------------

The ledger reads ``record_links`` from a mapping report
(``full_content_behavior_mapping_001.json`` or
``content_behavior_mapping_001.json``).  Each record carries
``static_link.classification``, whose authoritative meanings are recorded in the
same document under ``link_classifications``:

``EXACT_ID``
    literal source owner reference equals an exact local static entity ID.
``EXACT_CONFIG_ID``
    an unambiguous numeric config token equals exactly one static entity ID.
``STRUCTURED_MAPPING``
    a separately recorded source relationship joins a behavior record to an
    exact local static entity.
``REPRESENTATION_TRANSFORM_CANDIDATE``
    a cached StarRailRes tag/filename relation; explicitly **not** native-ID
    proof.
``PARENT_AVATAR_ONLY``
    source name indicates the shape but does not identify the static entity ID.
``UNMAPPED``
    source path/name identifies a behavior family but has no exact static
    entity relation.
``OUT_OF_STATIC_FAMILY_SCOPE``
    captured global behavior has no corresponding requested static-content
    family.

State policy (a declaration, not an inference)
---------------------------------------------

============  ===========================================================
``EXACT``     an exact-relation classification with exactly one candidate.
``AMBIGUOUS`` more than one candidate: no single value may be exposed.
``MISSING``   no exact static entity relation is asserted.
``BLOCKED``   resolution is impossible against the requested scope, or the
              recorded classification is not one this ledger understands.
============  ===========================================================

Hard rules enforced here:

* ``AMBIGUOUS`` never exposes a resolved value, and ``require_resolved()``
  refuses for every state except ``EXACT``.
* ``MISSING``, ``AMBIGUOUS`` and ``BLOCKED`` are three distinct states and are
  never collapsed into one generic failure; an unrecognised classification
  becomes ``BLOCKED`` with a reason code rather than being guessed into
  ``MISSING``.
* Every unresolved state carries a :class:`UnknownHandle`, so the blocker, its
  owner family, the recorded payload and the required evidence all travel with
  the entry.
* ``EXACT`` records that the *static link* is exact.  It says nothing about
  executability: the ledger exposes no executable helper, and
  :meth:`ResolutionLedgerEntry.execution_permitted` refuses.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import (
    EvidenceVocabularyError,
    UnknownHandle,
)

__all__ = [
    "AMBIGUOUS_CLASSIFICATIONS",
    "BLOCKED_CLASSIFICATIONS",
    "EXACT_CLASSIFICATIONS",
    "MISSING_CLASSIFICATIONS",
    "RESOLUTION_LEDGER_SCHEMA",
    "RESOLUTION_STATES",
    "ResolutionLedger",
    "ResolutionLedgerEntry",
    "ResolutionLedgerError",
    "ResolutionProvenance",
    "ResolutionState",
]

RESOLUTION_LEDGER_SCHEMA = "resolution_ledger/1"

#: Classifications whose meaning is "this is an exact local static entity
#: relation", verbatim from the mapping document's own vocabulary.
EXACT_CLASSIFICATIONS: tuple[str, ...] = (
    "EXACT_ID",
    "EXACT_CONFIG_ID",
    "STRUCTURED_MAPPING",
)

#: Classifications that assert no exact static entity relation.
MISSING_CLASSIFICATIONS: tuple[str, ...] = (
    "UNMAPPED",
    "PARENT_AVATAR_ONLY",
    "REPRESENTATION_TRANSFORM_CANDIDATE",
)

#: Classifications that block resolution against the requested scope.
BLOCKED_CLASSIFICATIONS: tuple[str, ...] = ("OUT_OF_STATIC_FAMILY_SCOPE",)

AMBIGUOUS_CLASSIFICATIONS: tuple[str, ...] = ()

#: Reason codes for BLOCKED entries.  Stable machine codes, never message text.
REASON_OUT_OF_STATIC_FAMILY_SCOPE = "OUT_OF_STATIC_FAMILY_SCOPE"
REASON_UNRECOGNISED_CLASSIFICATION = "UNRECOGNISED_MAPPING_CLASSIFICATION"
REASON_MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATE_STATIC_ENTITIES"
REASON_NO_CANDIDATE_RECORDED = "NO_CANDIDATE_STATIC_ENTITY_RECORDED"

#: Source-reference keys the mapping records.  Anything absent stays absent.
SOURCE_REF_FIELDS: tuple[str, ...] = (
    "repository",
    "commit",
    "path",
    "raw_sha256",
    "version_relation",
)

#: The frozen close-version marker prefix recorded by the mapping.
_FROZEN_CLOSE_PREFIX = "CLOSE_"


class ResolutionLedgerError(ValueError):
    """Raised for a malformed ledger entry or an illegal state transition."""


class ResolutionState(Enum):
    """The four resolution states.  Deliberately not a ``str`` mixin.

    ``__bool__`` refuses, so a state can never be used as a truthy "resolved"
    or "executable" shortcut.
    """

    EXACT = "EXACT"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    BLOCKED = "BLOCKED"

    def __bool__(self) -> NoReturn:
        raise ResolutionLedgerError(
            f"ResolutionState.{self.name} is a classification, not a boolean; "
            "compare it with is and use is_exact()/is_unresolved()"
        )

    def serialize(self) -> str:
        return str(self.value)

    @classmethod
    def spellings(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)


RESOLUTION_STATES: tuple[str, ...] = ResolutionState.spellings()


def _parse_state(value: Any) -> ResolutionState:
    if isinstance(value, ResolutionState):
        return value
    if value is None or not isinstance(value, str):
        raise ResolutionLedgerError(
            f"resolution state must be a serialized string, got "
            f"{type(value).__name__}"
        )
    try:
        return ResolutionState(value)
    except ValueError:
        raise ResolutionLedgerError(
            f"unknown resolution state {value!r}; expected one of "
            f"{RESOLUTION_STATES}"
        ) from None


def _require_non_empty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResolutionLedgerError(f"{label} must be a non-empty string")
    return value


@dataclass(frozen=True)
class ResolutionProvenance:
    """Provenance for a resolution entry, recorded verbatim.

    Every value here is copied from the mapping document.  Nothing is filled in:
    a field the mapping did not record stays absent, and
    :meth:`absent_field_names` reports it.  No native claim is made.
    """

    fields: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.fields, Mapping):
            raise ResolutionLedgerError(
                "ResolutionProvenance.fields must be a mapping"
            )
        copied: dict[str, Any] = {}
        for key, value in self.fields.items():
            if not isinstance(key, str):
                raise ResolutionLedgerError(
                    "ResolutionProvenance field names must be strings; "
                    "keys are never coerced"
                )
            copied[key] = copy.deepcopy(value)
        object.__setattr__(self, "fields", copied)

    def has(self, name: str) -> bool:
        return name in self.fields

    def value(self, name: str) -> Any:
        """Return the recorded value, or raise.  Never supplies a default."""
        if name not in self.fields:
            raise ResolutionLedgerError(
                f"provenance field {name!r} was not recorded; there is no "
                "default and no fallback"
            )
        return self.fields[name]

    def recorded_names(self) -> tuple[str, ...]:
        return tuple(self.fields)

    def absent_field_names(self) -> frozenset[str]:
        return frozenset(
            name
            for name in SOURCE_REF_FIELDS
            if f"source_ref.{name}" not in self.fields
        )

    def to_dict(self) -> dict[str, Any]:
        return {"fields": copy.deepcopy(dict(self.fields))}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResolutionProvenance":
        if not isinstance(data, Mapping):
            raise ResolutionLedgerError(
                "ResolutionProvenance document must be a mapping"
            )
        if "fields" not in data:
            raise ResolutionLedgerError(
                "ResolutionProvenance document is missing the 'fields' key"
            )
        return cls(fields=data["fields"])

    @classmethod
    def from_mapping_record(
        cls, record: Mapping[str, Any], document: Mapping[str, Any] | None = None
    ) -> "ResolutionProvenance":
        """Build provenance from a mapping record without inventing anything."""
        fields: dict[str, Any] = {}
        if document is not None:
            for name in ("report_id", "report_sha256", "game_version"):
                if name in document:
                    fields[name] = document[name]
            inputs = document.get("inputs")
            if isinstance(inputs, Mapping):
                # Record the mapping's own input digests verbatim; no field is
                # invented and nothing absent is filled in.
                for name in inputs:
                    if isinstance(name, str) and name.endswith("_sha256"):
                        fields[f"inputs.{name}"] = inputs[name]
        static_link = record.get("static_link")
        if isinstance(static_link, Mapping) and "static_family" in static_link:
            fields["static_family"] = static_link["static_family"]
        source_ref = record.get("source_ref")
        if isinstance(source_ref, Mapping):
            for name in SOURCE_REF_FIELDS:
                if name in source_ref:
                    fields[f"source_ref.{name}"] = source_ref[name]
        return cls(fields=fields)


def _required_evidence_for(classification: str, reason_code: str) -> str:
    """The evidence request that would close an unresolved entry.

    Derived from the mapping document's own wording for each classification; no
    new semantic claim is introduced.
    """
    if reason_code == REASON_MULTIPLE_CANDIDATES:
        return (
            "disambiguation to exactly one local static entity id; the mapping "
            "recorded more than one candidate"
        )
    if reason_code == REASON_UNRECOGNISED_CLASSIFICATION:
        return (
            f"a supported mapping link classification for {classification!r}; "
            "the ledger refuses to guess a state"
        )
    if reason_code == REASON_NO_CANDIDATE_RECORDED:
        return (
            "an exact local static entity id; the record claims an exact "
            "relation but recorded no candidate"
        )
    if classification == "REPRESENTATION_TRANSFORM_CANDIDATE":
        return (
            "native-ID proof for the behavior record; a cached StarRailRes "
            "tag/filename relation is explicitly not native-ID proof"
        )
    if classification == "PARENT_AVATAR_ONLY":
        return (
            "the static entity id itself; the source name only indicates the "
            "record shape"
        )
    if classification == "UNMAPPED":
        return "an exact static entity relation for this behavior record"
    if classification == "OUT_OF_STATIC_FAMILY_SCOPE":
        return (
            "a requested static-content family corresponding to this captured "
            "global behavior record"
        )
    return f"an exact static entity relation for classification {classification!r}"


def classify_record(record: Mapping[str, Any]) -> tuple[ResolutionState, str | None]:
    """Derive the resolution state and BLOCKED reason code for one record.

    Pure function over the recorded classification and candidate list.  It never
    inspects behavior payloads and never re-derives a join.
    """
    static_link = record.get("static_link")
    if not isinstance(static_link, Mapping) or "classification" not in static_link:
        return ResolutionState.BLOCKED, REASON_UNRECOGNISED_CLASSIFICATION
    classification = static_link["classification"]
    if not isinstance(classification, str) or not classification:
        return ResolutionState.BLOCKED, REASON_UNRECOGNISED_CLASSIFICATION

    candidates = static_link.get("candidate_entity_ids", ())
    if isinstance(candidates, (str, bytes)) or not isinstance(
        candidates, (tuple, list)
    ):
        return ResolutionState.BLOCKED, REASON_UNRECOGNISED_CLASSIFICATION

    if classification in EXACT_CLASSIFICATIONS:
        if len(candidates) == 1:
            return ResolutionState.EXACT, None
        if len(candidates) > 1:
            return ResolutionState.AMBIGUOUS, REASON_MULTIPLE_CANDIDATES
        return ResolutionState.MISSING, REASON_NO_CANDIDATE_RECORDED

    if classification in MISSING_CLASSIFICATIONS:
        return ResolutionState.MISSING, None

    if classification in BLOCKED_CLASSIFICATIONS:
        return ResolutionState.BLOCKED, REASON_OUT_OF_STATIC_FAMILY_SCOPE

    return ResolutionState.BLOCKED, REASON_UNRECOGNISED_CLASSIFICATION


@dataclass(frozen=True)
class ResolutionLedgerEntry:
    """One behavior record's resolution state, plus provenance and blocker."""

    behavior_id: str
    state: ResolutionState
    classification: str
    owner_kind: str
    static_family: str | None
    candidate_entity_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence: str = ""
    mapping_method: str = ""
    representation_tag: str | None = None
    resolved_entity_id: str | None = None
    reason_code: str | None = None
    provenance: ResolutionProvenance = field(
        default_factory=ResolutionProvenance
    )
    unknown_handle: UnknownHandle | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "behavior_id", _require_non_empty(self.behavior_id, "behavior_id")
        )
        object.__setattr__(self, "state", _parse_state(self.state))
        if isinstance(self.candidate_entity_ids, str) or not isinstance(
            self.candidate_entity_ids, (tuple, list)
        ):
            raise ResolutionLedgerError(
                "candidate_entity_ids must be a tuple or list of id strings"
            )
        object.__setattr__(
            self,
            "candidate_entity_ids",
            tuple(
                _require_non_empty(item, "candidate_entity_ids entry")
                for item in self.candidate_entity_ids
            ),
        )
        if not isinstance(self.provenance, ResolutionProvenance):
            raise ResolutionLedgerError(
                "provenance must be a ResolutionProvenance"
            )

        if self.state is ResolutionState.EXACT:
            if self.resolved_entity_id is None:
                raise ResolutionLedgerError(
                    "EXACT must expose exactly one resolved entity id"
                )
            if self.resolved_entity_id not in self.candidate_entity_ids:
                raise ResolutionLedgerError(
                    "EXACT resolved_entity_id must be the recorded candidate"
                )
            if len(self.candidate_entity_ids) != 1:
                raise ResolutionLedgerError(
                    "EXACT requires exactly one recorded candidate"
                )
            if self.unknown_handle is not None:
                raise ResolutionLedgerError(
                    "EXACT is resolved and must not carry an UnknownHandle"
                )
        else:
            if self.resolved_entity_id is not None:
                raise ResolutionLedgerError(
                    f"{self.state.value} must not expose a resolved value"
                )
            if self.unknown_handle is None:
                raise ResolutionLedgerError(
                    f"{self.state.value} must carry an UnknownHandle"
                )
            if not isinstance(self.unknown_handle, UnknownHandle):
                raise ResolutionLedgerError(
                    "unknown_handle must be an UnknownHandle"
                )
        if self.state is ResolutionState.BLOCKED and not self.reason_code:
            raise ResolutionLedgerError("BLOCKED must record an explicit reason")

    # -- state queries ---------------------------------------------------

    def is_exact(self) -> bool:
        return self.state is ResolutionState.EXACT

    def is_missing(self) -> bool:
        return self.state is ResolutionState.MISSING

    def is_ambiguous(self) -> bool:
        return self.state is ResolutionState.AMBIGUOUS

    def is_blocked(self) -> bool:
        return self.state is ResolutionState.BLOCKED

    def is_unresolved(self) -> bool:
        return self.state is not ResolutionState.EXACT

    def require_resolved(self) -> str:
        """Return the resolved id, or raise.  Never guesses or falls back."""
        if self.state is not ResolutionState.EXACT:
            raise ResolutionLedgerError(
                f"entry {self.behavior_id!r} is {self.state.value} and exposes "
                "no resolved value; there is no default"
            )
        assert self.resolved_entity_id is not None
        return self.resolved_entity_id

    def execution_permitted(self) -> NoReturn:
        """Refuse: an exact static link is not native executability."""
        raise ResolutionLedgerError(
            f"entry {self.behavior_id!r} is {self.state.value}; an exact static "
            "link is representation evidence and never implies native "
            "executability"
        )

    def __bool__(self) -> NoReturn:
        raise ResolutionLedgerError(
            "ResolutionLedgerEntry has no truthiness; inspect its state "
            "explicitly"
        )

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "behavior_id": self.behavior_id,
            "state": self.state.value,
            "classification": self.classification,
            "owner_kind": self.owner_kind,
            "static_family": self.static_family,
            "candidate_entity_ids": list(self.candidate_entity_ids),
            "evidence": self.evidence,
            "mapping_method": self.mapping_method,
            "representation_tag": copy.deepcopy(self.representation_tag),
            "provenance": self.provenance.to_dict(),
        }
        if self.resolved_entity_id is not None:
            payload["resolved_entity_id"] = self.resolved_entity_id
        if self.reason_code is not None:
            payload["reason_code"] = self.reason_code
        if self.unknown_handle is not None:
            payload["unknown_handle"] = self.unknown_handle.to_dict()
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResolutionLedgerEntry":
        if not isinstance(data, Mapping):
            raise ResolutionLedgerError(
                f"ledger entry must be a mapping, got {type(data).__name__}"
            )
        for name in ("behavior_id", "state", "classification"):
            if name not in data:
                raise ResolutionLedgerError(
                    f"ledger entry is missing required field {name!r}"
                )
        handle = None
        if "unknown_handle" in data and data["unknown_handle"] is not None:
            try:
                handle = UnknownHandle.from_dict(data["unknown_handle"])
            except EvidenceVocabularyError as exc:
                raise ResolutionLedgerError(
                    f"invalid attached UnknownHandle: {exc}"
                ) from exc
        provenance = ResolutionProvenance()
        if "provenance" in data:
            provenance = ResolutionProvenance.from_dict(data["provenance"])
        return cls(
            behavior_id=data["behavior_id"],
            state=data["state"],
            classification=data["classification"],
            owner_kind=data["owner_kind"] if "owner_kind" in data else "",
            static_family=data["static_family"] if "static_family" in data else "",
            candidate_entity_ids=tuple(
                data["candidate_entity_ids"]
                if "candidate_entity_ids" in data
                else ()
            ),
            evidence=data["evidence"] if "evidence" in data else "",
            mapping_method=(
                data["mapping_method"] if "mapping_method" in data else ""
            ),
            representation_tag=(
                data["representation_tag"] if "representation_tag" in data else None
            ),
            resolved_entity_id=(
                data["resolved_entity_id"]
                if "resolved_entity_id" in data
                else None
            ),
            reason_code=(
                data["reason_code"] if "reason_code" in data else None
            ),
            provenance=provenance,
            unknown_handle=handle,
        )

    # -- construction from a mapping record ------------------------------

    @classmethod
    def from_mapping_record(
        cls, record: Mapping[str, Any], document: Mapping[str, Any] | None = None
    ) -> "ResolutionLedgerEntry":
        if not isinstance(record, Mapping):
            raise ResolutionLedgerError(
                "mapping record must be a mapping"
            )
        static_link = record.get("static_link")
        if not isinstance(static_link, Mapping):
            raise ResolutionLedgerError(
                "mapping record static_link must be a mapping"
            )
        classification = static_link.get("classification")
        if not isinstance(classification, str) or not classification:
            raise ResolutionLedgerError(
                "mapping record classification must be a non-empty string"
            )
        candidates_raw = static_link.get("candidate_entity_ids", ())
        if isinstance(candidates_raw, (str, bytes)) or not isinstance(
            candidates_raw, (tuple, list)
        ):
            raise ResolutionLedgerError(
                "mapping record candidate_entity_ids must be a tuple or list"
            )
        candidates = tuple(
            _require_non_empty(item, "candidate_entity_ids entry")
            for item in candidates_raw
        )
        state, reason = classify_record(record)

        owner_kind = record.get("owner_kind", "")
        static_family = static_link.get("static_family", "")
        evidence = static_link.get("evidence", "")
        mapping_method = static_link.get("mapping_method", "")
        representation_tag = static_link.get("representation_tag", None)
        behavior_id = _require_non_empty(record.get("behavior_id"), "behavior_id")

        for label, value in (
            ("owner_kind", owner_kind),
            ("evidence", evidence),
            ("mapping_method", mapping_method),
        ):
            if not isinstance(value, str):
                raise ResolutionLedgerError(
                    f"mapping record {label} must be a string when present"
                )
        if static_family is not None and not isinstance(static_family, str):
            raise ResolutionLedgerError(
                "mapping record static_family must be a string or null"
            )
        if representation_tag is not None and not isinstance(
            representation_tag, str
        ):
            raise ResolutionLedgerError(
                "mapping record representation_tag must be a string or null"
            )

        resolved_entity_id = candidates[0] if state is ResolutionState.EXACT else None

        handle = None
        if state is not ResolutionState.EXACT:
            owner_family = (
                static_family
                if isinstance(static_family, str) and static_family
                else (owner_kind if isinstance(owner_kind, str) and owner_kind else "UNKNOWN")
            )
            payload: dict[str, Any] = {
                "classification": classification,
                "candidate_entity_ids": list(candidates),
                "evidence": evidence,
                "mapping_method": mapping_method,
                "representation_tag": representation_tag,
                "static_family": static_family,
                "owner_kind": owner_kind,
                "source_ref_present": "source_ref" in record,
            }
            if "source_ref" in record:
                payload["source_ref"] = copy.deepcopy(record["source_ref"])
            handle = UnknownHandle(
                blocker_id=f"{classification or 'UNCLASSIFIED'}:{behavior_id}",
                owner_family=str(owner_family),
                payload=payload,
                provenance={
                    "resolution_state": state.value,
                    "reason_code": reason or "",
                    "report_id": (
                        document["report_id"]
                        if isinstance(document, Mapping)
                        and "report_id" in document
                        else ""
                    ),
                },
                required_evidence=(
                    _required_evidence_for(str(classification), reason or ""),
                ),
            )

        return cls(
            behavior_id=behavior_id,
            state=state,
            classification=classification,
            owner_kind=owner_kind,
            static_family=static_family,
            candidate_entity_ids=candidates,
            evidence=evidence,
            mapping_method=mapping_method,
            representation_tag=representation_tag,
            resolved_entity_id=resolved_entity_id,
            reason_code=reason,
            provenance=ResolutionProvenance.from_mapping_record(record, document),
            unknown_handle=handle,
        )


@dataclass(frozen=True)
class ResolutionLedger:
    """A ledger of resolution entries built from a published mapping report."""

    entries: tuple[ResolutionLedgerEntry, ...] = field(default_factory=tuple)
    report_id: str = ""
    report_sha256: str = ""
    game_version: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.entries, (str, bytes)) or not isinstance(
            self.entries, (tuple, list)
        ):
            raise ResolutionLedgerError("entries must be a tuple or list")
        for entry in self.entries:
            if not isinstance(entry, ResolutionLedgerEntry):
                raise ResolutionLedgerError(
                    "entries must be ResolutionLedgerEntry instances, got "
                    f"{type(entry).__name__}"
                )
        object.__setattr__(self, "entries", tuple(self.entries))

    # -- queries ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self.entries)

    def by_state(self, state: Any) -> tuple[ResolutionLedgerEntry, ...]:
        wanted = _parse_state(state)
        return tuple(e for e in self.entries if e.state is wanted)

    def counts(self) -> dict[str, int]:
        counts = {name: 0 for name in RESOLUTION_STATES}
        for entry in self.entries:
            counts[entry.state.value] += 1
        return counts

    def reasons(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.entries:
            if entry.reason_code:
                counts[entry.reason_code] = counts.get(entry.reason_code, 0) + 1
        return counts

    def get(self, behavior_id: str) -> ResolutionLedgerEntry:
        for entry in self.entries:
            if entry.behavior_id == behavior_id:
                return entry
        raise ResolutionLedgerError(
            f"no ledger entry for behavior_id {behavior_id!r}"
        )

    def require_resolved(self, behavior_id: str) -> str:
        return self.get(behavior_id).require_resolved()

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RESOLUTION_LEDGER_SCHEMA,
            "report_id": self.report_id,
            "report_sha256": self.report_sha256,
            "game_version": self.game_version,
            "counts": self.counts(),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResolutionLedger":
        if not isinstance(data, Mapping):
            raise ResolutionLedgerError(
                f"ledger document must be a mapping, got {type(data).__name__}"
            )
        schema = data["schema"] if "schema" in data else RESOLUTION_LEDGER_SCHEMA
        if schema != RESOLUTION_LEDGER_SCHEMA:
            raise ResolutionLedgerError(
                f"unknown ledger schema {schema!r}; expected "
                f"{RESOLUTION_LEDGER_SCHEMA!r}"
            )
        raw = data["entries"] if "entries" in data else []
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
            raise ResolutionLedgerError("entries must be a list")
        return cls(
            entries=tuple(
                ResolutionLedgerEntry.from_dict(item) for item in raw
            ),
            report_id=data["report_id"] if "report_id" in data else "",
            report_sha256=(
                data["report_sha256"] if "report_sha256" in data else ""
            ),
            game_version=data["game_version"] if "game_version" in data else "",
        )

    # -- construction from mapping output ---------------------------------

    @classmethod
    def from_mapping_document(cls, document: Mapping[str, Any]) -> "ResolutionLedger":
        """Build a ledger from a mapping report; performs no join of its own."""
        if not isinstance(document, Mapping):
            raise ResolutionLedgerError(
                f"mapping document must be a mapping, got {type(document).__name__}"
            )
        if "record_links" not in document:
            raise ResolutionLedgerError(
                "mapping document is missing 'record_links'; the ledger consumes "
                "existing mapping output only"
            )
        raw = document["record_links"]
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (tuple, list)):
            raise ResolutionLedgerError("record_links must be a list")
        return cls(
            entries=tuple(
                ResolutionLedgerEntry.from_mapping_record(record, document)
                for record in raw
            ),
            report_id=document["report_id"] if "report_id" in document else "",
            report_sha256=(
                document["report_sha256"] if "report_sha256" in document else ""
            ),
            game_version=(
                document["game_version"] if "game_version" in document else ""
            ),
        )

    @classmethod
    def from_mapping_path(cls, path: str | Path) -> "ResolutionLedger":
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_mapping_document(document)

    def digest(self) -> str:
        """Stable digest of the ledger's own state distribution (audit only)."""
        import hashlib

        text = json.dumps(
            {
                "report_id": self.report_id,
                "report_sha256": self.report_sha256,
                "counts": self.counts(),
                "reasons": self.reasons(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
