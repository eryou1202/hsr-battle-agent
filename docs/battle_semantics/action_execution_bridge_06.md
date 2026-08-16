# Battle Semantic Action Execution Bridge Batch 06

> Final status: **`BATTLE_SEMANTIC = ACTION_EXECUTION_BRIDGE_06_PROOF`**
> Sandbox status: **`BATTLE_SANDBOX = ACTION_EXECUTION_RUNTIME_06_PROOF`**
> Game version: `4.4.54` (20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb)
> Evidence level: `E4_STATIC_MACHINE_CODE` (all accepted primitives)
> Artifact schema: `battle_semantics_batch/1`

## 1. Scope and real runtime layer (name accuracy)

The client does **not** implement action execution as one named
`ActionExecutor` method. The real recovered shape is a **generated task
executor runtime** over the `TaskConfig` DSL:

```text
serialized action/task config
  (TaskConfig DSL family; serializer identity OJNNBEJLDIJ/MGMEGEDLMAK/
   LJACLBNEEEB/EOJLPDGNHEK, SKIP_SERIALIZATION as in earlier batches)
  -> generated task executor class
      (.ctor(TaskContext, config); OnTaskBegin / OnTaskReset / Tick / Dispose)
  -> TaskState transition at executor [+0x10]
      Ready=0x7777, Executing=0x8888, Success=0x9999, Fail=0xAAAA
  -> context/target/value inputs (Batch 02-05 reuse)
  -> observable deterministic result
      (this batch: TaskState transition and selected-target slot;
       persistent BattleState / component writes are explicitly deferred)
```

The batch label keeps the requested `ACTION_EXECUTION_BRIDGE_06` name, but the
artifact records `runtime_layer_name = GENERATED_TASK_EXECUTOR_RUNTIME`, and
this document presents that real layer. There is no fake single
`ActionExecutor` class.

## 2. First-round report (before PHASE A acceptance)

1. **Commits / tracked state**: `74c5a59`, `7ae767f`, `dc668d7`, `8d4319e`
   confirmed at session start; pre-existing untracked files
   (`hsr_design_data_hashes.csv`, `hsr_design_data_inventory.csv`,
   `tools/reference/`, `tools/reverse/vendor/`) left untouched.
2. **Action/task config family count**: 6578 config families carry the
   `MGMEGEDLMAK` 2-parameter serializer identity.
3. **Generated/runtime implementation count**: 3070 generated task executor
   classes (`OnTaskBegin` declared, `.ctor` 2 parameters); 3060 distinct
   second-ctor-parameter type references.
4. **Config → executor bridge**: **YES**. 3024 rows match
   `generated executor .ctor parameter 2 type_reference == config
   MGMEGEDLMAK parameter 2 type_reference`. This is E3 metadata identity
   combined with E4 native ctor stores
   (`data/raw/4.4.54/action_config_runtime_bridge_06.json`). 41 executor
   type refs are unmatched and preserved as unknowns.
5. **TaskContext main action-side callers**:
   - `EvaluateTarget` (`0xE6F1530`): 544 rel32 call sites;
     **427 are generated `OnTaskBegin` leaves**.
   - `EvaluateSingleTarget` (`0xE6D5830`): 424 rel32 call sites;
     **320 are generated `OnTaskBegin` leaves**.
   - `set_TaskActionTarget`: 0 direct rel32 callers — generated executors
     write TaskContext slots inline; the setter itself is not an execution
     entrypoint.
   - `get_SourceEntity`: 13 rel32 callers, including two heavy OnTaskBegin
     leaves (`AddModifier` 6592-byte body; `AGPMEJILJBO` 4000-byte body).
6. **EvaluateTarget / EvaluateSingleTarget gameplay-side caller situation**:
   generated task executors are the gameplay-side consumers. The two most
   important chains are:
   - `SetCurrentTurnActionEntity` OnTaskBegin → `GetTaskSingleTarget`
     (Batch 05) → `TurnBasedGameMode.SetCurrentTurnActionEntity`
     (persistent write, deferred);
   - `SwitchHandItemSetBreathingLight` OnTaskBegin →
     `EvaluateSingleTarget` (Batch 05) → executor selected-target slot →
     `Tick` leaf (component write, deferred).
