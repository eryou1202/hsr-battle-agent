# -*- coding: utf-8 -*-
"""Source provenance for recovered battle semantics.

These values are evidence / debug / audit metadata only.  Runtime execution
must never branch on ``method_index`` or ``native_rva``.

Schema history
--------------

``source_provenance/1`` (v1, legacy)
    The original seven fields.  A v1 document carries no ``schema_version``
    key.  v1 reads remain supported and are explicit:
    :meth:`SourceProvenance.from_dict_v1`.

``source_provenance/2`` (v2, envelope)
    Adds the envelope fields required by Terra F01: ``source_commit``,
    ``version_relation``, ``content_sha256`` and ``profile``.  A v2 document
    carries ``schema_version = source_provenance/2``.

Losslessness rules
------------------

* **Absence stays observable.**  A field that was not present in the source
  document is not present in :meth:`to_dict` output either.  Absence is never
  silently filled with a default, and a present-but-null value stays distinct
  from an absent key.
* **Unknown fields stay observable.**  Keys outside the known vocabulary are
  preserved verbatim in :attr:`SourceProvenance.unknown_fields` and re-emitted,
  so a document round-trips with the same key set and same values.
* **Serialization never aliases the model.**  :meth:`to_dict` returns a fresh
  deep-copied structure; mutating it cannot mutate the model.

Dispatch rule
-------------

``native_rva`` and ``method_index`` exist for audit and debugging.  They are
never dispatch inputs: :meth:`dispatch_key` refuses rather than supplying one,
and the test suite asserts that no ``battle_sandbox`` module reads either
attribute.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, NoReturn

from hsr_battle_agent.battle_ir.evidence import (
    VersionRelation,
    parse_version_relation,
)

PROVENANCE_NOTE_DEFAULT = (
    "RVA and method index are provenance only; runtime logic must not depend on them"
)

SOURCE_PROVENANCE_SCHEMA_V1 = "source_provenance/1"
SOURCE_PROVENANCE_SCHEMA_V2 = "source_provenance/2"

#: The legacy v1 field set, in its original declaration order.
V1_FIELD_NAMES: tuple[str, ...] = (
    "game_version",
    "runtime_type",
    "method",
    "method_index",
    "native_rva",
    "evidence_level",
    "note",
)

#: The F01 v2 envelope fields, excluding ``schema_version``.
V2_ENVELOPE_FIELD_NAMES: tuple[str, ...] = (
    "source_commit",
    "version_relation",
    "content_sha256",
    "profile",
)

KNOWN_FIELD_NAMES: tuple[str, ...] = (
    ("schema_version",) + V1_FIELD_NAMES + V2_ENVELOPE_FIELD_NAMES
)

#: v1 fields a document must supply; ``note`` keeps its documented default.
REQUIRED_V1_FIELD_NAMES: tuple[str, ...] = V1_FIELD_NAMES[:-1]

_GIT_COMMIT_RE = re.compile(r"\A[0-9a-f]{40}\Z")
_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")


class SourceProvenanceError(ValueError):
    """Raised for a malformed provenance document."""


def _require_non_empty_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SourceProvenanceError(f"{label} must be a non-empty string")
    return value


def _require_commit(value: Any, label: str) -> str:
    text = _require_non_empty_str(value, label)
    if not _GIT_COMMIT_RE.match(text):
        raise SourceProvenanceError(
            f"{label} must be 40 lowercase hexadecimal characters, got {text!r}"
        )
    return text


def _require_sha256(value: Any, label: str) -> str:
    text = _require_non_empty_str(value, label)
    if not _SHA256_RE.match(text):
        raise SourceProvenanceError(
            f"{label} must be 64 lowercase hexadecimal characters, got {text!r}"
        )
    return text


@dataclass(frozen=True)
class SourceProvenance:
    # --- v1 fields; declaration order and defaults are unchanged ---
    game_version: str
    runtime_type: str
    method: str
    method_index: int | None
    native_rva: str
    evidence_level: str
    note: str = PROVENANCE_NOTE_DEFAULT

    # --- v2 envelope fields; optional, so v1 construction stays valid ---
    schema_version: str | None = None
    source_commit: str | None = None
    version_relation: VersionRelation | None = None
    content_sha256: str | None = None
    profile: str | None = None

    # --- lossless observability ---
    unknown_fields: Mapping[str, Any] = field(default_factory=dict)
    #: Keys present in the source document, or ``None`` when this object was
    #: constructed directly rather than read from a document.
    source_fields: tuple[str, ...] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        # --- v1 validation; behaviour preserved from the legacy class ---
        if not self.game_version:
            raise ValueError("game_version must be non-empty")
        if not self.runtime_type:
            raise ValueError("runtime_type must be non-empty")
        if not self.method:
            raise ValueError("method must be non-empty")
        if self.method_index is not None:
            if isinstance(self.method_index, bool) or not isinstance(
                self.method_index, int
            ):
                raise TypeError("method_index must be an int or None")
            if self.method_index < 0:
                raise ValueError("method_index must be >= 0")

        # --- v2 validation: validate what is present, never fill anything ---
        if self.schema_version is not None and self.schema_version not in (
            SOURCE_PROVENANCE_SCHEMA_V1,
            SOURCE_PROVENANCE_SCHEMA_V2,
        ):
            raise SourceProvenanceError(
                f"unknown schema_version {self.schema_version!r}; expected "
                f"{SOURCE_PROVENANCE_SCHEMA_V1!r} or "
                f"{SOURCE_PROVENANCE_SCHEMA_V2!r}"
            )
        if self.source_commit is not None:
            object.__setattr__(
                self,
                "source_commit",
                _require_commit(self.source_commit, "source_commit"),
            )
        if self.content_sha256 is not None:
            object.__setattr__(
                self,
                "content_sha256",
                _require_sha256(self.content_sha256, "content_sha256"),
            )
        if self.profile is not None:
            object.__setattr__(
                self, "profile", _require_non_empty_str(self.profile, "profile")
            )
        if self.version_relation is not None and not isinstance(
            self.version_relation, VersionRelation
        ):
            # Accept a spelling and canonicalize it; reject anything unknown.
            object.__setattr__(
                self,
                "version_relation",
                parse_version_relation(self.version_relation),
            )
        if self.schema_version == SOURCE_PROVENANCE_SCHEMA_V1 and any(
            getattr(self, name) is not None for name in V2_ENVELOPE_FIELD_NAMES
        ):
            raise SourceProvenanceError(
                "a source_provenance/1 document must not carry v2 envelope "
                "fields; use source_provenance/2"
            )

        # --- immutable copies: no shared mutable alias ---
        if not isinstance(self.unknown_fields, Mapping):
            raise SourceProvenanceError(
                "unknown_fields must be a mapping of unknown source keys"
            )
        for key in self.unknown_fields:
            if not isinstance(key, str):
                raise SourceProvenanceError(
                    "unknown_fields keys must be strings; coercion would lose "
                    "the source JSON shape"
                )
        object.__setattr__(
            self, "unknown_fields", copy.deepcopy(dict(self.unknown_fields))
        )
        if self.source_fields is not None:
            for name in self.source_fields:
                if not isinstance(name, str):
                    raise SourceProvenanceError(
                        "source_fields entries must be strings"
                    )
            object.__setattr__(
                self,
                "source_fields",
                tuple(self.source_fields),
            )

    # ------------------------------------------------------------------
    # schema and presence observability
    # ------------------------------------------------------------------

    def effective_schema_version(self) -> str:
        """The schema this object presents as, without silent downgrading.

        An object carrying any v2 envelope field reports as v2 even when
        ``schema_version`` itself was left unset.
        """
        if self.schema_version is not None:
            return self.schema_version
        if any(
            getattr(self, name) is not None for name in V2_ENVELOPE_FIELD_NAMES
        ):
            return SOURCE_PROVENANCE_SCHEMA_V2
        return SOURCE_PROVENANCE_SCHEMA_V1

    def is_field_present(self, name: str) -> bool:
        """True when ``name`` is part of this object's serialized key set."""
        return name in self.serialized_field_names()

    def serialized_field_names(self) -> tuple[str, ...]:
        """The exact key set :meth:`to_dict` will produce, in order."""
        if self.source_fields is not None:
            return self.source_fields
        names: list[str] = list(V1_FIELD_NAMES)
        if self.effective_schema_version() == SOURCE_PROVENANCE_SCHEMA_V2:
            names.insert(0, "schema_version")
        for name in V2_ENVELOPE_FIELD_NAMES:
            if getattr(self, name) is not None:
                names.append(name)
        names.extend(self.unknown_fields)
        return tuple(names)

    def absent_field_names(self) -> frozenset[str]:
        """Known field names this object does not serialize at all."""
        present = set(self.serialized_field_names())
        return frozenset(
            name for name in KNOWN_FIELD_NAMES if name not in present
        )

    # ------------------------------------------------------------------
    # audit surface
    # ------------------------------------------------------------------

    def source_reference(self) -> str:
        """Compact debug/audit reference; never used for dispatch."""
        method_index = (
            str(self.method_index)
            if self.method_index is not None
            else f"unregistered@{self.native_rva}"
        )
        return f"{self.game_version}:{self.runtime_type}.{self.method}:{method_index}"

    def dispatch_key(self) -> NoReturn:
        """Refuse to act as a runtime dispatch key.

        Present so that any attempt to branch execution on RVA, method index or
        provenance in general fails loudly instead of silently appearing to work.
        """
        raise SourceProvenanceError(
            "SourceProvenance is audit metadata and must not be used as a "
            "runtime dispatch key (native_rva and method_index are not "
            "execution inputs)"
        )

    # ------------------------------------------------------------------
    # serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize losslessly to a fresh, non-aliasing structure."""
        data: dict[str, Any] = {}
        version = self.effective_schema_version()
        for name in self.serialized_field_names():
            if name == "schema_version":
                data[name] = version
            elif name in self.unknown_fields:
                data[name] = self.unknown_fields[name]
            elif name == "version_relation" and self.version_relation is not None:
                data[name] = self.version_relation.serialize()
            else:
                data[name] = getattr(self, name, None)
        return copy.deepcopy(data)

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------

    @staticmethod
    def _present_source_fields(data: Mapping[str, Any]) -> tuple[str, ...]:
        fields = tuple(data.keys())
        if any(not isinstance(key, str) for key in fields):
            raise SourceProvenanceError(
                "provenance document keys must be strings; coercion would "
                "lose the source JSON shape"
            )
        return fields

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceProvenance":
        """Read a provenance document of either schema.

        Dispatches on ``schema_version``: absent or v1 reads as v1, v2 reads as
        v2, and an unknown schema is rejected rather than guessed.
        """
        if not isinstance(data, Mapping):
            raise SourceProvenanceError(
                "provenance document must be a mapping, got "
                f"{type(data).__name__}"
            )
        version = data.get("schema_version")
        if version is None or version == SOURCE_PROVENANCE_SCHEMA_V1:
            return cls.from_dict_v1(data)
        if version == SOURCE_PROVENANCE_SCHEMA_V2:
            return cls.from_dict_v2(data)
        raise SourceProvenanceError(
            f"unknown schema_version {version!r}; expected "
            f"{SOURCE_PROVENANCE_SCHEMA_V1!r} or "
            f"{SOURCE_PROVENANCE_SCHEMA_V2!r}"
        )

    @classmethod
    def from_dict_v1(cls, data: Mapping[str, Any]) -> "SourceProvenance":
        """Explicit v1 read.  Rejects v2 envelope content."""
        if not isinstance(data, Mapping):
            raise SourceProvenanceError(
                "provenance document must be a mapping, got "
                f"{type(data).__name__}"
            )
        present_v2 = [name for name in V2_ENVELOPE_FIELD_NAMES if name in data]
        if present_v2:
            raise SourceProvenanceError(
                "source_provenance/1 does not define "
                f"{sorted(present_v2)}; read it as source_provenance/2"
            )
        missing = [name for name in REQUIRED_V1_FIELD_NAMES if name not in data]
        if missing:
            raise SourceProvenanceError(
                f"v1 provenance document is missing required fields {missing}"
            )
        unknown = {
            key: copy.deepcopy(value)
            for key, value in data.items()
            if key not in V1_FIELD_NAMES and key != "schema_version"
        }
        try:
            return cls(
                game_version=data["game_version"],
                runtime_type=data["runtime_type"],
                method=data["method"],
                method_index=data["method_index"],
                native_rva=data["native_rva"],
                evidence_level=data["evidence_level"],
                note=data.get("note", PROVENANCE_NOTE_DEFAULT),
                schema_version=None,
                unknown_fields=unknown,
                source_fields=cls._present_source_fields(data),
            )
        except (SourceProvenanceError, TypeError):
            raise
        except KeyError as exc:
            raise SourceProvenanceError(
                f"invalid SourceProvenance dict: {exc}"
            ) from exc

    @classmethod
    def from_dict_v2(cls, data: Mapping[str, Any]) -> "SourceProvenance":
        """Explicit v2 read.  Requires the v2 marker; fills nothing in."""
        if not isinstance(data, Mapping):
            raise SourceProvenanceError(
                "provenance document must be a mapping, got "
                f"{type(data).__name__}"
            )
        if data.get("schema_version") != SOURCE_PROVENANCE_SCHEMA_V2:
            raise SourceProvenanceError(
                "a source_provenance/2 document must declare schema_version "
                f"{SOURCE_PROVENANCE_SCHEMA_V2!r}"
            )
        missing = [name for name in REQUIRED_V1_FIELD_NAMES if name not in data]
        if missing:
            raise SourceProvenanceError(
                f"v2 provenance document is missing required v1 fields {missing}"
            )
        unknown = {
            key: copy.deepcopy(value)
            for key, value in data.items()
            if key not in KNOWN_FIELD_NAMES
        }
        try:
            return cls(
                game_version=data["game_version"],
                runtime_type=data["runtime_type"],
                method=data["method"],
                method_index=data["method_index"],
                native_rva=data["native_rva"],
                evidence_level=data["evidence_level"],
                note=data.get("note", PROVENANCE_NOTE_DEFAULT),
                schema_version=SOURCE_PROVENANCE_SCHEMA_V2,
                source_commit=data.get("source_commit"),
                version_relation=data.get("version_relation"),
                content_sha256=data.get("content_sha256"),
                profile=data.get("profile"),
                unknown_fields=unknown,
                source_fields=cls._present_source_fields(data),
            )
        except (SourceProvenanceError, TypeError):
            raise
        except KeyError as exc:
            raise SourceProvenanceError(
                f"invalid SourceProvenance v2 dict: {exc}"
            ) from exc
