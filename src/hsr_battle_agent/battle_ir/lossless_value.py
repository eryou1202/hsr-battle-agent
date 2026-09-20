# -*- coding: utf-8 -*-
"""Lossless value envelopes for absent, null and present distinction.

F01-005 introduces :class:`PresenceValue`.  F01-006 extends this module with
``LosslessNumber``; the two share the strictness rules established here.

Why this exists
---------------

``None`` cannot express both "the key is not there" and "the key is there and
its value is null".  Collapsing them loses information that the frozen authority
requires to stay observable, so presence is modelled explicitly with three
states:

``ABSENT``
    The key was not present at all.  Carries no payload.
``NULL``
    The key was present with a null value.  Carries no payload.
``PRESENT``
    The key was present with a non-null value, *whatever* that value is.  A
    false, zero, empty-string, empty-list, list-containing-null or empty-mapping
    value is still PRESENT.

Rules enforced here
-------------------

* ``ABSENT`` with a payload is invalid.
* ``NULL`` with a non-null payload is invalid.
* ``PRESENT(None)`` is invalid: ``NULL`` is the one encoding for a null value, so
  two encodings of the same state can never coexist.
* The API exposes no defaulting, no truthiness and no None-as-absence shortcut.
  ``require_present()`` returns the value or raises; there is deliberately no
  ``or_else``/``value_or``/``unwrap_or``.
* Values are never converted: a tuple stays a tuple.  (A JSON transport will of
  course turn tuples into arrays; the in-process envelope does not do that for
  you.)
"""
from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable, Mapping, NoReturn

__all__ = [
    "LOSSLESS_NUMBER_SCHEMA",
    "NUMERIC_CATEGORIES",
    "PRESENCE_STATES",
    "PRESENCE_VALUE_SCHEMA",
    "LosslessNumber",
    "LosslessValueError",
    "NumericCategory",
    "PresenceState",
    "PresenceValue",
    "PresenceValueError",
    "require_exact_integer",
]


class PresenceValueError(ValueError):
    """Raised for an invalid presence encoding."""


class LosslessValueError(ValueError):
    """Raised for a lossy or malformed numeric encoding."""


class PresenceState(Enum):
    """The three mutually exclusive presence states.

    Not a ``str`` mixin, for the same reason as ``EvidenceMode``: accidental
    string equality and meaningless ordering are both undesirable.  ``__bool__``
    refuses so that a state can never be used as a falsey presence check.
    """

    ABSENT = "ABSENT"
    NULL = "NULL"
    PRESENT = "PRESENT"

    def __bool__(self) -> NoReturn:
        raise PresenceValueError(
            f"PresenceState.{self.name} is a presence classification, not a "
            "boolean; use is_absent()/is_null()/is_present()"
        )

    def serialize(self) -> str:
        return str(self.value)

    @classmethod
    def spellings(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)


PRESENCE_STATES: tuple[str, ...] = PresenceState.spellings()

PRESENCE_VALUE_SCHEMA = "presence_value/1"

#: Marker meaning "this envelope carries no payload at all".
_NO_VALUE = object()


def _parse_state(value: Any) -> PresenceState:
    if isinstance(value, PresenceState):
        return value
    if value is None:
        raise PresenceValueError(
            "presence state cannot be absent; absence is a state, not a "
            "missing argument"
        )
    if not isinstance(value, str):
        raise PresenceValueError(
            f"presence state must be a serialized string, got {type(value).__name__}"
        )
    try:
        return PresenceState(value)
    except ValueError:
        raise PresenceValueError(
            f"unknown presence state {value!r}; expected one of {PRESENCE_STATES}"
        ) from None


def is_no_value(candidate: Any) -> bool:
    """True when ``candidate`` is the internal no-payload marker."""
    return candidate is _NO_VALUE