7. **Plausible candidates**: 3024 ranked OnTaskBegin rows in
   `data/raw/4.4.54/action_execution_shortlist_06.json` (10-30 used as the
   candidate table; the shortest 30 are machine-recorded in the artifact
   `first_round_report`).
8. **Shortlist (7 accepted)**: `HDDPKFNLMEG..ctor`, `.OnTaskBegin`,
   `.OnTaskReset` (`RPG.GameCore.Obsolete`); `GELIALJDFBL..ctor`,
   `.MDFBKGOJOJI` (generated task base); `CPHGMLEAPJL.OnTaskBegin`,
   `.OnTaskReset` (`RPG.GameCore.SwitchHandItemSetBreathingLight`).
9. **Shortlist details**: see §4 accepted primitive table and
   `candidate_table` in the JSON artifact; every row has config/runtime type,
   method, method_index, RVA, size, branch, callees, reads, writes/effect
   category.
10. **PRIMARY chain**: `RPG.GameCore.Obsolete` → generated executor
    `HDDPKFNLMEG` `.ctor` → `OnTaskBegin` → `TaskState.Success`
    (the real empty/no-op action DSL leaf, E4 closed).
11. **Heavy dependency skip list**:
    - `SequenceConfig` step helper (`0xB526340`, 2080 B): ordered child-task
      dispatcher; structure SUPPORTED, internals deferred.
    - `TriggerHitTarget` leaf (`0x15547AB0`, 656 B): hit/damage processing.
    - `AddModifier` / `AGPMEJILJBO` OnTaskBegin: modifier subsystem.
    - `NotifyManager.Notify` leaves (`0xD994450`): event system.
    - `SetDynamicValueByBattleTargetParam` helpers: TaskContext string-hash
      dictionary dispatcher.
    - `TurnBasedGameMode.SetCurrentTurnActionEntity`: persistent field
      identities unresolved.
    - `CPHGMLEAPJL.Tick` component write: component class/field unresolved.
12. **Real runtime layer name**: `GENERATED_TASK_EXECUTOR_RUNTIME`
    (see §1).

## 3. Config/runtime bridge (E3 metadata + E4 ctor stores)

`tools/reverse/scripts/build_action_config_runtime_bridge.py` produced:

```text
6578 config families (MGMEGEDLMAK 2-parameter)
3070 generated executor classes (OnTaskBegin + .ctor 2-parameter)
3024 matched rows (exact second-parameter type_reference match)
```

Native ctor evidence used by the accepted primitives:

```text
generated .ctor(rcx=this, rdx=arg0 TaskContext, r8=arg1 config):
    this[+0x18] = arg1  (config slot)
    this[+0x20] = arg0  (TaskContext slot)
    this[+0x10] = 0x7777 (TaskState.Ready)
```

Slot order differs across generated base families (e.g. `KLJNMOLABGO`
stores ctx at `+0x18` / config at `+0x20`); this is recorded as an unknown,
not silently normalized.

## 4. Accepted primitives (7, all E4)

