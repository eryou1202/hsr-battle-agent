# -*- coding: utf-8 -*-
"""Action Execution Bridge 06 runtime implementations.

Every function mirrors one bounded native body from
``data/semantics/4.4.54/action_execution_bridge_06.json`` (E4).  The sandbox
executes immutable ``TaskExecutionState`` transitions; it does not simulate the
generated executor object memory, TaskContext pointer slots, or the deferred
Tick gameplay leaves.

Client-faithful details preserved:

* ``task_executor_init``: both native pointer slots are stored without
  validation; canonically only the config reference is materialized (the live
  ExecutionContext is never captured).
* ``task_begin_immediate_success`` / ``task_reset_ready``: the exact native
  leaves write **only** task_state (other slots are preserved).
* ``task_begin_select_single_target``: Batch 05 collapse is reused, then the
  selected target is stored and the next phase is marked ``"Tick"`` (native
  tailcall with dt=0).
* ``task_reset_ready_clear_selected_target``: state -> Ready and selected
  target slot -> null (the exact two native writes).
"""
from __future__ import annotations

import dataclasses

from hsr_battle_agent.battle_ir.actions import TaskExecutionState, TaskState
from hsr_battle_agent.battle_ir.targets import TargetSet
from hsr_battle_agent.battle_runtime.targets import collapse_required_single_or_null


def task_executor_init(config: str | None) -> TaskExecutionState:
    """Generated executor .ctor: store config slot and initialize Ready."""
    if config is not None and not isinstance(config, str):
        raise TypeError(f"config must be str or None, got {type(config).__name__}")
    return TaskExecutionState(task_state=TaskState.READY, config_ref=config)


def task_begin_immediate_success(execution: TaskExecutionState) -> TaskExecutionState:
    """Generated Obsolete executor OnTaskBegin: only task_state := Success."""
    _require_execution(execution)
    return dataclasses.replace(execution, task_state=TaskState.SUCCESS)


def task_reset_ready(execution: TaskExecutionState) -> TaskExecutionState:
    """Generated Obsolete executor OnTaskReset: only task_state := Ready."""
    _require_execution(execution)
    return dataclasses.replace(execution, task_state=TaskState.READY)


def task_state_read(execution: TaskExecutionState) -> TaskState:
    """Generated task base accessor: read the raw TaskState slot."""
    _require_execution(execution)
    return execution.task_state


def task_executor_base_ready_init() -> TaskExecutionState:
    """Generated task base ctor: TaskState := Ready."""
    return TaskExecutionState(task_state=TaskState.READY)


def task_begin_select_single_target(
    execution: TaskExecutionState,
    targets: TargetSet,
) -> TaskExecutionState:
    """Generated target-selecting OnTaskBegin leaf (Batch 05 collapse reuse)."""
    _require_execution(execution)
    if not isinstance(targets, TargetSet):
        raise TypeError(f"targets must be TargetSet, got {type(targets).__name__}")
    selected_target = collapse_required_single_or_null(targets)
    return dataclasses.replace(
        execution,
        task_state=TaskState.EXECUTING,
        selected_target=selected_target,
        next_phase="Tick",
    )


def task_reset_ready_clear_selected_target(
    execution: TaskExecutionState,
) -> TaskExecutionState:
    """Generated target-aware OnTaskReset: Ready + selected target slot null."""
    _require_execution(execution)
    return dataclasses.replace(
        execution,
        task_state=TaskState.READY,
        selected_target=None,
        next_phase=None,
    )


def _require_execution(execution: TaskExecutionState) -> None:
    if not isinstance(execution, TaskExecutionState):
        raise TypeError(
            f"execution must be TaskExecutionState, got {type(execution).__name__}"
        )