@dataclass(frozen=True)
class PresenceValue:
    """A value together with its explicit presence state."""

    state: PresenceState
    value: Any = field(default=_NO_VALUE)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", _parse_state(self.state))
        carries = self.value is not _NO_VALUE

        if self.state is PresenceState.ABSENT:
            if carries:
                raise PresenceValueError(
                    "ABSENT must not carry a payload; an absent key has no value"
                )
            return

        if self.state is PresenceState.NULL:
            if carries:
                if self.value is not None:
                    raise PresenceValueError(
                        "NULL must not carry a non-null payload; use PRESENT for "
                        "a value, or omit the payload entirely"
                    )
                # Normalize the explicit-null form onto the single canonical
                # NULL representation, so NULL can never have two encodings.
                object.__setattr__(self, "value", _NO_VALUE)
            return

        # PRESENT
        if not carries:
            raise PresenceValueError(
                "PRESENT requires a payload; use ABSENT or NULL when there is "
                "no value"
            )
        if self.value is None:
            raise PresenceValueError(
                "PRESENT(None) is invalid: NULL is the single encoding of a "
                "null value, so two encodings of the same state cannot coexist"
            )
        # Frozen dataclass syntax alone does not freeze a nested list/dict.
        # Capture an independent value so caller mutation cannot rewrite the
        # presence observation after construction.
        object.__setattr__(self, "value", copy.deepcopy(self.value))

    def __bool__(self) -> NoReturn:
        raise PresenceValueError(
            "PresenceValue has no truthiness; use is_absent()/is_null()/"
            "is_present() and require_present()"
        )

    # -- constructors ----------------------------------------------------

    @classmethod
    def absent(cls) -> "PresenceValue":
        return cls(state=PresenceState.ABSENT)

    @classmethod
    def null(cls) -> "PresenceValue":
        return cls(state=PresenceState.NULL)

    @classmethod
    def present(cls, value: Any) -> "PresenceValue":
        """Wrap a non-null, present value, preserving its exact type."""
        if value is None:
            raise PresenceValueError(
                "PresenceValue.present(None) is invalid; use PresenceValue.null() "
                "for a present null value"
            )
        return cls(state=PresenceState.PRESENT, value=value)

    # -- state queries (never truthiness) --------------------------------

    def is_absent(self) -> bool:
        return self.state is PresenceState.ABSENT

    def is_null(self) -> bool:
        return self.state is PresenceState.NULL

    def is_present(self) -> bool:
        return self.state is PresenceState.PRESENT

    def require_present(self) -> Any:
        """Return the payload, or raise.  Never supplies a default."""
        if self.state is not PresenceState.PRESENT:
            raise PresenceValueError(
                f"require_present() called on a {self.state.value} value; there "
                "is no default and no fallback"
            )
        return self.value

    def missing_payload(self) -> NoReturn:
        """Refuse: nothing may substitute a default for a missing payload."""
        raise PresenceValueError(
            "no default value is available for an absent or null presence; "
            "handle the state explicitly"
        )

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": PRESENCE_VALUE_SCHEMA,
            "presence": self.state.value,
        }
        if self.state is PresenceState.PRESENT:
            payload["value"] = copy.deepcopy(self.value)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PresenceValue":
        if not isinstance(data, Mapping):
            raise PresenceValueError(
                f"PresenceValue document must be a mapping, got "
                f"{type(data).__name__}"
            )
        schema = data["schema"] if "schema" in data else PRESENCE_VALUE_SCHEMA
        if schema != PRESENCE_VALUE_SCHEMA:
            raise PresenceValueError(
                f"unknown PresenceValue schema {schema!r}; expected "
                f"{PRESENCE_VALUE_SCHEMA!r}"
            )
        if "presence" not in data:
            raise PresenceValueError(
                "PresenceValue document is missing the 'presence' field"
            )
        state = _parse_state(data["presence"])
        if state is PresenceState.PRESENT:
            if "value" not in data:
                raise PresenceValueError(
                    "a PRESENT document must carry a 'value' field"
                )
            return cls.present(copy.deepcopy(data["value"]))
        if "value" in data:
            # Presence of the key is what matters, never its truthiness.
            if state is PresenceState.NULL and data["value"] is None:
                return cls.null()
            raise PresenceValueError(
                f"{state.value} must not carry a 'value' field"
            )
        return cls(state=state)

    # -- batch helpers ---------------------------------------------------

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], key: str) -> "PresenceValue":
        """Read ``key`` from a mapping without any default-based decoding.

        Uses membership, never ``get(key, default)``, so absence and null stay
        distinguishable.
        """
        if not isinstance(data, Mapping):
            raise PresenceValueError(
                f"source must be a mapping, got {type(data).__name__}"
            )
        if key not in data:
            return cls.absent()
        raw = data[key]
        if raw is None:
            return cls.null()
        return cls.present(copy.deepcopy(raw))

    @classmethod
    def matrix(cls, keys: Iterable[str], data: Mapping[str, Any]) -> dict[str, "PresenceValue"]:
        """Presence for several keys at once, in the given key order."""
        return {key: cls.from_mapping(data, key) for key in keys}