| primitive_id | runtime type.method | M | RVA | body(B) | branch | calls | result |
|---|---|---|---|---|---:|---|---|---|
| `battle.ir.action.task_executor_init` | `HDDPKFNLMEG..ctor` (Obsolete) | 517404 | `0x15886B40` | 16 | 0 | 0 | `task_execution` |
| `battle.ir.action.task_begin_immediate_success` | `HDDPKFNLMEG.OnTaskBegin` | 517406 | `0x15886B90` | 30 | 1 | 0 | `task_execution` |
| `battle.ir.action.task_reset_ready` | `HDDPKFNLMEG.OnTaskReset` | 517407 | `0x15886BE0` | 30 | 1 | 0 | `task_execution` |
| `battle.ir.action.task_state_read` | `GELIALJDFBL.MDFBKGOJOJI` | 505903 | `0x156A31A0` | 26 | 1 | 0 | `task_state` |
| `battle.ir.action.task_executor_base_ready_init` | `GELIALJDFBL..ctor` | 505902 | `0x156600E0` | 8 | 0 | 0 | `task_execution` |
| `battle.ir.action.task_begin_select_single_target` | `CPHGMLEAPJL.OnTaskBegin` | 498176 | `0xDD77480` | 76 | 3 | 1 | `task_execution` |
| `battle.ir.action.task_reset_ready_clear_selected_target` | `CPHGMLEAPJL.OnTaskReset` | 498177 | `0xDD77500` | 38 | 1 | 0 | `task_execution` |

Bodies are exact bounded windows (`NORMAL_PATH_FIRST_RET_PROJECTION`, and
`NORMAL_PATH_FIRST_TAILCALL_PROJECTION` for `498176`); IL2CPP class-init /
instrumentation tails after the semantic window are retained in
`full_gap_disassembly` only.

### 4.1 `task_executor_init` (method_index 517404)

- Native: `HDDPKFNLMEG..ctor` body 16 B / 4 instructions / 0 branches / 0 calls
- ABI: `rcx=this, rdx=arg0 TaskContext, r8=arg1 config`
- Writes (task executor slots): `[+0x20] = ctx`, `[+0x18] = config`,
  `[+0x10] = Ready(0x7777)`
- Reads: none
- Canonical sandbox stores only `config_ref` + `TaskState.Ready`; the live
  `ExecutionContext` is never captured.
- Null/default: native stores pointers without validation; null ctx/config
  are stored as-is.

### 4.2 `task_begin_immediate_success` (method_index 517406)

- Native: `HDDPKFNLMEG.OnTaskBegin` body 30 B / 9 instructions / 1 branch /
  0 calls
- Effect: `[+0x10] = Success(0x9999)`; returns. No config/context read, no
  BattleState write.
- This is the real empty/no-op action DSL primitive: `RPG.GameCore.Obsolete`
  (fields: `Message`, never read) compiles to an executor whose only
  observable effect is the deterministic Success transition.
- Branch: one-time IL2CPP class-init gate (instrumentation; excluded from
  semantics).

### 4.3 `task_reset_ready` (method_index 517407)

- Native: `HDDPKFNLMEG.OnTaskReset` body 30 B / 9 instructions / 1 branch /
  0 calls
- Effect: `[+0x10] = Ready(0x7777)`. Only the state field is written; all
  other canonical slots are preserved by the sandbox implementation.

### 4.4 `task_state_read` (method_index 505903)

- Native: `GELIALJDFBL.MDFBKGOJOJI` body 26 B / 9 instructions / 1 branch /
  0 calls
- Effect: read `[+0x10]` raw int32 and return it.
- Identity anchor: the obfuscated method name is anchored by (a) the four
  TaskState constants written by every recovered lifecycle leaf and (b)
  `GELIALJDFBL.GetConfig` returning TaskConfig runtime `type_reference 22744`.

### 4.5 `task_executor_base_ready_init` (method_index 505902)

- Native: `GELIALJDFBL..ctor` body 8 B / 2 instructions / 0 branches / 0 calls
- Effect: `[+0x10] = Ready(0x7777)`.

### 4.6 `task_begin_select_single_target` (method_index 498176)

- Native: `CPHGMLEAPJL.OnTaskBegin` body 76 B / 21 instructions / 3 branches /
  1 call
- Effect:
  ```text
  [+0x10] = Executing(0x8888)
  entity = TaskContext.EvaluateSingleTarget(ctx, config.TargetType, mask=0xffff)
  [+0x28] = entity
  tailcall Tick(this, dt=0)
  ```
- Batch 05 reuse: the single-target collapse is
  `battle.ir.target.collapse_required_single_or_null` (0 or >=2 -> null).
