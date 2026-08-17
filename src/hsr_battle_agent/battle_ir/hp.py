# -*- coding: utf-8 -*-
"""Scoped HP-transition IR for Handoff 12.

This module contains only the minimal canonical representations needed by the
completed DirectDamageHP mode-0 contract:

* ``LockHPRecord`` - one ordered component[+0x50] lock record.  The action
  pointer is deliberately opaque and deterministic (``action_ref``); no
  gameplay name is attached.
* ``LockHPResult`` - the TryGetLockHP outcome: selected lock value and the
  forward ordered action references from the best index to list end.
* ``HPTransitionInput`` - neutral projection of the DirectDamageHP mode-0
  primitive inputs plus the unresolved NegativeHP property gate as an explicit
  deterministic input.
* ``HPTransitionResult`` - the observable transition result (current HP,
  applied delta, lock metadata, NegativeHP write metadata and boundary flags).

This is an HP transition contract, not a damage request or a general
NegativeHP runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hsr_battle_agent.battle_ir.targets import EntityRef

LOCK_RECORD_JSON_SCHEMA = "battle_ir_hp_lock_record/1"

_MASK64 = 0xFFFFFFFFFFFFFFFF


def _require_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")


def _require_qword_raw(value: int, name: str) -> None:
    _require_int(value, name)
    if not (-(2**63) <= value <= _MASK64):
        raise ValueError(f"{name} out of qword raw range: {value}")


def _validate_json_value(value: Any, where: str) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    raise TypeError(
        f"{where} must be a JSON-safe scalar for HP boundary projections, "
        f"got {type(value).__name__}"
    )


def _copy_json_value(value: Any) -> Any:
    _validate_json_value(value, "value")
    return value


@dataclass(frozen=True)
class LockHPRecord:
    """One ordered lock record from ``component[+0x50]``.

    Only the proven fields are represented:
    ``action_ref`` (opaque record[+0x20]), ``kind`` (record[+0x28] int32) and
    ``value`` (record[+0x30] FixPoint).
    """

    action_ref: str
    kind: int
    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.action_ref, str) or not self.action_ref:
            raise ValueError("action_ref must be a non-empty opaque string")
        _require_int(self.kind, "kind")
        _require_qword_raw(self.value, "value")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": LOCK_RECORD_JSON_SCHEMA,
            "kind_name": "LockHPRecord",
            "action_ref": self.action_ref,
            "kind": self.kind,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LockHPRecord":
        if not isinstance(data, Mapping):
            raise TypeError("LockHPRecord dict must be a mapping")
        if (
            data.get("schema") != LOCK_RECORD_JSON_SCHEMA
            or data.get("kind_name") != "LockHPRecord"
        ):
            raise ValueError(f"unsupported LockHPRecord dict: {data!r}")
        return cls(
            action_ref=str(data["action_ref"]),
            kind=int(data["kind"]),
            value=int(data["value"]),
        )

    def trace_summary(self) -> str:
        return (
            f"lock_hp_record:action:{self.action_ref}:"
            f"kind:{self.kind}:value:0x{self.value & _MASK64:X}"
        )


@dataclass(frozen=True)
class LockHPResult:
    """TryGetLockHP output projection.

    ``actions`` are the selected ordered opaque action references from the best
    index to list end in forward order.
    """

    success: bool
    lock_value: int
    actions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise TypeError("success must be bool")
        _require_qword_raw(self.lock_value, "lock_value")
        if not isinstance(self.actions, tuple):
            raise TypeError("actions must be a tuple")
        if not all(isinstance(item, str) for item in self.actions):
            raise TypeError("actions items must be opaque strings")

    def trace_summary(self) -> str:
        return (
            f"lock_hp_result:success:{self.success}:"
            f"lock:0x{self.lock_value & _MASK64:X}:"
            f"actions:{','.join(self.actions)}"
        )


@dataclass(frozen=True)
class HPTransitionInput:
    """Neutral DirectDamageHP mode-0 transition input projection.

    ``negative_hp_gate`` is the deterministic projection of the unresolved
    native post-write NegativeHP gate (feature byte + component[+0x20] list).
    The native fields are not modeled; callers supply the already-evaluated
    gate when the proven lock-overflow path is exercised.
    """

    component: EntityRef
    delta: int
    damage_kind: int
    context_token: Any = None
    input_record: Any = None
    mode: int = 0
    negative_hp_gate: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.component, EntityRef):
            raise TypeError(
                f"component must be EntityRef, got {type(self.component).__name__}"
            )
        _require_qword_raw(self.delta, "delta")
        _require_int(self.damage_kind, "damage_kind")
        _validate_json_value(self.context_token, "context_token")
        _validate_json_value(self.input_record, "input_record")
        _require_int(self.mode, "mode")
        if not isinstance(self.negative_hp_gate, bool):
            raise TypeError("negative_hp_gate must be bool")

    def trace_summary(self) -> str:
        return (
            f"hp_transition_input:entity:{self.component.runtime_id}:"
            f"delta:0x{self.delta & _MASK64:X}:kind:{self.damage_kind}:"
            f"mode:{self.mode}:neg_gate:{self.negative_hp_gate}"
        )


@dataclass(frozen=True)
class HPTransitionResult:
    """Observable DirectDamageHP mode-0 transition result.

    Persistent writes are reflected in BattleState; this result carries the
    deterministic output values and boundary flags for trace/reporting.
    """

    component: EntityRef
    old_current: int
    new_current: int
    applied_delta: int
    lock_hit: bool
    lock_value: int
    lock_actions: tuple[str, ...]
    flag: int
    p: int
    y: int
    negative_hp_written: bool
    old_negative: int | None
    new_negative: int | None
    negative_record_boundary: bool

    def __post_init__(self) -> None:
        if not isinstance(self.component, EntityRef):
            raise TypeError(
                f"component must be EntityRef, got {type(self.component).__name__}"
            )
        for name in (
            "old_current",
            "new_current",
            "applied_delta",
            "lock_value",
            "p",
            "y",
        ):
            _require_qword_raw(getattr(self, name), name)
        if not isinstance(self.lock_hit, bool):
            raise TypeError("lock_hit must be bool")
        if not isinstance(self.lock_actions, tuple):
            raise TypeError("lock_actions must be a tuple")
        if not all(isinstance(item, str) for item in self.lock_actions):
            raise TypeError("lock_actions items must be opaque strings")
        _require_int(self.flag, "flag")
        if self.flag not in (0, 1):
            raise ValueError("flag must be 0 or 1")
        if not isinstance(self.negative_hp_written, bool):
            raise TypeError("negative_hp_written must be bool")
        if self.old_negative is not None:
            _require_qword_raw(self.old_negative, "old_negative")
        if self.new_negative is not None:
            _require_qword_raw(self.new_negative, "new_negative")
        if not isinstance(self.negative_record_boundary, bool):
            raise TypeError("negative_record_boundary must be bool")

    def trace_summary(self) -> str:
        return (
            f"hp_transition_result:entity:{self.component.runtime_id}:"
            f"old:0x{self.old_current & _MASK64:X}:"
            f"new:0x{self.new_current & _MASK64:X}:"
            f"applied:0x{self.applied_delta & _MASK64:X}:"
            f"lock_hit:{self.lock_hit}:lock:0x{self.lock_value & _MASK64:X}:"
            f"actions:{','.join(self.lock_actions)}:"
            f"flag:{self.flag}:p:0x{self.p & _MASK64:X}:"
            f"y:0x{self.y & _MASK64:X}:"
            f"neg_write:{self.negative_hp_written}:"
            f"neg_record:{self.negative_record_boundary}"
        )
