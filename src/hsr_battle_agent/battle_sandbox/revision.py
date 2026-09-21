# -*- coding: utf-8 -*-
"""State revision value object for the Terra local state path.

TERRA F02-005.  A revision is an immutable, monotonically advancing counter that
        labels a state snapshot.  It is a **value object**: it holds no state mutation
capability, it exposes no clock and no object identity, and it can only advance
through an explicit, named call.

Hard rules enforced here
------------------------

* **Monotonic.**  A revision only ever advances.  :meth:`StateRevision.advance`
  moves the counter forward by exactly one and can never go backwards, and
  construction rejects a negative counter.
* **No wall-clock input.**  Reading a clock is not an input to a revision, and
  :meth:`StateRevision.from_wall_clock` refuses explicitly, so two runs can never
  disagree merely because of when they ran.
* **No object-address input.**  :meth:`StateRevision.from_object_address`
  refuses, so identity is never derived from ``id()`` or memory layout.
* **Snapshot identity is recorded.**  Each revision carries the snapshot token it
  labels, and staleness is compared only inside one lineage. Different snapshot
  tokens with ordered counters in the same lineage remain comparable; equal
  counters with different tokens are incomparable, and unrelated lineages are
  refused.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, NoReturn

__all__ = [
    "REVISION_SCHEMA",
    "REVISION_SEQUENCE_SCHEMA",
    "RevisionAndTransactionSequence",
    "StateRevision",
    "StateRevisionError",
]

REVISION_SCHEMA = "state_revision/1"
REVISION_SEQUENCE_SCHEMA = "revision_and_transaction_sequence/1"


class StateRevisionError(ValueError):
    """Raised for a malformed revision or an illegal revision operation."""


def _validate_counter(counter: Any) -> int:
    if isinstance(counter, bool) or not isinstance(counter, int):
        raise StateRevisionError(
            f"revision counter must be an int, got {type(counter).__name__}"
        )
    if counter < 0:
        raise StateRevisionError("revision counter must be >= 0")
    return counter


def _validate_token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise StateRevisionError(f"{label} must be a non-empty string")
    return value


@dataclass(frozen=True)
class StateRevision:
    """An immutable, monotonically advancing revision with snapshot identity."""

    counter: int
    snapshot_id: str
    lineage: str = "default"

    def __post_init__(self) -> None:
        object.__setattr__(self, "counter", _validate_counter(self.counter))
        object.__setattr__(
            self,
            "snapshot_id",
            _validate_token(self.snapshot_id, "snapshot_id"),
        )
        object.__setattr__(
            self, "lineage", _validate_token(self.lineage, "lineage")
        )

    # -- constructors ----------------------------------------------------

    @classmethod
    def initial(cls, snapshot_id: str, *, lineage: str = "default") -> "StateRevision":
        """The zero revision of a snapshot lineage."""
        return cls(counter=0, snapshot_id=snapshot_id, lineage=lineage)

    @classmethod
    def from_wall_clock(cls, *_args: Any, **_kwargs: Any) -> NoReturn:
        """Refuse: a revision never reads a clock."""
        raise StateRevisionError(
            "revision must not be derived from wall-clock time; a revision "
            "advances through an explicit named call only"
        )

    @classmethod
    def from_object_address(cls, *_args: Any, **_kwargs: Any) -> NoReturn:
        """Refuse: a revision never derives identity from an object address."""
        raise StateRevisionError(
            "revision must not be derived from an object address or memory "
            "layout; that is not stable state identity"
        )

    # -- advancement -----------------------------------------------------

    def advance(self, *, contract: str, snapshot_id: str | None = None) -> "StateRevision":
        """Advance by exactly one under an explicit named contract.

        The counter only ever moves forward.  A new ``snapshot_id`` may be given
        when the advance also produces a new snapshot token; otherwise the
        current token is retained.
        """
        if not isinstance(contract, str) or not contract:
            raise StateRevisionError(
                "advance() requires a non-empty named contract; a revision never "
                "advances implicitly"
            )
        next_snapshot = (
            self.snapshot_id
            if snapshot_id is None
            else _validate_token(snapshot_id, "snapshot_id")
        )
        return StateRevision(
            counter=self.counter + 1,
            snapshot_id=next_snapshot,
            lineage=self.lineage,
        )

    def advance_by(self, steps: int, *, contract: str) -> "StateRevision":
        """Advance by a positive number of steps under a named contract."""
        if isinstance(steps, bool) or not isinstance(steps, int):
            raise StateRevisionError(
                f"steps must be an int, got {type(steps).__name__}"
            )
        if steps <= 0:
            raise StateRevisionError(
                "steps must be > 0; a revision never goes backwards and a "
                "zero-step advance is a no-op"
            )
        if not isinstance(contract, str) or not contract:
            raise StateRevisionError(
                "advance_by() requires a non-empty named contract"
            )
        return StateRevision(
            counter=self.counter + steps,
            snapshot_id=self.snapshot_id,
            lineage=self.lineage,
        )

    # -- comparison ------------------------------------------------------

    def compare(self, other: "StateRevision") -> int:
        """Return -1, 0 or 1 within one snapshot lineage.

        Ordering is defined by the counter. Comparing across lineages is
        refused. Different snapshot tokens in the same lineage remain
        comparable when their counters order them; equal counters with
        different tokens are refused because neither token can be selected as
        the current point without inventing an ordering.
        """
        if not isinstance(other, StateRevision):
            raise StateRevisionError(
                f"compare() requires a StateRevision, got {type(other).__name__}"
            )
        self.require_same_lineage(other)
        if self.counter < other.counter:
            return -1
        if self.counter > other.counter:
            return 1
        if self.snapshot_id != other.snapshot_id:
            raise StateRevisionError(
                "equal counters with different snapshot identities are "
                "incomparable; neither revision may be treated as current"
            )
        return 0

    def is_stale_against(self, observed: "StateRevision") -> bool:
        """True when this revision is older than the observed revision."""
        return self.compare(observed) < 0

    def is_current_for(self, observed: "StateRevision") -> bool:
        """True when both revisions label the same point in the lineage."""
        return self.compare(observed) == 0

    def supersedes(self, other: "StateRevision") -> bool:
        """True when this revision is strictly newer than ``other``."""
        return self.compare(other) > 0

    def same_snapshot(self, other: "StateRevision") -> bool:
        if not isinstance(other, StateRevision):
            return False
        return (
            self.snapshot_id == other.snapshot_id
            and self.lineage == other.lineage
        )

    def require_same_snapshot(self, other: "StateRevision") -> None:
        """Raise unless both values label the exact same snapshot token."""
        self.require_same_lineage(other)
        if self.snapshot_id != other.snapshot_id:
            raise StateRevisionError(
                f"snapshot identities differ: {self.snapshot_id!r} and "
                f"{other.snapshot_id!r}"
            )

    def require_same_lineage(self, other: "StateRevision") -> None:
        """Raise when two revisions belong to unrelated lineages."""
        if not isinstance(other, StateRevision):
            raise StateRevisionError(
                f"expected a StateRevision, got {type(other).__name__}"
            )
        if self.lineage != other.lineage:
            raise StateRevisionError(
                f"cannot compare revisions across lineages "
                f"{self.lineage!r} and {other.lineage!r}"
            )

    # -- guards ----------------------------------------------------------

    def __bool__(self) -> NoReturn:
        raise StateRevisionError(
            "StateRevision has no truthiness; compare it explicitly"
        )

    def identity(self) -> str:
        """Stable audit label for this revision."""
        return f"{self.lineage}:{self.snapshot_id}@{self.counter}"

    def execution_permitted(self) -> NoReturn:
        """Refuse: a revision label is not an execution permission."""
        raise StateRevisionError(
            "a StateRevision labels state, it does not permit execution"
        )

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REVISION_SCHEMA,
            "counter": self.counter,
            "snapshot_id": self.snapshot_id,
            "lineage": self.lineage,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StateRevision":
        if not isinstance(data, Mapping):
            raise StateRevisionError(
                f"revision document must be a mapping, got {type(data).__name__}"
            )
        required = {"schema", "counter", "snapshot_id", "lineage"}
        if set(data) != required:
            raise StateRevisionError(
                "revision document must contain exactly schema, counter, "
                "snapshot_id and lineage"
            )
        schema = data["schema"]
        if schema != REVISION_SCHEMA:
            raise StateRevisionError(
                f"unknown revision schema {schema!r}; expected {REVISION_SCHEMA!r}"
            )
        return cls(
            counter=data["counter"],
            snapshot_id=data["snapshot_id"],
            lineage=data["lineage"],
        )


def _validate_local_sequence(value: Any, label: str) -> int:
    """Validate a deterministic local sequence value without native claims."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise StateRevisionError(
            f"{label} must be an explicit int, got {type(value).__name__}"
        )
    if value < 0:
        raise StateRevisionError(f"{label} must be >= 0")
    return value