- Canonical sandbox input is the already-evaluated ordered `TargetSet`; the
  deferred `Tick` gameplay leaf is recorded in `deferred_effects`.
- Null/default: null ctx/config slots throw; empty/two-target results store
  null selected target.

### 4.7 `task_reset_ready_clear_selected_target` (method_index 498177)

- Native: `CPHGMLEAPJL.OnTaskReset` body 38 B / 10 instructions / 1 branch /
  0 calls
- Effect: `[+0x10] = Ready(0x7777)`, `[+0x28] = null`.

## 5. Execution chains (machine-readable in the artifact)

### `obsolete_empty_action_chain` (PRIMARY, E4_CHAIN_CLOSED)

```text
RPG.GameCore.Obsolete (type 23463, MGMEGEDLMAK 133237,
    runtime type_reference 22744-consistent bridge)
  -> HDDPKFNLMEG .ctor (0x15886B40)  [slots + Ready]
  -> HDDPKFNLMEG.OnTaskBegin (0x15886B90)
  -> TaskState [+0x10] = Success (0x9999)
  -> observable deterministic result: TaskState.SUCCESS
```

### `obsolete_empty_action_reset_chain` (E4_CHAIN_CLOSED)

```text
HDDPKFNLMEG.OnTaskReset (0x15886BE0)
  -> TaskState [+0x10] = Ready (0x7777)
```

### `target_select_executor_chain` (E4_CHAIN_TARGET_STORE_CLOSED_TICK_LEAF_DEFERRED)

```text
RPG.GameCore.SwitchHandItemSetBreathingLight (type 20711)
  -> CPHGMLEAPJL.OnTaskBegin (0xDD77480)
  -> EvaluateSingleTarget (Batch 05 collapse reuse)
  -> executor [+0x28] = selected target
  -> tailcall Tick(this, dt=0)   [gameplay leaf deferred]
```

### `battle_current_turn_action_chain` (E4_STRUCTURE_SUPPORTED_PERSISTENT_DEPENDENCY)

```text
RPG.GameCore.SetCurrentTurnActionEntity (type 23367, field TargetType)
  -> EBHAGBCPFEN.OnTaskBegin (0x12844660)
       [+0x10] = Success(0x9999)
  -> AbilityStatic.GetTaskSingleTarget (0xE43E160, Batch 05)
  -> TurnBasedGameMode.SetCurrentTurnActionEntity (0xE75F700)
       observed writes when new entity differs:
         [mode+0x2FA]=0, [mode+0x318]=0,
         conditional [mode+0x2C9]/[mode+0x2CA]=0
       PERSISTENT_STATE_DEPENDENCY_REQUIRED
```

## 6. READ / WRITE set discipline

Top-level artifact fields:

| set | value |
|---|---|
| `context_reads` | `["targets"]` (only the target-selecting OnTaskBegin leaf) |
| `context_writes` | `[]` |
| `state_reads` (BattleState) | `[]` |
| `state_writes` (BattleState) | `[]` |

Each primitive additionally records `action_reads` / `action_writes` for the
generated task executor transient slots:

| primitive | action_reads | action_writes |
|---|---|---|
| `task_executor_init` | - | task_context_slot, task_config_slot, task_state |
| `task_begin_immediate_success` | - | task_state |
| `task_reset_ready` | - | task_state |
| `task_state_read` | task_state | - |
| `task_executor_base_ready_init` | - | task_state |
| `task_begin_select_single_target` | task_state | task_state, selected_target, next_phase |
| `task_reset_ready_clear_selected_target` | - | task_state, selected_target, next_phase |

Rules followed:

- Native writes to the **generated executor object** are transient task
  slots, never `BattleState`.
- `ExecutionContext` is not mutated by this batch; the sandbox returns a new
  immutable `TaskExecutionState`. This makes clone isolation structural.
