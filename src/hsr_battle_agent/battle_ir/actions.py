# -*- coding: utf-8 -*-
"""Canonical Action Execution Bridge 06 IR.

The recovered runtime layer is the generated task executor runtime
(``TaskConfig`` DSL -> generated executor -> ``OnTaskBegin`` /
``OnTaskReset`` / ``Tick`` / ``Dispose`` -> ``TaskState`` transition).
This module contains only the minimal representations proven by
``data/semantics/4.4.54/action_execution_bridge_06.json`` (E4):

* ``TaskState``  - raw int32 at executor [+0x10].
* ``TaskExecutionState`` - immutable snapshot of the proven executor slots
  (task state, config reference, selected target, next phase).

No Action AST, damage descriptor, modifier descriptor or event descriptor is
pre-built here; those enter only when a future semantic batch proves them.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from hsr_battle_agent.battle_ir.targets import EntityRef


class TaskState(IntEnum):
    """Recovered ``RPG.GameCore.TaskState`` (type 54932) raw values.

    Values are the exact int32 constants stored at generated task executor
    [+0x10] by the accepted native bodies (E4).
    """

    READY = 0x7777
    EXECUTING = 0x8888
    SUCCESS = 0x9999
    FAIL = 0xAAAA

    def trace_summary(self) -> str:
        return f"TaskState.{self.name}"


@dataclass(frozen=True)
class TaskExecutionState:
    """Immutable canonical projection of the proven generated executor slots.

    ``task_state``     - executor [+0x10] (TaskState).
    ``config_ref``     - executor config slot (native pointer; canonical
                         JSON-safe reference string or ``None``).
    ``selected_target``- executor selected-target slot (CPHGMLEAPJL [+0x28]);
                         EntityRef or ``None``.
    ``next_phase``     - canonical tailcall marker for the next lifecycle
                         phase proven by the accepted leaves (``"Tick"`` or
                         ``None``).
    """

    task_state: TaskState = TaskState.READY
    config_ref: str | None = None
    selected_target: EntityRef | None = None
    next_phase: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.task_state, TaskState):
            raise TypeError(f"task_state must be TaskState, got {type(self.task_state).__name__}")
        if self.config_ref is not None and not isinstance(self.config_ref, str):
            raise TypeError(f"config_ref must be str or None, got {type(self.config_ref).__name__}")
        if self.selected_target is not None and not isinstance(self.selected_target, EntityRef):
            raise TypeError(
                "selected_target must be EntityRef or None, "
                f"got {type(self.selected_target).__name__}"
            )
        if self.next_phase is not None and not isinstance(self.next_phase, str):
            raise TypeError(f"next_phase must be str or None, got {type(self.next_phase).__name__}")

    def trace_summary(self) -> str:
        target = (
            "None"
            if self.selected_target is None
            else self.selected_target.trace_summary()
        )
        config = "None" if self.config_ref is None else repr(self.config_ref)
        return (
            f"TaskExecutionState(task_state={self.task_state.name}, "
            f"config_ref={config}, selected_target={target}, "
            f"next_phase={self.next_phase!r})"
        )