# ---------------------------------------------------------------------------
# LosslessNumber (F01-006)
# ---------------------------------------------------------------------------

LOSSLESS_NUMBER_SCHEMA = "lossless_number/1"

_INTEGER_LEXEME_RE = re.compile(r"\A[+-]?[0-9]+\Z")
_DECIMAL_LEXEME_RE = re.compile(
    r"\A[+-]?(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?\Z"
)
_NON_FINITE_LEXEMES = frozenset(
    {
        "nan", "+nan", "-nan",
        "inf", "+inf", "-inf",
        "infinity", "+infinity", "-infinity",
    }
)


class NumericCategory(Enum):
    """The numeric category a source literal belongs to.

    Not a ``str`` mixin, and ``__bool__`` refuses, so a category can never be
    used as a truthiness or executability flag.
    """

    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    FLOAT = "FLOAT"

    def __bool__(self) -> NoReturn:
        raise LosslessValueError(
            f"NumericCategory.{self.name} is a numeric classification, not a "
            "boolean; compare with is"
        )

    def serialize(self) -> str:
        return str(self.value)

    @classmethod
    def spellings(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)


NUMERIC_CATEGORIES: tuple[str, ...] = NumericCategory.spellings()


def _parse_category(value: Any) -> NumericCategory:
    if isinstance(value, NumericCategory):
        return value
    if value is None or not isinstance(value, str):
        raise LosslessValueError(
            f"numeric category must be a serialized string, got "
            f"{type(value).__name__}"
        )
    try:
        return NumericCategory(value)
    except ValueError:
        raise LosslessValueError(
            f"unknown numeric category {value!r}; expected one of "
            f"{NUMERIC_CATEGORIES}"
        ) from None