@dataclass(frozen=True)
class RevisionAndTransactionSequence:
    """The complete frozen revision-and-sequence field-family shape.

    ``replay_sequence`` and ``committed_effect_sequence`` are deterministic
    local ordering values only.  Their required, explicit construction avoids
    silently inventing zero/default state, and this representation makes no
    claim about client-native counters or transaction behavior.
    """

    published_revision: StateRevision
    replay_sequence: int
    committed_effect_sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.published_revision, StateRevision):
            raise StateRevisionError(
                "published_revision must be a StateRevision"
            )
        object.__setattr__(
            self,
            "replay_sequence",
            _validate_local_sequence(self.replay_sequence, "replay_sequence"),
        )
        object.__setattr__(
            self,
            "committed_effect_sequence",
            _validate_local_sequence(
                self.committed_effect_sequence,
                "committed_effect_sequence",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REVISION_SEQUENCE_SCHEMA,
            "published_revision": self.published_revision.to_dict(),
            "replay_sequence": self.replay_sequence,
            "committed_effect_sequence": self.committed_effect_sequence,
        }

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any]
    ) -> "RevisionAndTransactionSequence":
        if not isinstance(data, Mapping):
            raise StateRevisionError(
                "revision-and-transaction-sequence document must be a mapping"
            )
        expected = {
            "schema",
            "published_revision",
            "replay_sequence",
            "committed_effect_sequence",
        }
        if set(data) != expected:
            raise StateRevisionError(
                "revision-and-transaction-sequence document must contain "
                "exactly schema, published_revision, replay_sequence and "
                "committed_effect_sequence"
            )
        if data["schema"] != REVISION_SEQUENCE_SCHEMA:
            raise StateRevisionError(
                "unknown revision-and-transaction-sequence schema "
                f"{data['schema']!r}; expected {REVISION_SEQUENCE_SCHEMA!r}"
            )
        return cls(
            published_revision=StateRevision.from_dict(
                data["published_revision"]
            ),
            replay_sequence=data["replay_sequence"],
            committed_effect_sequence=data["committed_effect_sequence"],
        )