- Persistent writes (`TurnBasedGameMode` fields, component `+0x44`) are only
  recorded as observed E4 write shapes with
  `PERSISTENT_STATE_DEPENDENCY_REQUIRED` / `COMPONENT_STATE_DEPENDENCY_REQUIRED`;
  no BattleState field is added from a guess.

## 7. Ordering / null / determinism

- TaskState transitions are constant stores: no PRNG, clock or context input.
- `task_begin_immediate_success` is terminal; the native `Obsolete.Tick`
  normal path is empty (SKIP_WRAPPER in candidate table).
- `task_begin_select_single_target` preserves Batch 05 target ordering and
  strict-single collapse (0 or >=2 -> null), then marks `next_phase = "Tick"`
  (the proven native tailcall with dt=0).
- Reset leaves restore Ready; the target-aware reset also clears the
  selected-target slot exactly as the native body does.

## 8. Effect boundaries / deferred heavy subsystems

`deferred_effects[]` in the artifact records, without inventing descriptors:

1. `turn_based_game_mode_set_current_turn_action_entity`:
   `PERSISTENT_STATE_DEPENDENCY_REQUIRED` (field identities unresolved).
2. `switch_hand_item_breathing_light_tick_leaf`:
   `COMPONENT_STATE_DEPENDENCY_REQUIRED` (component class global
   `0x983DA48`, field `+0x44` unresolved).
3. `trigger_hit_target_leaf`: hit/damage subsystem dependency.
4. `notify_manager_client_event_effects`: event system excluded.

Explicitly **not** entered this round: Damage, Modifier, DOT, buff/debuff,
event listener, toughness, AV, turn queue, summon lifecycle, full Skill
execution, `legal_actions`, `step`, `is_terminal`.

## 9. Candidate table / skip discipline

See `candidate_table[]` in the JSON artifact. Summary of skips:

| candidate | classification |
|---|---|
| `TaskContext.EvaluateTarget` (0xE6F1530) | SKIP_CONTEXT_HEAVY (Batch 05 leaves reused) |
| `SequenceConfig` step helper (0xB526340) | DISPATCHER_STRUCTURE_SUPPORTED |
| `TriggerHitTarget` leaf (0x15547AB0) | SKIP_CONTEXT_HEAVY (hit/damage) |
| `NotifyManager.Notify` (0xD994450) | SKIP_EVENT_SYSTEM |
| `TurnBasedGameMode.SetCurrentTurnActionEntity` (0xE75F700) | PERSISTENT_STATE_DEPENDENCY_REQUIRED |
| `CPHGMLEAPJL.Tick` (0xDD772E0) | COMPONENT_STATE_DEPENDENCY_REQUIRED |
| `SetDynamicValueByBattleTargetParam` helpers | SKIP_CONTEXT_HEAVY (dictionary dispatcher) |
| `Obsolete` serializer family | SKIP_SERIALIZATION |
| `Obsolete` executor Dispose / Tick | SKIP_WRAPPER (empty normal paths) |

## 10. Known unknowns

- Obfuscated base class true names (`GELIALJDFBL` / `DJPBAKPBELL`); anchored
  by `TaskConfig` type_reference 22744 and TaskState field semantics.
- TaskState fieldDefinition provenance (`type_reference 586147`) has no
  formal type-reference resolver; E4 constants + E3 enum members carry the
  identity.
- Generated executor slot layouts differ across generated base families.
- The three generated `TaskConfig` executors share the same ctor signature;
  the specialization rule was not recovered (all variants recorded).
- `SequenceConfig` exact early-stop internals beyond the proven
  Ready/Executing/Success/Fail transitions.
- No E5 client-side runtime observation.

Machine-readable companions:

- `data/semantics/4.4.54/action_execution_bridge_06.json`
- `data/raw/4.4.54/action_config_runtime_bridge_06.json`
- `data/raw/4.4.54/action_execution_discovery_06.json`
- `data/raw/4.4.54/action_execution_shortlist_06.json`
- `data/raw/4.4.54/task_context_action_xrefs_06.json`
- Sandbox report: `data/sandbox/action_execution_runtime_06_report.json`
