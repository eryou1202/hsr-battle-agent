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
  labels, and staleness is only compared inside one snapshot lineage:
  :meth:`StateRevision.require_same_snapshot` refuses a cross-snapshot
  comparison rather than inventing an ordering between unrelated snapshots.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Mapping, NoReturn

__all__ = [
    "REVISION_SCHEMA",
    "StateRevision",
    "StateRevisionError",
]

REVISION_SCHEMA = "state_revision/1"


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

        Ordering is defined by the counter alone.  Comparing across lineages or
        snapshot identities is refused rather than guessed.
        """
        if not isinstance(other, StateRevision):
            raise StateRevisionError(
                f"compare() requires a StateRevision, got {type(other).__name__}"
            )
        self.require_same_snapshot(other)
        if self.counter < other.counter:
            return -1
        if self.counter > other.counter:
            return 1
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
        """Raise when two revisions belong to different snapshot identities."""
        if not isinstance(other, StateRevision):
            raise StateRevisionError(
                f"expected a StateRevision, got {type(other).__name__}"
            )
        if self.lineage != other.lineage:
            raise StateRevisionError(
                f"cannot compare revisions across lineages "
                f"{self.lineage!r} and {other.lineage!r}"
            )
        if self.snapshot_id != other.snapshot_id:
            raise StateRevisionError(
                f"cannot compare revisions across snapshot identities "
                f"{self.snapshot_id!r} and {other.snapshot_id!r}"
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
        schema = data["schema"] if "schema" in data else REVISION_SCHEMA
        if schema != REVISION_SCHEMA:
            raise StateRevisionError(
                f"unknown revision schema {schema!r}; expected {REVISION_SCHEMA!r}"
            )
        for name in ("counter", "snapshot_id"):
            if name not in data:
                raise StateRevisionError(
                    f"revision document is missing required field {name!r}"
                )
        return cls(
            counter=data["counter"],
            snapshot_id=data["snapshot_id"],
            lineage=data["lineage"] if "lineage" in data else "default",
        )