@dataclass(frozen=True)
class LosslessNumber:
    """A number plus the exact source lexeme and numeric category it came from.

    Preserved exactly:

    * the **source lexeme** -- the literal text, so ``"0.10"`` and ``"0.1"``
      stay distinguishable even though they denote the same value;
    * the **numeric category** -- so ``1`` (INTEGER) and ``1.0`` (DECIMAL) are
      never the same object;
    * **exact integer identity** -- an integer of any size is held as a Python
      ``int`` and never passes through ``float``, so values beyond 2**53
      round-trip exactly.

    Non-finite values (nan, inf, -inf, and their textual spellings) are rejected
    outright: they are not numbers that can be compared or ordered exactly.
    """

    lexeme: str
    category: NumericCategory

    def __post_init__(self) -> None:
        object.__setattr__(self, "category", _parse_category(self.category))
        object.__setattr__(
            self, "lexeme", self._validate_lexeme(self.lexeme, self.category)
        )

    @staticmethod
    def _validate_lexeme(value: Any, category: NumericCategory) -> str:
        if not isinstance(value, str) or not value:
            raise LosslessValueError(
                "numeric lexeme must be a non-empty string"
            )
        if value.strip() != value:
            raise LosslessValueError(
                f"numeric lexeme {value!r} must not carry surrounding whitespace"
            )
        if "_" in value:
            raise LosslessValueError(
                f"numeric lexeme {value!r} must not contain digit separators"
            )
        lowered = value.lower()
        if lowered in _NON_FINITE_LEXEMES:
            raise LosslessValueError(
                f"non-finite numeric lexeme {value!r} is rejected: nan and inf "
                "have no exact identity"
            )
        if category is NumericCategory.INTEGER:
            if not _INTEGER_LEXEME_RE.match(value):
                raise LosslessValueError(
                    f"lexeme {value!r} is not an integer literal for category "
                    "INTEGER"
                )
            return value
        if category is NumericCategory.DECIMAL:
            if not _DECIMAL_LEXEME_RE.match(value):
                raise LosslessValueError(
                    f"lexeme {value!r} is not a decimal literal for category "
                    "DECIMAL"
                )
            try:
                Decimal(value)
            except InvalidOperation as exc:
                raise LosslessValueError(
                    f"lexeme {value!r} is not an exact decimal: {exc}"
                ) from exc
            return value
        # FLOAT
        if not _DECIMAL_LEXEME_RE.match(value):
            raise LosslessValueError(
                f"lexeme {value!r} is not a numeric literal for category FLOAT"
            )
        try:
            parsed = float(value)
        except ValueError as exc:
            raise LosslessValueError(
                f"lexeme {value!r} is not a finite float: {exc}"
            ) from exc
        if not math.isfinite(parsed):
            raise LosslessValueError(
                f"lexeme {value!r} resolves to a non-finite float, which is "
                "rejected"
            )
        return value

    # -- constructors ----------------------------------------------------

    @classmethod
    def from_lexeme(cls, lexeme: str) -> "LosslessNumber":
        """Build from a source literal, choosing the category from its shape."""
        if not isinstance(lexeme, str) or not lexeme:
            raise LosslessValueError(
                "LosslessNumber.from_lexeme requires a non-empty literal string"
            )
        if _INTEGER_LEXEME_RE.match(lexeme):
            return cls(lexeme=lexeme, category=NumericCategory.INTEGER)
        if "." in lexeme or "e" in lexeme or "E" in lexeme:
            return cls(lexeme=lexeme, category=NumericCategory.DECIMAL)
        raise LosslessValueError(f"unsupported numeric lexeme {lexeme!r}")

    @classmethod
    def from_int(cls, value: int) -> "LosslessNumber":
        if isinstance(value, bool) or not isinstance(value, int):
            raise LosslessValueError(
                f"from_int requires a Python int, got {type(value).__name__}"
            )
        return cls(lexeme=str(value), category=NumericCategory.INTEGER)

    @classmethod
    def from_decimal(cls, value: Decimal | str) -> "LosslessNumber":
        if isinstance(value, bool) or not isinstance(value, (Decimal, str)):
            raise LosslessValueError(
                "from_decimal requires a Decimal or a decimal string"
            )
        text = str(value)
        return cls(lexeme=text, category=NumericCategory.DECIMAL)

    @classmethod
    def from_float(cls, value: float) -> "LosslessNumber":
        """Build from a binary float, keeping only the exact finite literal."""
        if isinstance(value, bool) or not isinstance(value, float):
            raise LosslessValueError(
                f"from_float requires a Python float, got {type(value).__name__}"
            )
        if not math.isfinite(value):
            raise LosslessValueError(
                f"non-finite float {value!r} is rejected: it has no exact identity"
            )
        return cls(lexeme=repr(value), category=NumericCategory.FLOAT)

    @classmethod
    def from_source(cls, value: Any) -> "LosslessNumber":
        """Build from a decoded source value without losing its category."""
        if isinstance(value, bool):
            raise LosslessValueError(
                "booleans are not numbers; keep them in a PresenceValue"
            )
        if isinstance(value, int):
            return cls.from_int(value)
        if isinstance(value, Decimal):
            return cls.from_decimal(value)
        if isinstance(value, float):
            return cls.from_float(value)
        if isinstance(value, str):
            return cls.from_lexeme(value)
        raise LosslessValueError(
            f"cannot represent {type(value).__name__} as a LosslessNumber"
        )

    # -- values ----------------------------------------------------------

    def is_integer(self) -> bool:
        return self.category is NumericCategory.INTEGER

    def require_int(self) -> int:
        """Exact integer identity, or raise.  Never goes through float."""
        if self.category is not NumericCategory.INTEGER:
            raise LosslessValueError(
                f"{self.lexeme!r} is {self.category.value}, not an exact integer; "
                "refusing to normalize it through float"
            )
        return int(self.lexeme)

    def as_decimal(self) -> Decimal:
        """Exact decimal value for INTEGER and DECIMAL categories."""
        if self.category is NumericCategory.FLOAT:
            raise LosslessValueError(
                f"{self.lexeme!r} is a binary FLOAT; use as_float_lossy() and "
                "acknowledge the loss"
            )
        return Decimal(self.lexeme)

    def as_float_lossy(self) -> float:
        """Convert to ``float``, explicitly acknowledging a possible loss."""
        return float(self.lexeme)

    def to_python(self) -> Any:
        """The exact Python value for this category.

        ``INTEGER`` gives ``int`` (exact at any size), ``DECIMAL`` gives
        ``Decimal`` (exact base-10), ``FLOAT`` gives ``float``.
        """
        if self.category is NumericCategory.INTEGER:
            return int(self.lexeme)
        if self.category is NumericCategory.DECIMAL:
            return Decimal(self.lexeme)
        return float(self.lexeme)

    def __bool__(self) -> NoReturn:
        raise LosslessValueError(
            "LosslessNumber has no truthiness; compare it explicitly"
        )

    # -- serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": LOSSLESS_NUMBER_SCHEMA,
            "category": self.category.value,
            "lexeme": self.lexeme,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LosslessNumber":
        if not isinstance(data, Mapping):
            raise LosslessValueError(
                f"LosslessNumber document must be a mapping, got "
                f"{type(data).__name__}"
            )
        schema = data["schema"] if "schema" in data else LOSSLESS_NUMBER_SCHEMA
        if schema != LOSSLESS_NUMBER_SCHEMA:
            raise LosslessValueError(
                f"unknown LosslessNumber schema {schema!r}; expected "
                f"{LOSSLESS_NUMBER_SCHEMA!r}"
            )
        if "category" not in data:
            raise LosslessValueError(
                "LosslessNumber document is missing the 'category' field"
            )
        if "lexeme" not in data:
            raise LosslessValueError(
                "LosslessNumber document is missing the 'lexeme' field"
            )
        return cls(lexeme=data["lexeme"], category=data["category"])


def require_exact_integer(value: Any) -> int:
    """Return an exact integer identity, refusing any float normalization.

    Identifiers must never be routed through ``float``: values above 2**53 are
    silently rounded and two distinct identifiers can collide.
    """
    if isinstance(value, bool):
        raise LosslessValueError("booleans are not integer identifiers")
    if isinstance(value, int):
        return value
    if isinstance(value, LosslessNumber):
        return value.require_int()
    if isinstance(value, float):
        raise LosslessValueError(
            f"refusing to use the float {value!r} as an identifier: float "
            "normalization loses exactness above 2**53"
        )
    if isinstance(value, str):
        if not _INTEGER_LEXEME_RE.match(value):
            raise LosslessValueError(
                f"refusing to use {value!r} as an integer identifier: it is not "
                "an exact integer literal"
            )
        return int(value)
    raise LosslessValueError(
        f"cannot take an exact integer identity from {type(value).__name__}"
    )
