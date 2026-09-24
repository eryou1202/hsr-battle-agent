# -*- coding: utf-8 -*-
"""Exact import of the D5 / D8 / D9 followup ledgers (C02-001).

REPRESENTATION AND MAPPING ONLY.  This module reads the five already-present
followup artifacts and represents their recorded facts exactly.  It performs no
matching of its own: every relation it carries was already in the source
artifact, and every count it publishes is cross-checked against the artifact's
own rows, so the declared number and the rows can never drift apart silently.

The five artifacts are exactly the ones the frozen authority registers as
followups, each with ``native_execution_gain: 0``
(``astra_semantic_freeze_v1.json`` ``followup_registry``)::

    monster_ai_content_acquisition_001.json
    monster_ai_binding_ledger_001.json
    monster_ai_sequence_id_binding_001.json
    equipment_trace_eidolon_content_followup_001.json
    stage_environment_mode_content_followup_001.json

What this module deliberately does not do
-----------------------------------------

* **No fetch, no reconstruction, no HEAD refresh.**  Only the recorded artifacts
  are read; nothing is downloaded or re-derived from raw game data.
* **No new matching.**  There is no integer-coincidence, substring, prefix,
  suffix, normalization, nearest-id, same-index or inheritance-based join
  anywhere, and no helper that could perform one.  Relations come only from
  fields the source artifact already labelled (D8's ``EXACT_ID_EQUALITY`` and
  ``EXPLICIT_SOURCE_REFERENCE``, D5's ``EXACT`` / ``MISSING`` field statuses).
* **No collapse into one "supported" flag.**  Counts are kept **per metric with
  their own denominator under a verbatim path**, exactly as
  ``coverage_ledger.policy`` requires ("Never combine categories into one
  percentage; denominators and evidence modes are recorded per metric").  Paths
  are what make this safe: D8 carries ``EXACT = 4696`` for the Trace composite
  join and ``EXACT = 6458`` for the join ledger, and a single flat state key
  would silently overwrite one with the other.  There is deliberately no
  ``supported()``, ``is_supported()``, ``ready()`` or aggregate accessor.
* **No gate or execution surface.**  It imports neither the gate certificate
  producer nor a native contract type, and no type here can permit execution.
  An ``EXACT`` mapping is a mapping state, never permission.
* **No semantic inference.**  It does not infer an AI runtime winner, RNG
  policy, state predicate, target semantics, ``DefaultDSE`` meaning, AI
  commitment or execution (D5); activation, cumulative Eidolon thresholds, relic
  activation or inherited activation (D8); or native waves, wave progression,
  terminal policy, mode inheritance, environment behavior or a ``StageID``
  fallback (D9).
* **Absence stays absence.**  Where the source records that a path, hash or row
  is absent at the pinned commit, this module carries that absence and never
  substitutes another file, another row or a fallback value.

Evidence mode
-------------

The artifacts record no evidence mode of their own (no file in the semantics
directory declares one).  :data:`FOLLOWUP_EVIDENCE_MODE` states the
classification once as a declared constant, and every parser takes the mode as
an explicit argument, so the choice is never baked silently into the schema:

* all five are registered with ``native_execution_gain: 0``, so no mode may be
  ``NATIVE_EVIDENCED`` -- and a hard invariant rejects that mode outright;
* ``authority.precedence`` says historical compiler/mapping/reference labels are
  "evidence of their recorded scope, not native runtime permission";
* each artifact is a *named packet with explicit assumptions and exclusions*
  (D5 ``remaining_unknowns``, D8 ``strict_nonclaims``, D9 ``semantic_nonclaims``)
  and the version relation is ``CLOSE_4.4.0_TO_4.4.54``, never exact native.

Ownership and mutation isolation
--------------------------------

Following ``CR-R01-CLOSURE-REVIEW-20260922-001`` and
``CR-G01-001-RAW-ALIAS-20260923-001``, the representation each object owns is
private and every public name is a read-only property returning a detached,
revalidated copy.  The nested values here are arbitrary source payloads carried
inside :class:`PresenceValue`, so ``frozen=True`` alone would not protect them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, NoReturn, Sequence

from hsr_battle_agent.battle_ir.evidence import (
    EvidenceMode,
    EvidenceVocabularyError,
    parse_evidence_mode,
)
from hsr_battle_agent.battle_ir.lossless_value import (
    PresenceValue,
    PresenceValueError,
)
from hsr_battle_agent.battle_ir.provenance import (
    SourceProvenance,
    VersionRelation,
)

__all__ = [
    "FOLLOWUP_ARTIFACTS",
    "FOLLOWUP_EVIDENCE_MODE",
    "FOLLOWUP_LEDGER_SCHEMA",
    "FOLLOWUP_RECORD_SCHEMA",
    "PARSERS",
    "STAGE_COMMON_TEMPLATE_PATH",
    "TARGET_GAME_VERSION",
    "FollowupDomain",
    "FollowupFamily",
    "FollowupLedger",
    "FollowupLedgerError",
    "FollowupRecord",
    "FollowupState",
    "load_followup_ledgers",
    "parse_d5_binding_ledger",
    "parse_d5_content_acquisition",
    "parse_d5_sequence_id_binding",
    "parse_d8_content_followup",
    "parse_d9_content_followup",
    "parse_followup_state",
]

FOLLOWUP_LEDGER_SCHEMA = "followup_ledger/1"
FOLLOWUP_RECORD_SCHEMA = "followup_record/1"

#: The repository's declared target version.  This is the version being modelled,
#: not the version the source content came from: every artifact records
#: ``CLOSE_4.4.0_TO_4.4.54``, so the *source* version stays in provenance's
#: ``unknown_fields`` verbatim rather than overwriting this field.
TARGET_GAME_VERSION = "4.4.54"

#: The exact requested path whose absence D9 records at the pinned commit.
STAGE_COMMON_TEMPLATE_PATH = "Config/Level/StageCommonTemplate.json"

#: The freeze's single recorded close-version marker, and its canonical member.
CLOSE_VERSION_MARKER = "CLOSE_4.4.0_TO_4.4.54"

#: Every ``effective_precedence`` spelling D5's binding ledger records.
D5_PRECEDENCE_SPELLINGS = frozenset(
    {"EXACT_TEMPLATE_PATH_ONLY", "UNRESOLVED_PRECEDENCE"}
)


class FollowupLedgerError(ValueError):
    """Raised for a malformed, inconsistent or unsupported followup document."""


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

class FollowupDomain(Enum):
    """Which followup domain an artifact belongs to."""

    D5_MONSTER_AI = "D5_MONSTER_AI"
    D8_EQUIPMENT_TRACE_EIDOLON = "D8_EQUIPMENT_TRACE_EIDOLON"
    D9_STAGE_ENVIRONMENT_MODE = "D9_STAGE_ENVIRONMENT_MODE"

    def __bool__(self) -> NoReturn:
        raise FollowupLedgerError(
            f"FollowupDomain.{self.name} is a domain tag, not a boolean"
        )

    def serialize(self) -> str:
        return str(self.value)


class FollowupFamily(Enum):
    """The source list a record came from.

    A closed vocabulary -- one member per source list this module imports -- so
    an unrecognised family fails closed instead of becoming a generic bucket.
    It is deliberately not one "supported" dimension: ``ABSENT_ROW`` and
    ``REMAINING_GAP`` are how holes stay visible beside ``EXACT_JOIN``.
    """

    # D5 sequence-id binding
    MONSTER_SKILL_ROW = "MONSTER_SKILL_ROW"
    SEQUENCE_SOURCE = "SEQUENCE_SOURCE"
    SEQUENCE_OCCURRENCE = "SEQUENCE_OCCURRENCE"
    # D5 binding ledger
    TEMPLATE_RECORD = "TEMPLATE_RECORD"
    MONSTER_RECORD = "MONSTER_RECORD"
    MONSTER_BINDING = "MONSTER_BINDING"
    DUPLICATE_OVERRIDE_ELEMENT = "DUPLICATE_OVERRIDE_ELEMENT"
    # D5 content acquisition
    ACQUISITION_REQUEST = "ACQUISITION_REQUEST"
    # D8 content followup
    EXACT_JOIN = "EXACT_JOIN"
    BEHAVIOR_CANDIDATE = "BEHAVIOR_CANDIDATE"
    SKILL_ADD_LEVEL_EDGE = "SKILL_ADD_LEVEL_EDGE"
    ABSENT_ROW = "ABSENT_ROW"
    # D9 content followup
    SOURCE_REQUEST = "SOURCE_REQUEST"
    # D8 and D9
    REMAINING_GAP = "REMAINING_GAP"

    def __bool__(self) -> NoReturn:
        raise FollowupLedgerError(
            f"FollowupFamily.{self.name} is a family tag, not a boolean"
        )

    def serialize(self) -> str:
        return str(self.value)


class FollowupState(Enum):
    """A mapping or binding state, spelled exactly as the artifacts spell it.

    Every member occurs verbatim in at least one artifact -- as a per-row
    ``status``, an ``edge_status_legend`` entry, or a key of a declared count
    block.  Nothing is renamed, merged or reinterpreted, and the *zero-valued*
    spellings are members too: a declared count of zero for ``ROW_MISSING`` is a
    fact, and dropping the spelling would lose it.

    ``EXACT`` means a mapping is exact.  It does **not** mean executable, and
    there is deliberately no predicate on this enum -- no ``is_exact()``, no
    ``is_supported()``, no ``executable()``, no truthiness.
    """

    # -- per-row status and legend spellings --
    EXACT = "EXACT"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"
    UNRESOLVED_PRECEDENCE = "UNRESOLVED_PRECEDENCE"
    ABSENT_AT_PINNED_COMMIT = "ABSENT_AT_PINNED_COMMIT"
    NOT_INSPECTED_OUT_OF_SCOPE = "NOT_INSPECTED_OUT_OF_SCOPE"
    BLOCKED_BY_CONTENT_COVERAGE = "BLOCKED_BY_CONTENT_COVERAGE"
    STILL_CONTENT_BLOCKED = "STILL_CONTENT_BLOCKED"
    SOURCE_VERSION_LIMITED = "SOURCE_VERSION_LIMITED"
    EXCLUDED_BY_TICKET = "EXCLUDED_BY_TICKET"
    # -- declared count keys, including the zero-valued ones --
    ROW_MISSING = "ROW_MISSING"
    SKILL_TRIGGER_KEY_MISSING = "SKILL_TRIGGER_KEY_MISSING"
    CHARACTER_SKILL_MISSING = "CHARACTER_SKILL_MISSING"
    EXACT_EXISTING_DEFINITION = "EXACT_EXISTING_DEFINITION"
    MISSING_DEFINITION = "MISSING_DEFINITION"
    AMBIGUOUS_DEFINITION = "AMBIGUOUS_DEFINITION"

    def __bool__(self) -> NoReturn:
        raise FollowupLedgerError(
            f"FollowupState.{self.name} is a mapping classification, not a "
            "boolean, not a permission and not an executability flag"
        )

    def serialize(self) -> str:
        return str(self.value)

    @classmethod
    def spellings(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)


#: The mode these artifacts may never carry (``native_execution_gain: 0``).
FORBIDDEN_EVIDENCE_MODE = EvidenceMode.NATIVE_EVIDENCED

#: See the module docstring for the grounding of this single declared choice.
FOLLOWUP_EVIDENCE_MODE = EvidenceMode.REFERENCE_MODEL

#: Artifact names per domain, in the freeze's registry order.
FOLLOWUP_ARTIFACTS: Mapping[FollowupDomain, tuple[str, ...]] = {
    FollowupDomain.D5_MONSTER_AI: (
        "monster_ai_content_acquisition_001.json",
        "monster_ai_binding_ledger_001.json",
        "monster_ai_sequence_id_binding_001.json",
    ),
    FollowupDomain.D8_EQUIPMENT_TRACE_EIDOLON: (
        "equipment_trace_eidolon_content_followup_001.json",
    ),
    FollowupDomain.D9_STAGE_ENVIRONMENT_MODE: (
        "stage_environment_mode_content_followup_001.json",
    ),
}


def parse_followup_state(value: Any) -> FollowupState:
    """Strictly parse a mapping/binding state; never guess a default."""
    if isinstance(value, FollowupState):
        return value
    if value is None:
        raise FollowupLedgerError(
            "mapping state cannot be absent; absence is not a state spelling"
        )
    if not isinstance(value, str):
        raise FollowupLedgerError(
            f"mapping state must be a serialized string, got {type(value).__name__}"
        )
    if not value:
        raise FollowupLedgerError("mapping state must be a non-empty string")
    try:
        return FollowupState(value)
    except ValueError:
        raise FollowupLedgerError(
            f"unknown mapping state {value!r}; expected one of "
            f"{FollowupState.spellings()}"
        ) from None


def _parse_domain(value: Any) -> FollowupDomain:
    if isinstance(value, FollowupDomain):
        return value
    if isinstance(value, str):
        try:
            return FollowupDomain(value)
        except ValueError:
            pass
    raise FollowupLedgerError(f"unknown followup domain {value!r}")


def _parse_family(value: Any) -> FollowupFamily:
    if isinstance(value, FollowupFamily):
        return value
    if isinstance(value, str):
        try:
            return FollowupFamily(value)
        except ValueError:
            pass
    raise FollowupLedgerError(f"unknown followup family {value!r}")


def require_evidence_mode(value: Any) -> EvidenceMode:
    """Coerce the evidence mode, refusing the native mode outright."""
    try:
        mode = parse_evidence_mode(value)
    except EvidenceVocabularyError as exc:
        raise FollowupLedgerError(f"invalid evidence mode: {exc}") from exc
    if mode is FORBIDDEN_EVIDENCE_MODE:
        raise FollowupLedgerError(
            "the followup artifacts are registered with native_execution_gain 0 "
            f"and may never carry {FORBIDDEN_EVIDENCE_MODE.value}"
        )
    return mode


# ---------------------------------------------------------------------------
# Strict helpers
# ---------------------------------------------------------------------------

def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FollowupLedgerError(f"{label} must be a mapping")
    return value


def _require_list(value: Any, label: str) -> list:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise FollowupLedgerError(f"{label} must be a list")
    return list(value)


def _require_token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise FollowupLedgerError(f"{label} must be a non-empty string")
    if value != value.strip():
        raise FollowupLedgerError(
            f"{label} {value!r} must not carry surrounding whitespace"
        )
    return value


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FollowupLedgerError(
            f"{label} must be an int, got {type(value).__name__}"
        )
    if value < 0:
        raise FollowupLedgerError(f"{label} must be >= 0")
    return value


def _require_field_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise FollowupLedgerError(f"{label} must be a non-empty string")
    return value


def _require_pointer(value: Any) -> str | tuple[str, ...]:
    """A source pointer: one string, or an ordered composite list of strings.

    The shape is part of the fact.  D8 records a Trace row's composite join as a
    list of pointers; collapsing it to a string, or expanding a string into a
    one-element tuple, would erase a distinction the source recorded.
    """
    if isinstance(value, str):
        return _require_token(value, "source_pointer")
    values = _require_list(value, "source_pointer")
    if not values:
        raise FollowupLedgerError(
            "a composite source_pointer must carry at least one pointer"
        )
    return tuple(
        _require_token(item, "source_pointer value") for item in values
    )


def _presence_map(row: Mapping[str, Any]) -> dict[str, PresenceValue]:
    """Wrap a source row verbatim, keeping absent/null/present distinct.

    Membership decides presence -- never truthiness -- so a recorded ``false``,
    ``0``, ``""``, ``[]``, ``{}`` or ``null`` is never mistaken for an omitted
    key, and ``null`` is never mistaken for an absent key.
    """
    return {
        _require_field_name(key, "row key"): PresenceValue.from_mapping(row, key)
        for key in row
    }


def _detach_payload(values: Mapping[str, PresenceValue]) -> dict[str, PresenceValue]:
    return {
        name: PresenceValue.from_dict(value.to_dict())
        for name, value in values.items()
    }


def _flatten_counts(
    block: Mapping[str, Any], path: str, *, states_only: bool = False
) -> dict[str, int]:
    """Flatten a count block into verbatim ``path/...`` keys.

    Nested counters keep their own path so they can never be read as one number,
    and zero-valued entries are preserved rather than dropped.  With
    ``states_only`` the leaf key must itself be a known state spelling.
    """
    flat: dict[str, int] = {}
    for key, value in block.items():
        leaf = f"{path}/{key}"
        if isinstance(value, Mapping):
            for inner_key, inner_value in value.items():
                if isinstance(inner_value, int) and not isinstance(inner_value, bool):
                    if states_only:
                        parse_followup_state(inner_key)
                    flat[f"{leaf}/{inner_key}"] = inner_value
        elif isinstance(value, int) and not isinstance(value, bool):
            if states_only:
                parse_followup_state(key)
            flat[leaf] = value
    return flat


def _count_states(
    rows: Sequence[Mapping[str, Any]], field: str, path: str
) -> dict[str, int]:
    """Count row states verbatim under ``path/<STATE>``."""
    counts: dict[str, int] = {}
    for row in rows:
        state = parse_followup_state(row[field])
        counts[f"{path}/{state.serialize()}"] = (
            counts.get(f"{path}/{state.serialize()}", 0) + 1
        )
    return counts


def _provenance(
    *,
    repository: Any,
    source_commit: Any,
    version_relation: Any,
    declared_source_version: Any = None,
    raw_sha256: Any = None,
) -> SourceProvenance:
    """Provenance from the artifact's own recorded authority block.

    Nothing is filled in: a field the artifact did not record stays absent, and
    the verbatim spellings it did record are preserved in ``unknown_fields``.
    """
    unknown: dict[str, Any] = {}
    if repository is not None:
        unknown["repository"] = repository
    if version_relation is not None:
        unknown["version_relation_spelling"] = version_relation
    if declared_source_version is not None:
        unknown["declared_source_version"] = declared_source_version
    commit: str | None = None
    if source_commit is not None:
        commit = _require_token(source_commit, "source_commit")
    relation: VersionRelation | None = None
    if version_relation is not None:
        marker = _require_token(version_relation, "version_relation")
        if marker != CLOSE_VERSION_MARKER:
            raise FollowupLedgerError(
                f"unrecognised version relation {marker!r}; this module does not "
                "map a relation the freeze did not record"
            )
        # The canonical mapping documented in battle_ir.evidence: the freeze's
        # one recorded marker is CLOSE_VERSION, and a close-version source may
        # never compare or merge as EXACT_NATIVE.
        relation = VersionRelation.CLOSE_VERSION
    sha: str | None = None
    if raw_sha256 is not None:
        sha = _require_token(raw_sha256, "raw_sha256")
    return SourceProvenance(
        game_version=TARGET_GAME_VERSION,
        runtime_type="FollowupArtifact",
        method="RecordedContentImport",
        method_index=None,
        native_rva="UNKNOWN",
        evidence_level=FOLLOWUP_EVIDENCE_MODE.value,
        source_commit=commit,
        version_relation=relation,
        content_sha256=sha,
        unknown_fields=unknown,
    )


def _cross_check(
    *,
    artifact: str,
    declared_label: str,
    declared: int,
    observed_label: str,
    observed: int,
) -> None:
    """Fail closed when a declared count disagrees with the artifact's rows.

    This is C02-001's stop condition: the count is never patched, and the exact
    source difference is reported instead.
    """
    if declared != observed:
        raise FollowupLedgerError(
            f"{artifact}: declared {declared_label}={declared} but "
            f"{observed_label}={observed}; refusing to patch the count. Exact "
            f"source difference: {declared_label} != len/observed {observed_label}"
        )


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

@dataclass(frozen=True, eq=False, init=False, repr=False)
class FollowupRecord:
    """One represented fact from one followup artifact.

    ``source_pointer``, ``source_id`` and ``ordinal`` together are the source
    occurrence identity, so two byte-identical rows at different positions stay
    distinguishable -- which is what keeps D5's repeated override occurrences
    observable rather than silently deduplicated.
    """

    _domain: FollowupDomain
    _artifact: str
    _family: FollowupFamily
    _ordinal: int
    _source_pointer: str | tuple[str, ...]
    _source_id: str
    _state: FollowupState
    _unknown_reason: PresenceValue
    _payload: Mapping[str, PresenceValue]

    __hash__ = None

    def __init__(
        self,
        domain: Any,
        artifact: Any,
        family: Any,
        ordinal: Any,
        source_pointer: Any,
        source_id: Any,
        state: Any,
        unknown_reason: Any = None,
        payload: Mapping[str, PresenceValue] | None = None,
    ) -> None:
        object.__setattr__(self, "_domain", _parse_domain(domain))
        object.__setattr__(self, "_artifact", _require_token(artifact, "artifact"))
        object.__setattr__(self, "_family", _parse_family(family))
        object.__setattr__(self, "_ordinal", _require_int(ordinal, "ordinal"))
        object.__setattr__(
            self, "_source_pointer", _require_pointer(source_pointer)
        )
        object.__setattr__(self, "_source_id", _require_token(source_id, "source_id"))
        object.__setattr__(self, "_state", parse_followup_state(state))
        if unknown_reason is None:
            reason = PresenceValue.absent()
        elif isinstance(unknown_reason, PresenceValue):
            reason = PresenceValue.from_dict(unknown_reason.to_dict())
        else:
            raise FollowupLedgerError(
                "unknown_reason must be a PresenceValue; a reason is never "
                "inferred from a bare value"
            )
        object.__setattr__(self, "_unknown_reason", reason)
        values = {} if payload is None else payload
        if not isinstance(values, Mapping):
            raise FollowupLedgerError("payload must be a mapping")
        for name, value in values.items():
            _require_field_name(name, "payload key")
            if not isinstance(value, PresenceValue):
                raise FollowupLedgerError(
                    f"payload[{name!r}] must be a PresenceValue; absence and null "
                    "may never be inferred"
                )
        object.__setattr__(self, "_payload", _detach_payload(values))

    # -- public reads (detached) ------------------------------------------

    @property
    def domain(self) -> FollowupDomain:
        return self._domain

    @property
    def artifact(self) -> str:
        return self._artifact

    @property
    def family(self) -> FollowupFamily:
        return self._family

    @property
    def ordinal(self) -> int:
        return self._ordinal

    @property
    def source_pointer(self) -> str | tuple[str, ...]:
        """The verbatim pointer: a single string, or the ordered composite list.

        The shape is preserved.  D8's ledger records 4696 composite joins as a
        *list* of pointers and the rest as a single string, so flattening a
        one-element list into a string (or a string into a one-element tuple)
        would destroy a recorded distinction.
        """
        return self._source_pointer

    def source_pointer_values(self) -> tuple[str, ...]:
        """The pointer as an ordered tuple, for uniform querying only."""
        if isinstance(self._source_pointer, str):
            return (self._source_pointer,)
        return self._source_pointer

    def has_composite_pointer(self) -> bool:
        """True when the source recorded several pointers for this fact."""
        return not isinstance(self._source_pointer, str)

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def state(self) -> FollowupState:
        return self._state

    @property
    def unknown_reason(self) -> PresenceValue:
        return PresenceValue.from_dict(self._unknown_reason.to_dict())

    @property
    def payload(self) -> Mapping[str, PresenceValue]:
        return _detach_payload(self._payload)

    def occurrence_identity(self) -> tuple[str, tuple[str, ...], str, int]:
        """Source occurrence identity: artifact, pointers, id and position."""
        return (
            self._artifact,
            self.source_pointer_values(),
            self._source_id,
            self._ordinal,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": FOLLOWUP_RECORD_SCHEMA,
            "domain": self._domain.serialize(),
            "artifact": self._artifact,
            "family": self._family.serialize(),
            "ordinal": self._ordinal,
            # An explicit shape discriminator: a one-element composite list must
            # not round-trip into a single string.
            "source_pointer": {
                "shape": "SINGLE" if isinstance(self._source_pointer, str) else "COMPOSITE",
                "values": list(self.source_pointer_values()),
            },
            "source_id": self._source_id,
            "state": self._state.serialize(),
            "unknown_reason": self.unknown_reason.to_dict(),
            "payload": [
                {"name": name, "value": value.to_dict()}
                for name, value in self.payload.items()
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FollowupRecord":
        if not isinstance(data, Mapping):
            raise FollowupLedgerError("followup record must be a mapping")
        required = {
            "schema", "domain", "artifact", "family", "ordinal", "source_pointer",
            "source_id", "state", "unknown_reason", "payload",
        }
        if set(data) != required:
            raise FollowupLedgerError(
                "followup record must contain exactly the declared schema fields"
            )
        if data["schema"] != FOLLOWUP_RECORD_SCHEMA:
            raise FollowupLedgerError(f"unknown record schema {data['schema']!r}")
        pointer = _require_mapping(data["source_pointer"], "source_pointer")
        if set(pointer) != {"shape", "values"}:
            raise FollowupLedgerError(
                "source_pointer must contain exactly shape and values"
            )
        values = [
            _require_token(item, "source_pointer value")
            for item in _require_list(pointer["values"], "source_pointer.values")
        ]
        if pointer["shape"] == "SINGLE":
            if len(values) != 1:
                raise FollowupLedgerError(
                    "a SINGLE source_pointer must carry exactly one value"
                )
            source_pointer: Any = values[0]
        elif pointer["shape"] == "COMPOSITE":
            if not values:
                raise FollowupLedgerError(
                    "a COMPOSITE source_pointer must carry at least one value"
                )
            source_pointer = tuple(values)
        else:
            raise FollowupLedgerError(
                f"unknown source_pointer shape {pointer['shape']!r}; expected "
                "'SINGLE' or 'COMPOSITE'"
            )
        payload: dict[str, PresenceValue] = {}
        for item in _require_list(data["payload"], "payload"):
            if not isinstance(item, Mapping) or set(item) != {"name", "value"}:
                raise FollowupLedgerError(
                    "payload items must contain exactly name and value"
                )
            name = _require_field_name(item["name"], "payload name")
            if name in payload:
                raise FollowupLedgerError(f"duplicate payload field {name!r}")
            try:
                payload[name] = PresenceValue.from_dict(item["value"])
            except PresenceValueError as exc:
                raise FollowupLedgerError(f"invalid payload value: {exc}") from exc
        try:
            reason = PresenceValue.from_dict(data["unknown_reason"])
        except PresenceValueError as exc:
            raise FollowupLedgerError(f"invalid unknown_reason: {exc}") from exc
        return cls(
            domain=data["domain"],
            artifact=data["artifact"],
            family=data["family"],
            ordinal=data["ordinal"],
            source_pointer=source_pointer,
            source_id=data["source_id"],
            state=data["state"],
            unknown_reason=reason,
            payload=payload,
        )

    def detached_copy(self) -> "FollowupRecord":
        return FollowupRecord.from_dict(self.to_dict())

    def __bool__(self) -> NoReturn:
        raise FollowupLedgerError(
            "FollowupRecord has no truthiness; a record is representation, not a "
            "permission -- test its state explicitly"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FollowupRecord):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"FollowupRecord({self._artifact}, {self._family.name}, "
            f"#{self._ordinal}, {self._state.name})"
        )


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

@dataclass(frozen=True, eq=False, init=False, repr=False)
class FollowupLedger:
    """The represented facts of one followup artifact.

    ``state_counts`` and ``metric_counts`` are both keyed by a **verbatim path**
    with its own denominator and are never combined: D8's Trace composite
    ``EXACT = 4696`` and join-ledger ``EXACT = 6458`` live under different paths,
    so neither can overwrite the other.  ``records`` preserves source order and
    keeps duplicates.  There is no aggregate "supported" answer.
    """

    _domain: FollowupDomain
    _artifact: str
    _schema_id: str
    _status: str
    _provenance: SourceProvenance
    _evidence_mode: EvidenceMode
    _state_counts: Mapping[str, int]
    _metric_counts: Mapping[str, int]
    _records: tuple[FollowupRecord, ...]
    _source_orders: Mapping[str, tuple[str, ...]]

    __hash__ = None

    def __init__(
        self,
        domain: Any,
        artifact: Any,
        schema_id: Any,
        status: Any,
        provenance: Any,
        evidence_mode: Any = FOLLOWUP_EVIDENCE_MODE,
        state_counts: Mapping[str, int] | None = None,
        metric_counts: Mapping[str, int] | None = None,
        records: Sequence[FollowupRecord] = (),
        source_orders: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        object.__setattr__(self, "_domain", _parse_domain(domain))
        object.__setattr__(self, "_artifact", _require_token(artifact, "artifact"))
        object.__setattr__(self, "_schema_id", _require_token(schema_id, "schema_id"))
        object.__setattr__(self, "_status", _require_token(status, "status"))
        if not isinstance(provenance, SourceProvenance):
            raise FollowupLedgerError("provenance must be a SourceProvenance")
        object.__setattr__(
            self, "_provenance", SourceProvenance.from_dict(provenance.to_dict())
        )
        object.__setattr__(self, "_evidence_mode", require_evidence_mode(evidence_mode))
        states: dict[str, int] = {}
        for path, value in (state_counts or {}).items():
            key = _require_field_name(path, "state_counts path")
            # Every state path must end in a known state spelling, so a
            # misspelled or invented state fails closed rather than lurking.
            parse_followup_state(key.rsplit("/", 1)[-1])
            states[key] = _require_int(value, f"state_counts[{key}]")
        object.__setattr__(self, "_state_counts", states)
        metrics: dict[str, int] = {}
        for path, value in (metric_counts or {}).items():
            key = _require_field_name(path, "metric_counts path")
            metrics[key] = _require_int(value, f"metric_counts[{key}]")
        object.__setattr__(self, "_metric_counts", metrics)
        if isinstance(records, (str, bytes)) or not isinstance(
            records, (tuple, list)
        ):
            raise FollowupLedgerError("records must be a tuple or list")
        detached: list[FollowupRecord] = []
        for index, item in enumerate(records):
            if not isinstance(item, FollowupRecord):
                raise FollowupLedgerError(
                    f"records[{index}] must be a FollowupRecord, got "
                    f"{type(item).__name__}"
                )
            detached.append(FollowupRecord.from_dict(item.to_dict()))
        # No sort and no dedupe: source order and repeated rows are data.
        object.__setattr__(self, "_records", tuple(detached))
        orders: dict[str, tuple[str, ...]] = {}
        for name, values in (source_orders or {}).items():
            _require_field_name(name, "source_orders name")
            orders[name] = tuple(
                _require_token(item, f"source_orders[{name}]")
                for item in _require_list(values, f"source_orders[{name}]")
            )
        object.__setattr__(self, "_source_orders", orders)

    # -- public reads (detached) ------------------------------------------

    @property
    def domain(self) -> FollowupDomain:
        return self._domain

    @property
    def artifact(self) -> str:
        return self._artifact

    @property
    def schema_id(self) -> str:
        return self._schema_id

    @property
    def status(self) -> str:
        return self._status

    @property
    def provenance(self) -> SourceProvenance:
        return SourceProvenance.from_dict(self._provenance.to_dict())

    @property
    def evidence_mode(self) -> EvidenceMode:
        return self._evidence_mode

    @property
    def state_counts(self) -> Mapping[str, int]:
        return dict(self._state_counts)

    @property
    def metric_counts(self) -> Mapping[str, int]:
        return dict(self._metric_counts)

    @property
    def records(self) -> tuple[FollowupRecord, ...]:
        return tuple(item.detached_copy() for item in self._records)

    @property
    def source_orders(self) -> Mapping[str, tuple[str, ...]]:
        return dict(self._source_orders)

    # -- explicit queries (never an aggregate) ----------------------------

    def state_count(self, path: Any) -> int:
        """Declared count at one verbatim path.  A zero is a recorded fact."""
        key = _require_token(path, "state path")
        if key not in self._state_counts:
            raise FollowupLedgerError(
                f"unknown state path {key!r}; this ledger records "
                f"{tuple(self._state_counts)}"
            )
        return self._state_counts[key]

    def metric(self, path: Any) -> int:
        """One metric with its own denominator.  Never combined with others."""
        key = _require_token(path, "metric path")
        if key not in self._metric_counts:
            raise FollowupLedgerError(
                f"unknown metric {key!r}; this ledger records "
                f"{tuple(self._metric_counts)}"
            )
        return self._metric_counts[key]

    def records_of_family(self, family: Any) -> tuple[FollowupRecord, ...]:
        """All records of one family, in source order, duplicates included."""
        wanted = _parse_family(family)
        return tuple(
            item.detached_copy() for item in self._records if item._family is wanted
        )

    def records_in_state(
        self, state: Any, family: Any = None
    ) -> tuple[FollowupRecord, ...]:
        """All records in one state, in source order, duplicates included.

        Without ``family`` this spans every family in the ledger, which is why
        the family is required for a count that is meant to be about one source
        list.  ``EXACT`` alone is ambiguous: in the D5 sequence ledger it covers
        both the 11 skill rows and the 15 occurrences.
        """
        wanted_state = parse_followup_state(state)
        wanted_family = None if family is None else _parse_family(family)
        return tuple(
            item.detached_copy()
            for item in self._records
            if item._state is wanted_state
            and (wanted_family is None or item._family is wanted_family)
        )

    def source_order(self, name: Any) -> tuple[str, ...]:
        """One declared ordered id list, verbatim and unsorted."""
        key = _require_token(name, "source order name")
        if key not in self._source_orders:
            raise FollowupLedgerError(
                f"unknown source order {key!r}; this ledger records "
                f"{tuple(self._source_orders)}"
            )
        return self._source_orders[key]

    def multiplicity_of(self, family: Any, source_id: str) -> int:
        """How many records of one family carry one source id.

        The family is required because the same id can legitimately appear in
        more than one source list -- D5's sequence ledger holds both a
        ``MONSTER_SKILL_ROW`` and three ``SEQUENCE_OCCURRENCE`` records for
        ``801503001`` -- and a cross-family count would conflate them.
        ``records_of_family`` returns the records themselves, so duplicates stay
        observable rather than merely counted.
        """
        wanted = _parse_family(family)
        if not isinstance(source_id, str) or not source_id:
            raise FollowupLedgerError("source_id must be a non-empty string")
        return sum(
            1
            for item in self._records
            if item._family is wanted and item._source_id == source_id
        )

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": FOLLOWUP_LEDGER_SCHEMA,
            "domain": self._domain.serialize(),
            "artifact": self._artifact,
            "schema_id": self._schema_id,
            "status": self._status,
            "evidence_mode": self._evidence_mode.serialize(),
            "provenance": self._provenance.to_dict(),
            "state_counts": [
                {"path": path, "count": count}
                for path, count in self._state_counts.items()
            ],
            "metric_counts": [
                {"path": path, "count": count}
                for path, count in self._metric_counts.items()
            ],
            "records": [item.to_dict() for item in self._records],
            "source_orders": [
                {"name": name, "values": list(values)}
                for name, values in self._source_orders.items()
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FollowupLedger":
        if not isinstance(data, Mapping):
            raise FollowupLedgerError("followup ledger must be a mapping")
        required = {
            "schema", "domain", "artifact", "schema_id", "status", "evidence_mode",
            "provenance", "state_counts", "metric_counts", "records",
            "source_orders",
        }
        if set(data) != required:
            raise FollowupLedgerError(
                "followup ledger must contain exactly the declared schema fields"
            )
        if data["schema"] != FOLLOWUP_LEDGER_SCHEMA:
            raise FollowupLedgerError(f"unknown ledger schema {data['schema']!r}")
        states = _records_from_pairs(
            data["state_counts"], "state_counts", key_name="path"
        )
        for path in states:
            parse_followup_state(path.rsplit("/", 1)[-1])
        metrics = _records_from_pairs(
            data["metric_counts"], "metric_counts", key_name="path"
        )
        records = tuple(
            FollowupRecord.from_dict(item)
            for item in _require_list(data["records"], "records")
        )
        orders: dict[str, tuple[str, ...]] = {}
        for item in _require_list(data["source_orders"], "source_orders"):
            if not isinstance(item, Mapping) or set(item) != {"name", "values"}:
                raise FollowupLedgerError(
                    "source_orders items must contain exactly name and values"
                )
            name = _require_field_name(item["name"], "source_orders name")
            if name in orders:
                raise FollowupLedgerError(f"duplicate source order {name!r}")
            orders[name] = tuple(
                _require_token(value, f"source_orders[{name}]")
                for value in _require_list(item["values"], f"source_orders[{name}]")
            )
        try:
            provenance = SourceProvenance.from_dict(data["provenance"])
        except Exception as exc:  # SourceProvenanceError / ValueError / TypeError
            raise FollowupLedgerError(f"invalid provenance: {exc}") from exc
        return cls(
            domain=data["domain"],
            artifact=data["artifact"],
            schema_id=data["schema_id"],
            status=data["status"],
            provenance=provenance,
            evidence_mode=data["evidence_mode"],
            state_counts=states,
            metric_counts=metrics,
            records=records,
            source_orders=orders,
        )

    def detached_copy(self) -> "FollowupLedger":
        return FollowupLedger.from_dict(self.to_dict())

    def __bool__(self) -> NoReturn:
        raise FollowupLedgerError(
            "FollowupLedger has no truthiness; a ledger is representation, not a "
            "permission and not a coverage verdict -- read a metric explicitly"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FollowupLedger):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"FollowupLedger({self._artifact}, {self._domain.name}, "
            f"records={len(self._records)})"
        )


def _records_from_pairs(value: Any, label: str, *, key_name: str) -> dict[str, int]:
    """Restore an ordered ``path -> count`` register, rejecting duplicates."""
    counts: dict[str, int] = {}
    for item in _require_list(value, label):
        if not isinstance(item, Mapping) or set(item) != {key_name, "count"}:
            raise FollowupLedgerError(
                f"{label} items must contain exactly {key_name} and count"
            )
        key = _require_field_name(item[key_name], label)
        if key in counts:
            raise FollowupLedgerError(f"duplicate {label} path {key!r}")
        counts[key] = _require_int(item["count"], f"{label}[{key}]")
    return counts


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------

def _record(
    *,
    domain: FollowupDomain,
    artifact: str,
    family: FollowupFamily,
    ordinal: int,
    source_pointer: Any,
    source_id: Any,
    state: Any,
    row: Mapping[str, Any],
    reason: PresenceValue | None = None,
) -> FollowupRecord:
    return FollowupRecord(
        domain=domain,
        artifact=artifact,
        family=family,
        ordinal=ordinal,
        source_pointer=source_pointer,
        source_id=source_id,
        state=state,
        unknown_reason=reason,
        payload=_presence_map(row),
    )


# ---------------------------------------------------------------------------
# D5 -- monster AI
# ---------------------------------------------------------------------------

D5 = FollowupDomain.D5_MONSTER_AI
D5_ACQUISITION = "monster_ai_content_acquisition_001.json"
D5_BINDING = "monster_ai_binding_ledger_001.json"
D5_SEQUENCE = "monster_ai_sequence_id_binding_001.json"

#: ``monster_ai_binding_ledger_001.json`` declares no status of its own, so its
#: posture comes from the frozen authority's ``followup_registry`` entry, which
#: records ``"EXACT_BINDING_LEDGER"`` for it.  The other four artifacts declare
#: their own status, and each agrees with the registry.
D5_BINDING_DECLARED_STATUS = "EXACT_BINDING_LEDGER"


def parse_d5_sequence_id_binding(
    document: Mapping[str, Any],
    *,
    evidence_mode: Any = FOLLOWUP_EVIDENCE_MODE,
) -> FollowupLedger:
    """Import ``monster_ai_sequence_id_binding_001.json`` (11 ids, 15 rows).

    The requested-id order and the table source order are two separate facts and
    are kept as two separate ordered lists; neither is sorted or merged.  The
    five declared zero-valued status counters are kept as zeros.
    """
    doc = _require_mapping(document, "document")
    artifact = D5_SEQUENCE
    requested_ids = _require_list(doc["requested_ids"], "requested_ids")
    skill_rows = _require_list(doc["monster_skill_rows"], "monster_skill_rows")
    table_order = _require_list(doc["table_source_order"], "table_source_order")
    sources = _require_list(doc["sequence_sources"], "sequence_sources")
    occurrences = _require_list(doc["sequence_occurrences"], "sequence_occurrences")
    summary = _require_mapping(doc["summary"], "summary")
    declared = _require_mapping(summary["status_counts"], "summary.status_counts")

    _cross_check(
        artifact=artifact,
        declared_label="summary.requested_ids",
        declared=_require_int(summary["requested_ids"], "summary.requested_ids"),
        observed_label="requested_ids",
        observed=len(requested_ids),
    )
    _cross_check(
        artifact=artifact,
        declared_label="summary.rows_found",
        declared=_require_int(summary["rows_found"], "summary.rows_found"),
        observed_label="monster_skill_rows",
        observed=len(skill_rows),
    )
    for label, rows in (("monster_skill_rows", skill_rows),):
        _cross_check(
            artifact=artifact,
            declared_label=f"len({label})",
            declared=len(rows),
            observed_label="len(table_source_order)",
            observed=len(table_order),
        )
    _cross_check(
        artifact=artifact,
        declared_label="summary.sequence_sources",
        declared=_require_int(summary["sequence_sources"], "summary.sequence_sources"),
        observed_label="sequence_sources",
        observed=len(sources),
    )
    _cross_check(
        artifact=artifact,
        declared_label="summary.sequence_occurrences",
        declared=_require_int(
            summary["sequence_occurrences"], "summary.sequence_occurrences"
        ),
        observed_label="sequence_occurrences",
        observed=len(occurrences),
    )
    exact_occurrences = sum(
        1 for item in occurrences if item.get("status") == FollowupState.EXACT.value
    )
    _cross_check(
        artifact=artifact,
        declared_label="summary.status_counts.EXACT",
        declared=_require_int(declared["EXACT"], "status_counts.EXACT"),
        observed_label="occurrences statused EXACT",
        observed=exact_occurrences,
    )
    _cross_check(
        artifact=artifact,
        declared_label="summary.exact_character_bindings",
        declared=_require_int(
            summary["exact_character_bindings"], "summary.exact_character_bindings"
        ),
        observed_label="occurrences statused EXACT",
        observed=exact_occurrences,
    )
    _cross_check(
        artifact=artifact,
        declared_label="sum(summary.status_counts)",
        declared=sum(
            _require_int(value, f"status_counts[{key}]")
            for key, value in declared.items()
        ),
        observed_label="sequence_occurrences",
        observed=len(occurrences),
    )
    _cross_check(
        artifact=artifact,
        declared_label="summary.blocked",
        declared=_require_int(summary["blocked"], "summary.blocked"),
        observed_label="non-EXACT occurrences",
        observed=len(occurrences) - exact_occurrences,
    )
    sequence_total = sum(
        len(_require_list(source["raw_sequence"], "raw_sequence")) for source in sources
    )
    _cross_check(
        artifact=artifact,
        declared_label="sum(sequence_sources[].raw_sequence)",
        declared=sequence_total,
        observed_label="sequence_occurrences",
        observed=len(occurrences),
    )

    records = [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.MONSTER_SKILL_ROW, ordinal=index,
            source_pointer=row["source_ref"]["pointer"],
            source_id=str(row["SkillID"]),
            state=FollowupState.EXACT, row=row,
        )
        for index, row in enumerate(skill_rows)
    ]
    records += [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.SEQUENCE_SOURCE, ordinal=index,
            source_pointer=source["source_ref"]["pointer"],
            source_id=str(source.get("template_id", source.get("monster_id"))),
            state=FollowupState.EXACT, row=source,
        )
        for index, source in enumerate(sources)
    ]
    records += [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.SEQUENCE_OCCURRENCE, ordinal=index,
            source_pointer=(
                f"{occurrence['sequence_source_ref']['pointer']}#{occurrence['index']}"
            ),
            source_id=str(occurrence["raw_id"]),
            state=occurrence["status"], row=occurrence,
        )
        for index, occurrence in enumerate(occurrences)
    ]
    return FollowupLedger(
        domain=D5,
        artifact=artifact,
        schema_id=doc["schema"],
        status=doc["result"],
        provenance=_provenance(
            repository=doc["authority"].get("repository"),
            source_commit=doc["authority"].get("source_commit"),
            version_relation=doc["authority"].get("version_relation"),
            raw_sha256=doc["authority"].get("sha256"),
        ),
        evidence_mode=evidence_mode,
        state_counts=_flatten_counts(declared, "summary/status_counts", states_only=True),
        metric_counts={
            "summary/requested_ids": _require_int(
                summary["requested_ids"], "summary.requested_ids"
            ),
            "summary/rows_found": _require_int(
                summary["rows_found"], "summary.rows_found"
            ),
            "summary/exact_trigger_keys": _require_int(
                summary["exact_trigger_keys"], "summary.exact_trigger_keys"
            ),
            "summary/exact_character_bindings": _require_int(
                summary["exact_character_bindings"], "summary.exact_character_bindings"
            ),
            "summary/sequence_sources": _require_int(
                summary["sequence_sources"], "summary.sequence_sources"
            ),
            "summary/sequence_occurrences": _require_int(
                summary["sequence_occurrences"], "summary.sequence_occurrences"
            ),
            "summary/blocked": _require_int(summary["blocked"], "summary.blocked"),
            "sequence_occurrences/unique_source_ids": len(
                {str(item["raw_id"]) for item in occurrences}
            ),
            "requested_ids/unique": len({str(value) for value in requested_ids}),
        },
        records=records,
        source_orders={
            "requested_ids": tuple(str(value) for value in requested_ids),
            "table_source_order": tuple(str(item["SkillID"]) for item in table_order),
        },
    )


def parse_d5_binding_ledger(
    document: Mapping[str, Any],
    *,
    evidence_mode: Any = FOLLOWUP_EVIDENCE_MODE,
) -> FollowupLedger:
    """Import ``monster_ai_binding_ledger_001.json`` (14 bindings, 6 templates).

    Per-field statuses stay separate: an EXACT template path and a MISSING
    override path are two facts and are never merged into one answer.  A binding
    is ``UNRESOLVED_PRECEDENCE`` only where the artifact's own
    ``unresolved_precedence_monster_ids`` names that monster.
    """
    doc = _require_mapping(document, "document")
    artifact = D5_BINDING
    templates = _require_list(doc["template_records"], "template_records")
    monsters = _require_list(doc["monster_records"], "monster_records")
    bindings = _require_list(doc["bindings"], "bindings")
    join = _require_mapping(doc["join_summary"], "join_summary")
    legend = _require_list(doc["edge_status_legend"], "edge_status_legend")
    for item in legend:
        parse_followup_state(item)
    unresolved_ids = {
        str(value)
        for value in _require_list(
            join["unresolved_precedence_monster_ids"], "unresolved_precedence_monster_ids"
        )
    }
    duplicates = _require_list(
        join["duplicate_override_sequence_preserved"],
        "duplicate_override_sequence_preserved",
    )

    _cross_check(
        artifact=artifact,
        declared_label="join_summary.monster_rows",
        declared=_require_int(join["monster_rows"], "join_summary.monster_rows"),
        observed_label="monster_records",
        observed=len(monsters),
    )
    _cross_check(
        artifact=artifact,
        declared_label="join_summary.monster_rows",
        declared=_require_int(join["monster_rows"], "join_summary.monster_rows"),
        observed_label="bindings",
        observed=len(bindings),
    )
    _cross_check(
        artifact=artifact,
        declared_label="join_summary.template_rows",
        declared=_require_int(join["template_rows"], "join_summary.template_rows"),
        observed_label="template_records",
        observed=len(templates),
    )
    _cross_check(
        artifact=artifact,
        declared_label="join_summary.policy_skill_edges_exact + missing",
        declared=(
            _require_int(join["policy_skill_edges_exact"], "edges_exact")
            + _require_int(join["policy_skill_edges_missing"], "edges_missing")
        ),
        observed_label="join_summary.policy_skill_edges_total",
        observed=_require_int(join["policy_skill_edges_total"], "edges_total"),
    )

    field_counts: dict[str, int] = {}
    binding_states: dict[str, int] = {}
    for binding in bindings:
        for field in binding["static_policy_fields_in_source_order"]:
            state = parse_followup_state(field["status"])
            key = f"static_policy_field_status/{state.serialize()}"
            field_counts[key] = field_counts.get(key, 0) + 1
        precedence = binding["effective_precedence"]
        if not isinstance(precedence, str) or precedence not in D5_PRECEDENCE_SPELLINGS:
            raise FollowupLedgerError(
                f"{artifact}: unrecognised effective_precedence {precedence!r}; this "
                "module does not map a precedence the artifact did not record"
            )
        state = (
            FollowupState.UNRESOLVED_PRECEDENCE
            if str(binding["monster_row_source"]["MonsterID"]) in unresolved_ids
            else FollowupState.EXACT
            if precedence == "EXACT_TEMPLATE_PATH_ONLY"
            else FollowupState.MISSING
        )
        key = f"monster_binding/{state.serialize()}"
        binding_states[key] = binding_states.get(key, 0) + 1

    records = [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.TEMPLATE_RECORD, ordinal=index,
            source_pointer=row["pointer"],
            source_id=str(row["row"]["MonsterTemplateID"]),
            state=FollowupState.EXACT, row=row,
        )
        for index, row in enumerate(templates)
    ]
    records += [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.MONSTER_RECORD, ordinal=index,
            source_pointer=row["pointer"],
            source_id=str(row["row"]["MonsterID"]),
            state=FollowupState.EXACT, row=row,
        )
        for index, row in enumerate(monsters)
    ]
    records += [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.MONSTER_BINDING, ordinal=index,
            source_pointer=binding["monster_row_source"]["raw_pointer"],
            source_id=str(binding["monster_row_source"]["MonsterID"]),
            state=(
                FollowupState.UNRESOLVED_PRECEDENCE
                if str(binding["monster_row_source"]["MonsterID"]) in unresolved_ids
                else FollowupState.EXACT
                if binding["effective_precedence"] == "EXACT_TEMPLATE_PATH_ONLY"
                else FollowupState.MISSING
            ),
            row=binding,
        )
        for index, binding in enumerate(bindings)
    ]
    records += [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.DUPLICATE_OVERRIDE_ELEMENT, ordinal=index,
            source_pointer=f"/join_summary/duplicate_override_sequence_preserved/{index}",
            source_id=str(next(iter(element.values()))),
            state=FollowupState.EXACT, row=element,
        )
        for index, element in enumerate(duplicates)
    ]
    counts = dict(field_counts)
    counts.update(binding_states)
    return FollowupLedger(
        domain=D5,
        artifact=artifact,
        schema_id=doc["schema"],
        status=D5_BINDING_DECLARED_STATUS,
        provenance=_provenance(
            repository=doc["authority"].get("repository"),
            source_commit=doc["authority"].get("selected_commit"),
            version_relation=None,
        ),
        evidence_mode=evidence_mode,
        state_counts=counts,
        metric_counts={
            "join_summary/monster_rows": _require_int(
                join["monster_rows"], "monster_rows"
            ),
            "join_summary/template_rows": _require_int(
                join["template_rows"], "template_rows"
            ),
            "join_summary/policy_skill_edges_total": _require_int(
                join["policy_skill_edges_total"], "edges_total"
            ),
            "join_summary/policy_skill_edges_exact": _require_int(
                join["policy_skill_edges_exact"], "edges_exact"
            ),
            "join_summary/policy_skill_edges_missing": _require_int(
                join["policy_skill_edges_missing"], "edges_missing"
            ),
            "join_summary/groupname_consumer_edges_exact": _require_int(
                join["groupname_consumer_edges_exact"], "groupname_edges"
            ),
            "join_summary/duplicate_override_sequence_preserved": len(duplicates),
            "join_summary/unresolved_precedence_monster_ids": len(unresolved_ids),
            "edge_status_legend/declared": len(legend),
            "non_inferences/count": len(
                _require_list(doc["non_inferences"], "non_inferences")
            ),
        },
        records=records,
        source_orders={
            "template_pointers": tuple(str(row["pointer"]) for row in templates),
            "monster_pointers": tuple(str(row["pointer"]) for row in monsters),
        },
    )


def parse_d5_content_acquisition(
    document: Mapping[str, Any],
    *,
    evidence_mode: Any = FOLLOWUP_EVIDENCE_MODE,
) -> FollowupLedger:
    """Import ``monster_ai_content_acquisition_001.json``.

    Recorded absences stay absent; the recorded extraction maps are counted but
    not interpreted as runtime behavior.
    """
    doc = _require_mapping(document, "document")
    artifact = D5_ACQUISITION
    requested = _require_list(doc["requested_paths"], "requested_paths")
    absent = _require_list(
        doc["verified_absent_at_pinned_revision"],
        "verified_absent_at_pinned_revision",
    )
    structural = _require_mapping(
        doc["policy_structural_extraction"], "policy_structural_extraction"
    )
    character = _require_mapping(
        doc["character_config_extraction"], "character_config_extraction"
    )
    consumer = _require_mapping(
        doc["global_group_consumer_result"], "global_group_consumer_result"
    )
    records = [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.ACQUISITION_REQUEST, ordinal=index,
            source_pointer=f"/requested_paths/{index}",
            source_id=str(path),
            state=FollowupState.EXACT,
            row={"requested_path": path},
        )
        for index, path in enumerate(requested)
    ]
    records += [
        _record(
            domain=D5, artifact=artifact,
            family=FollowupFamily.ABSENT_ROW, ordinal=index,
            source_pointer=f"/verified_absent_at_pinned_revision/{index}",
            source_id=str(item),
            state=FollowupState.ABSENT_AT_PINNED_COMMIT,
            row={"absent": item},
        )
        for index, item in enumerate(absent)
    ]
    return FollowupLedger(
        domain=D5,
        artifact=artifact,
        schema_id=doc["schema"],
        status=doc["result"],
        provenance=_provenance(
            repository=doc["authority"].get("repository"),
            source_commit=doc["authority"].get("selected_commit"),
            version_relation=None,
        ),
        evidence_mode=evidence_mode,
        state_counts={
            "requested_paths/EXACT": len(requested),
            "verified_absent_at_pinned_revision/ABSENT_AT_PINNED_COMMIT": len(absent),
        },
        metric_counts={
            "policy_structural_extraction/extracted_documents": len(structural),
            "character_config_extraction/extracted_documents": len(character),
            "global_group_consumer_result/consumer_edges": len(
                _require_list(consumer["consumer_edges"], "consumer_edges")
            ),
            "global_group_consumer_result/cached_global_group_sources": len(
                _require_list(
                    consumer["cached_global_group_sources"],
                    "cached_global_group_sources",
                )
            ),
        },
        records=records,
        source_orders={"requested_paths": tuple(str(path) for path in requested)},
    )


# ---------------------------------------------------------------------------
# D8 -- equipment / trace / eidolon
# ---------------------------------------------------------------------------

D8 = FollowupDomain.D8_EQUIPMENT_TRACE_EIDOLON
D8_ARTIFACT = "equipment_trace_eidolon_content_followup_001.json"

#: requests[i] maps to the sub-block holding its selected/absent rows.
_D8_REQUEST_BLOCKS = {
    "ExcelOutput/AvatarConfig.json": "avatar_config_rows",
    "ExcelOutput/AvatarSkillTreeConfig.json": "trace_rows",
    "ExcelOutput/AvatarRankConfig.json": "rank_rows",
    "ExcelOutput/AvatarSkillConfig.json": "missing_skill_rows",
}


def parse_d8_content_followup(
    document: Mapping[str, Any],
    *,
    evidence_mode: Any = FOLLOWUP_EVIDENCE_MODE,
) -> FollowupLedger:
    """Import ``equipment_trace_eidolon_content_followup_001.json``.

    Preserves the 4696 exact raw Trace joins, the 322 that remain missing, the
    136 exact-name behavior candidates at their own classification, and every
    recorded absence.  No activation, cumulative threshold or relic behavior is
    inferred, and ``EXACT_EXISTING_DEFINITION`` is a mapping classification only.
    """
    doc = _require_mapping(document, "document")
    artifact = D8_ARTIFACT
    requests = _require_list(doc["requests"], "requests")
    joins = _require_list(doc["exact_join_ledger"], "exact_join_ledger")
    candidates = _require_list(
        doc["behavior_candidate_ledger"], "behavior_candidate_ledger"
    )
    add_level = _require_list(doc["skill_add_level_ledger"], "skill_add_level_ledger")
    absent_rows = _require_list(doc["absent_rows"], "absent_rows")
    before = _require_mapping(doc["coverage_before"], "coverage_before")
    after = _require_mapping(doc["coverage_after"], "coverage_after")
    gaps = _require_list(doc["remaining_content_gaps"], "remaining_content_gaps")
    collisions = _require_list(doc["collisions"], "collisions")
    strict_nonclaims = _require_list(doc["strict_nonclaims"], "strict_nonclaims")

    absent_total = 0
    for index, request in enumerate(requests):
        path = _require_token(request["path"], "requests[].path")
        block_name = _D8_REQUEST_BLOCKS.get(path)
        if block_name is None:
            raise FollowupLedgerError(
                f"{artifact}: unexpected request path {path!r}; this module does "
                "not import an unregistered request block"
            )
        block = _require_mapping(doc[block_name], block_name)
        selected = _require_list(block["selected_rows"], f"{block_name}.selected_rows")
        absent = _require_list(
            block["absent_selector_rows"], f"{block_name}.absent_selector_rows"
        )
        _cross_check(
            artifact=artifact,
            declared_label=f"requests[{index}].selected_rows",
            declared=_require_int(request["selected_rows"], "selected_rows"),
            observed_label=f"{block_name}.selected_rows",
            observed=len(selected),
        )
        _cross_check(
            artifact=artifact,
            declared_label=f"requests[{index}].missing_selector_rows",
            declared=_require_int(
                request["missing_selector_rows"], "missing_selector_rows"
            ),
            observed_label=f"{block_name}.absent_selector_rows",
            observed=len(absent),
        )
        absent_total += len(absent)

    trace_before = _require_mapping(before["Trace"], "coverage_before.Trace")
    trace_after = _require_mapping(after["Trace"], "coverage_after.Trace")
    eidolon_after = _require_mapping(after["Eidolon"], "coverage_after.Eidolon")
    composite = _require_mapping(
        trace_after["exact_composite_raw_joins"],
        "coverage_after.Trace.exact_composite_raw_joins",
    )
    composite_total = sum(
        _require_int(value, f"exact_composite_raw_joins[{key}]")
        for key, value in composite.items()
    )
    for key in composite:
        parse_followup_state(key)
    # 4696 EXACT + 0 AMBIGUOUS + 322 MISSING must account for every existing row.
    _cross_check(
        artifact=artifact,
        declared_label="coverage_after.Trace.existing_static_rows",
        declared=_require_int(
            trace_after["existing_static_rows"], "existing_static_rows"
        ),
        observed_label="exact_composite_raw_joins total",
        observed=composite_total,
    )
    behaviour = _require_mapping(
        eidolon_after["behavior_candidates"], "behavior_candidates"
    )
    for key in behaviour:
        parse_followup_state(key)
    behaviour_total = sum(
        _require_int(value, f"behavior_candidates[{key}]")
        for key, value in behaviour.items()
    )
    _cross_check(
        artifact=artifact,
        declared_label="coverage_after.Eidolon.behavior_candidates total",
        declared=behaviour_total,
        observed_label="behavior_candidate_ledger",
        observed=len(candidates),
    )
    _cross_check(
        artifact=artifact,
        declared_label="coverage_after.Eidolon.exact_skill_level_override_edges",
        declared=_require_int(
            eidolon_after["exact_skill_level_override_edges"],
            "exact_skill_level_override_edges",
        ),
        observed_label="skill_add_level_ledger",
        observed=len(add_level),
    )
    _cross_check(
        artifact=artifact,
        declared_label="sum(requests[].missing_selector_rows)",
        declared=absent_total,
        observed_label="absent_rows",
        observed=len(absent_rows),
    )
    _cross_check(
        artifact=artifact,
        declared_label="collisions",
        declared=0,
        observed_label="collisions",
        observed=len(collisions),
    )

    state_counts: dict[str, int] = {}
    state_counts.update(
        _flatten_counts(composite, "coverage_after/Trace/exact_composite_raw_joins")
    )
    state_counts.update(
        _flatten_counts(behaviour, "coverage_after/Eidolon/behavior_candidates")
    )
    # Row-level registers live under their own path, so the composite counters
    # above are never overwritten by the ledger's own EXACT/MISSING tallies.
    state_counts.update(
        _count_states(joins, "status", "exact_join_ledger")
    )
    state_counts.update(_count_states(candidates, "status", "behavior_candidate_ledger"))
    state_counts.update(_count_states(absent_rows, "status", "absent_rows"))
    state_counts.update(_count_states(gaps, "status", "remaining_content_gaps"))

    metrics: dict[str, int] = {
        "coverage_before/Trace/unique_point_ids": _require_int(
            trace_before["unique_point_ids"], "unique_point_ids"
        ),
        "coverage_before/Trace/skill_target_edges": _require_int(
            trace_before["skill_target_edges"], "skill_target_edges"
        ),
        "coverage_before/Trace/skill_target_edges_missing": _require_int(
            trace_before["skill_target_edges_missing"], "skill_target_edges_missing"
        ),
        "coverage_before/Trace/missing_skill_ids": len(
            _require_list(trace_before["missing_skill_ids"], "missing_skill_ids")
        ),
        # A static surface classification is a coverage metric, not a mapping
        # state: its keys are surface kinds, and keeping them here prevents them
        # from being read as resolved/unresolved bindings.
        "coverage_before/Trace/static_surface_classification/total": sum(
            _require_int(value, f"static_surface_classification[{key}]")
            for key, value in _require_mapping(
                trace_before["static_surface_classification"],
                "coverage_before.Trace.static_surface_classification",
            ).items()
        ),
        "coverage_after/Trace/existing_static_rows": _require_int(
            trace_after["existing_static_rows"], "existing_static_rows"
        ),
        "absent_rows/total": len(absent_rows),
        "exact_join_ledger/total": len(joins),
        "behavior_candidate_ledger/total": len(candidates),
        "skill_add_level_ledger/total": len(add_level),
        "collisions/total": len(collisions),
        "strict_nonclaims/count": len(strict_nonclaims),
        "requests/total": len(requests),
    }
    for key, value in trace_after.items():
        if isinstance(value, int) and not isinstance(value, bool):
            metrics[f"coverage_after/Trace/{key}"] = value
    for key, value in eidolon_after.items():
        if isinstance(value, int) and not isinstance(value, bool):
            metrics[f"coverage_after/Eidolon/{key}"] = value

    records = [
        _record(
            domain=D8, artifact=artifact,
            family=FollowupFamily.EXACT_JOIN, ordinal=index,
            source_pointer=row["source_pointer"],
            source_id=str(row["source_id"]),
            state=row["status"], row=row,
        )
        for index, row in enumerate(joins)
    ]
    records += [
        _record(
            domain=D8, artifact=artifact,
            family=FollowupFamily.BEHAVIOR_CANDIDATE, ordinal=index,
            source_pointer=row["source_pointer"],
            source_id=str(row["source_id"]),
            state=row["status"], row=row,
        )
        for index, row in enumerate(candidates)
    ]
    records += [
        _record(
            domain=D8, artifact=artifact,
            family=FollowupFamily.SKILL_ADD_LEVEL_EDGE, ordinal=index,
            source_pointer=row["source_pointer"],
            source_id=str(row["source_rank_id"]),
            state=FollowupState.EXACT, row=row,
        )
        for index, row in enumerate(add_level)
    ]
    records += [
        _record(
            domain=D8, artifact=artifact,
            family=FollowupFamily.ABSENT_ROW, ordinal=index,
            source_pointer=f"/absent_rows/{index}",
            source_id=str(row["selector_id"]),
            state=row["status"], row=row,
        )
        for index, row in enumerate(absent_rows)
    ]
    records += [
        _record(
            domain=D8, artifact=artifact,
            family=FollowupFamily.REMAINING_GAP, ordinal=index,
            source_pointer=f"/remaining_content_gaps/{index}",
            source_id=str(row.get("portion", f"gap:{index}")),
            state=row["status"], row=row,
            reason=(
                PresenceValue.present(row["reason"])
                if isinstance(row.get("reason"), str)
                else PresenceValue.absent()
            ),
        )
        for index, row in enumerate(gaps)
    ]
    return FollowupLedger(
        domain=D8,
        artifact=artifact,
        schema_id=doc["ticket"],
        status=doc["status"],
        provenance=_provenance(
            repository=doc["source"].get("repository"),
            source_commit=doc["source"].get("source_commit"),
            version_relation=doc["source"].get("version_relation"),
            declared_source_version=doc["source"].get("declared_source_version"),
        ),
        evidence_mode=evidence_mode,
        state_counts=state_counts,
        metric_counts=metrics,
        records=records,
        source_orders={
            "request_paths": tuple(
                _require_token(request["path"], "requests[].path")
                for request in requests
            ),
            "absent_row_requests": tuple(str(row["request"]) for row in absent_rows),
        },
    )


# ---------------------------------------------------------------------------
# D9 -- stage / environment / mode
# ---------------------------------------------------------------------------

D9 = FollowupDomain.D9_STAGE_ENVIRONMENT_MODE
D9_ARTIFACT = "stage_environment_mode_content_followup_001.json"

#: Every index the artifact declares.  D9 records all of them empty.
_D9_INDEX_KEYS = (
    "node_index",
    "edge_index",
    "stage_config_key_refs",
    "wave_spawn_refs",
    "terminal_refs",
    "behavior_refs",
    "external_dependency_refs",
)


def parse_d9_content_followup(
    document: Mapping[str, Any],
    *,
    evidence_mode: Any = FOLLOWUP_EVIDENCE_MODE,
) -> FollowupLedger:
    """Import ``stage_environment_mode_content_followup_001.json``.

    The requested path is absent at the pinned commit.  This module keeps that
    absence: it does not substitute another Stage file, does not look for a
    neighbour path, and does not produce a node, an edge, a wave, a terminal
    rule, a behavior reference or an external dependency that the artifact does
    not record.  Every declared index must still be empty here.
    """
    doc = _require_mapping(document, "document")
    artifact = D9_ARTIFACT
    source = _require_mapping(doc["source"], "source")
    request = _require_mapping(doc["request_result"], "request_result")
    graph = _require_mapping(doc["graph_structure"], "graph_structure")
    validation = _require_mapping(doc["validation"], "validation")
    gaps = _require_list(doc["remaining_content_gaps"], "remaining_content_gaps")
    nonclaims = _require_list(doc["semantic_nonclaims"], "semantic_nonclaims")
    attempted = _require_list(request["attempted_paths"], "attempted_paths")
    indexes = {key: _require_list(doc[key], key) for key in _D9_INDEX_KEYS}

    for label, value in (
        ("request_result.lookup_result", request["lookup_result"]),
        ("request_result.result", request["result"]),
    ):
        if value != FollowupState.ABSENT_AT_PINNED_COMMIT.value:
            raise FollowupLedgerError(
                f"{artifact}: {label} is {value!r}, expected "
                f"{FollowupState.ABSENT_AT_PINNED_COMMIT.value!r}; no other "
                "outcome is represented by this import"
            )
    if request["requested_path"] != STAGE_COMMON_TEMPLATE_PATH:
        raise FollowupLedgerError(
            f"{artifact}: requested_path is {request['requested_path']!r}, expected "
            f"{STAGE_COMMON_TEMPLATE_PATH!r}; this module does not substitute a path"
        )
    _cross_check(
        artifact=artifact,
        declared_label="request_result.maximum_requested_paths",
        declared=_require_int(
            request["maximum_requested_paths"], "maximum_requested_paths"
        ),
        observed_label="attempted_paths",
        observed=len(attempted),
    )
    _cross_check(
        artifact=artifact,
        declared_label="validation.attempted_path_count",
        declared=_require_int(
            validation["attempted_path_count"], "attempted_path_count"
        ),
        observed_label="attempted_paths",
        observed=len(attempted),
    )
    if validation["only_one_path_attempted"] is not True:
        raise FollowupLedgerError(
            f"{artifact}: validation.only_one_path_attempted is not true; this "
            "module requires the artifact's single-path contract"
        )
    if graph["raw_document_persisted"] is not False:
        raise FollowupLedgerError(
            f"{artifact}: graph_structure.raw_document_persisted is not false"
        )
    for key, values in indexes.items():
        if values:
            raise FollowupLedgerError(
                f"{artifact}: {key} is not empty ({len(values)} entries); this "
                "module does not represent structure the artifact did not record"
            )
    if _require_list(graph["top_level_keys_types"], "top_level_keys_types"):
        raise FollowupLedgerError(
            f"{artifact}: graph_structure.top_level_keys_types is not empty"
        )

    records = [
        _record(
            domain=D9, artifact=artifact,
            family=FollowupFamily.SOURCE_REQUEST, ordinal=0,
            source_pointer="/request_result",
            source_id=STAGE_COMMON_TEMPLATE_PATH,
            state=FollowupState.ABSENT_AT_PINNED_COMMIT,
            row=request,
            reason=PresenceValue.present(request["action_after_absence"]),
        )
    ]
    records += [
        _record(
            domain=D9, artifact=artifact,
            family=FollowupFamily.REMAINING_GAP, ordinal=index,
            source_pointer=f"/remaining_content_gaps/{index}",
            source_id=str(row.get("portion", f"gap:{index}")),
            state=row["status"], row=row,
            reason=(
                PresenceValue.present(row["lookup_result"])
                if isinstance(row.get("lookup_result"), str)
                else PresenceValue.absent()
            ),
        )
        for index, row in enumerate(gaps)
    ]
    state_counts = {"request_result/ABSENT_AT_PINNED_COMMIT": 1}
    state_counts.update(_count_states(gaps, "status", "remaining_content_gaps"))
    metrics = {f"indexes/{key}": len(values) for key, values in indexes.items()}
    metrics.update(
        {
            "validation/attempted_path_count": _require_int(
                validation["attempted_path_count"], "attempted_path_count"
            ),
            "semantic_nonclaims/count": len(nonclaims),
            "remaining_content_gaps/count": len(gaps),
            "graph_structure/top_level_keys_types": len(
                _require_list(graph["top_level_keys_types"], "top_level_keys_types")
            ),
        }
    )
    return FollowupLedger(
        domain=D9,
        artifact=artifact,
        schema_id=doc["ticket"],
        status=doc["status"],
        provenance=_provenance(
            repository=source.get("repository"),
            source_commit=source.get("commit"),
            version_relation=source.get("version_relation"),
            declared_source_version=source.get("declared_version"),
            raw_sha256=source.get("raw_sha256"),
        ),
        evidence_mode=evidence_mode,
        state_counts=state_counts,
        metric_counts=metrics,
        records=records,
        source_orders={
            "attempted_paths": tuple(
                _require_token(value, "attempted_paths") for value in attempted
            )
        },
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

PARSERS: Mapping[str, Callable[..., FollowupLedger]] = {
    D5_ACQUISITION: parse_d5_content_acquisition,
    D5_BINDING: parse_d5_binding_ledger,
    D5_SEQUENCE: parse_d5_sequence_id_binding,
    D8_ARTIFACT: parse_d8_content_followup,
    D9_ARTIFACT: parse_d9_content_followup,
}


def load_followup_ledgers(
    base_dir: str | Path,
    *,
    evidence_mode: Any = FOLLOWUP_EVIDENCE_MODE,
) -> tuple[FollowupLedger, ...]:
    """Read and import all five followup artifacts from ``base_dir``.

    Only these five names are opened.  No directory scan, no neighbour lookup and
    no fallback path is performed, so an absent artifact fails loudly instead of
    being replaced by something else.
    """
    root = Path(base_dir)
    if not root.is_dir():
        raise FollowupLedgerError(f"{base_dir} is not a directory")
    ledgers: list[FollowupLedger] = []
    for names in FOLLOWUP_ARTIFACTS.values():
        for name in names:
            path = root / name
            if not path.is_file():
                raise FollowupLedgerError(
                    f"followup artifact {name} is absent from {root}; this module "
                    "does not substitute another file"
                )
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise FollowupLedgerError(f"{name} is not valid JSON: {exc}") from exc
            ledgers.append(PARSERS[name](document, evidence_mode=evidence_mode))
    return tuple(ledgers)
