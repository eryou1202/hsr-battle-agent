# Battle Semantic Modifier Application Bridge 07

> Final status: **`BATTLE_SEMANTIC = MODIFIER_APPLICATION_BRIDGE_07_PROOF`**
> Sandbox status: **`BATTLE_SANDBOX = MODIFIER_APPLICATION_RUNTIME_07_PROOF`**
> Game version: `4.4.54` (20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb)
> Evidence level: `E4_STATIC_MACHINE_CODE` (accepted primitives / chain boundaries)
> Artifact schema: `battle_semantics_batch/1`

## 1. Scope and real runtime layer (name accuracy)

The client does **not** implement modifier application as one named
`ModifierManager` / `ApplyModifier` method.  The real recovered layer is:

```text
serialized TaskConfig DSL
  RPG.GameCore.AddModifier (type 22786, runtime type_reference 283020)
    -> generated task executor JAJPDPAHFOA (type 54975)
    -> OnTaskBegin (0x161801C0)
    -> TaskContext.EvaluateTarget (Batch 05 target layer)
    -> per target:
         TurnBasedAbilityComponent.TryAddModifierInstance (0xE729500)
           signature: (string modifier-name, ModifierConfig, ability, param, bool)
         -> TurnBasedModifierInstance allocation (.ctor 0xE77EB00)
         -> AbilityComponent.AddModifierInstance (0xE431890)
         -> _ModifierList ordered append at component [+0x38]
```

The batch label keeps the requested `MODIFIER_APPLICATION_BRIDGE_07` name, but
the artifact records
`runtime_layer_name = TURNBASED_MODIFIER_APPLICATION_RUNTIME`.

## 2. First-round report (before PHASE A acceptance)

1. **Commits / tracked state**: `b62910f`, `1ec6983`, `74c5a59`, `7ae767f`
   confirmed at session start; pre-existing untracked files
   (`hsr_design_data_hashes.csv`, `hsr_design_data_inventory.csv`,
   `tools/reference/`, `tools/reverse/vendor/`) left untouched.
2. **AddModifier TaskConfig/runtime identity**:
   `RPG.GameCore.AddModifier` type 22786, serializer `MGMEGEDLMAK` M126119
   (`0x1CD26280`), runtime type_reference 283020; generated executor
   `JAJPDPAHFOA` type 54975 (Batch 06 bridge row, exact type-reference match).
3. **AddModifier executor method/index/RVA**: ctor M506046 `0x1617FE60`;
   OnTaskBegin M506048 `0x161801C0` (gap 6592 B); Dispose M506047
   `0x1617FFC0`.
4. **Application helper chain**:
   `OnTaskBegin (0x161801C0)` →
   `TaskContext.get_SourceEntity (0xE6EEFE0)` →
   `TaskContext.EvaluateTarget (0xE6F1530, call site 0x16180353)` →
   ordered target loop →
   `TryAddModifierInstance (0xE729500, call site 0x16181043)` →
   `TurnBasedModifierInstance..ctor (0xE77EB00, call site 0xE7298AE)` →
   `AbilityComponent.AddModifierInstance (0xE431890, call site 0xE729C2E)` →
   list append at component `[+0x38]`.
5. **Modifier runtime/config family scale**:
   - config factory: 4 variants (`ModifierConfig`,
     `AdventureModifierConfig`, `RtModifierConfig`,
     `TurnBasedModifierConfig`) from `design_runtime_registry.json`;
   - instance family: `BaseModifierInstance` (51 methods/24 fields),
     `AdventureModifierInstance` (45/24), `TurnBasedModifierInstance`
     (243/109), `ModifierSequenceComposite` (17/14);
   - container: `AbilityComponent` (50/15) and `TurnBasedAbilityComponent`
     (380/123).
6. **Persistent modifier owner/container candidates**: all three were proven:
   `TurnBasedAbilityComponent [+0x10]` owner entity (`_OnInitOwnerRef`
   0xE723BB0), `AbilityComponent [+0x38]` `_ModifierList`, and
   `TurnBasedModifierInstance [+0x198]` owner component
   (`GetOwnerAbilityComponent` 0xE740660).
7. **Plausible methods**: 28 `AddModifier` + 1 `ApplyModifier` + 1
   `CreateModifier` + 6 `RemoveModifier` + 22 `GetModifier` + 10
   `FindModifier` + 5 `HasModifier` keyword hits (names used only for
   discovery); 400 `modifier` type hits and 300 method hits capped in
   `data/raw/4.4.54/modifier_application_discovery_07.json`.
8. **Shortlist**: 16 accepted primitives (table in §4) plus boundary/query
   rows; heavy rows classified `SKIP_LIFECYCLE_HEAVY`,
   `SKIP_SERIALIZATION`, `SKIP_DUPLICATE`.
9. **Shortlist details**: type/method/index/RVA/body/branch/callees/read
   set/write category are machine-recorded in the artifact
   `primitives[]` / `candidate_table[]`.
10. **PRIMARY chain**: `add_modifier_action_application_chain`
    (`E4_CHAIN_CLOSED_BOUNDARY_PROJECTION`), §5.
11. **Event/Damage/Lifecycle heavy dependencies**: post-append virtual
    dispatches in `AddModifierInstance`, `TryAddModifierInstance` stack /
    lifetime internals, `_PostProcessAfterModifierAdd`,
    `_ProcessModifierRedd`, dynamic-value/string evaluators in OnTaskBegin,
    `GlobalFindModifierInstance` global search.  None were entered.
12. **Real runtime layer name**: `TURNBASED_MODIFIER_APPLICATION_RUNTIME`
    (see §1).

## 3. Config / runtime bridge (E3 + E4)

- Batch 06 bridge row: generated executor ctor second parameter
  type_reference == `AddModifier.MGMEGEDLMAK` second parameter type_reference
  (283020).  Native ctor stores config at `[+0x20]`, TaskContext at
  `[+0x18]`, TaskState Ready at `[+0x10]`.
- `TryAddModifierInstance` parameter relations prove the runtime rule:
  `string name (typeref 37) + ModifierConfig (typeref 104288) + ability
  (typeref 286703) + param (typeref 608873 UNKNOWN_NAME) + bool (typeref
  433618)`.
- There is **no** generated modifier class per config type_reference
  (unlike Target/Action).  See
  `data/raw/4.4.54/modifier_runtime_bridge_07.json`
  (`bridge_status = NO_GENERATED_CONFIG_TO_INSTANCE_BRIDGE`).

## 4. Accepted primitives (16, all E4)

| primitive_id | runtime type.method | M | RVA | result |
|---|---|---|---|---|
| `battle.ir.action.add_modifier_executor_init` | `JAJPDPAHFOA..ctor` | 506046 | `0x1617FE60` | `task_execution` |
| `battle.ir.modifier.add_modifier_task_begin_apply` | `JAJPDPAHFOA.OnTaskBegin` | 506048 | `0x161801C0` | `modifier_task_application` |
| `battle.ir.modifier.apply_modifier_instance` | `RPG.GameCore.AbilityComponent.AddModifierInstance` | 520236 | `0xE431890` | `modifier_container` |
| `battle.ir.modifier.container_get_by_index` | `RPG.GameCore.AbilityComponent.GetModifierByIndex` | 520239 | `0xE4321E0` | `modifier_state_or_null` |
| `battle.ir.modifier.container_index_of` | `RPG.GameCore.AbilityComponent.GetIndexByModifier` | 520240 | `0xE432270` | `int32` |
| `battle.ir.modifier.container_has_modifier_by_name` | `RPG.GameCore.AbilityComponent.HasModifier` | 520246 | `0xE4331F0` | `boolean` |
| `battle.ir.modifier.container_count` | `RPG.GameCore.AbilityComponent.get_ModifierCount` | 520257 | `0xE433DD0` | `int32` |
| `battle.ir.modifier.state_name` | `RPG.GameCore.BaseModifierInstance.get_Name` | 504746 | `0xE4EEF10` | `string_or_null` |
| `battle.ir.modifier.state_count` | `RPG.GameCore.BaseModifierInstance.get_Count` | 504765 | `0xE4EF0E0` | `int32` |
| `battle.ir.modifier.state_state_raw` | `RPG.GameCore.BaseModifierInstance.get_State` | 504749 | `0xE4EEF40` | `int32` |
| `battle.ir.modifier.state_stacking_flag_raw` | `RPG.GameCore.BaseModifierInstance.get_StackingFlag` | 504751 | `0xE4EEF60` | `int32` |
| `battle.ir.modifier.state_caster_entity` | `RPG.GameCore.BaseModifierInstance.get_CasterEntity` | 504757 | `0xE4EEFC0` | `EntityRef` |
| `battle.ir.modifier.state_layer` | `RPG.GameCore.TurnBasedModifierInstance.get_Layer` | 506325 | `0xE78E480` | `int32` |
| `battle.ir.modifier.state_max_layer` | `RPG.GameCore.TurnBasedModifierInstance.get_MaxLayer` | 506327 | `0xE78E500` | `int32` |
| `battle.ir.modifier.state_current_life` | `RPG.GameCore.TurnBasedModifierInstance.get_CurrentLife` | 506329 | `0xE78E5C0` | `int32` |
| `battle.ir.modifier.state_source_entity` | `RPG.GameCore.TurnBasedModifierInstance.get_SourceEntity` | 506280 | `0xE78A810` | `EntityRef` |

Body windows are exact (`EXACT` small leaves,
`NORMAL_PATH_FIRST_RET_PROJECTION`, or the explicit
`FULL_GAP_CHAIN_BOUNDARY` for the 6592-byte OnTaskBegin); full-gap
disassembly is retained in every `native_evidence` block.

### 4.1 Application leaf `apply_modifier_instance`

```text
list  = this[+0x38]                       # _ModifierList
list[+0x1c]++                             # version
if count < capacity:
    items[count*8 + 0x20] = modifier      # persistent write
    count++
else:
    List<T>.AddWithResize
# then two virtual dispatches on modifier -> POST_APPLY_LIFECYCLE_DEPENDENCY_REQUIRED
```

### 4.2 Container query leaves

- `get_by_index`: positional `[array + index*8 + 0x20]`; index >= count
  returns null.
- `index_of`: forward linear scan comparing instance identity; -1 if absent.
- `has_modifier_by_name`: only instances with raw state `[+0x80] == 1`;
  string length precheck then ordinal equality.
- `count`: list `[+0x18]`.

### 4.3 State leaves

Native slot map (all E4 getter bodies):

| canonical field | native slot | width |
|---|---|---|
| `name` | `+0x60` | string pointer |
| `count` | `+0x7c` | int32 |
| `state_raw` | `+0x80` | int32 (enum members UNKNOWN) |
| `stacking_flag_raw` | `+0x88` | int32 (enum members UNKNOWN) |
| `caster_entity` | `+0x58` cache / `+0x48` lazy resolver | entity pointer |
| `source_entity` | `+0x100` cache / `+0x48` lazy resolver | entity pointer |
| `layer` | `+0x288` | int32 |
| `max_layer` | `max(1, [+0x2e0] + [+0x270])` | int32 |
| `current_life` | `+0x2c4` | int32 |

## 5. Application chains (machine-readable in the artifact)

### `add_modifier_action_application_chain` (PRIMARY)

```text
RPG.GameCore.AddModifier (type 22786, type_reference 283020)
  -> JAJPDPAHFOA .ctor (0x1617FE60)         [+0x20]=config, [+0x18]=ctx, Ready
  -> OnTaskBegin (0x161801C0)
       TaskContext.get_SourceEntity (0xE6EEFE0)
       TaskContext.EvaluateTarget (0xE6F1530, call site 0x16180353)
       ordered target list iteration (0x16180517..0x1618059A)
       per target TryAddModifierInstance (0xE729500, call site 0x16181043)
  -> TurnBasedModifierInstance .ctor (0xE77EB00)
  -> AbilityComponent.AddModifierInstance (0xE431890)
       _ModifierList append at component [+0x38]
  -> TaskState [+0x10] = Success (0x9999) on the observed normal path
status: E4_CHAIN_CLOSED_BOUNDARY_PROJECTION
```

### `modifier_owner_container_chain` (E4_CHAIN_CLOSED)

```text
TurnBasedAbilityComponent [+0x10] = owner entity
    (_OnInitOwnerRef 0xE723BB0)
  -> AbilityComponent [+0x38] = _ModifierList
    (get_ModifierList 0xE433E20 / AddModifierInstance 0xE431890)
  -> TurnBasedModifierInstance [+0x198] = owner component
    (GetOwnerAbilityComponent 0xE740660)
```

## 6. Modifier identity (current coverage, no invented id)

`ModifierRef(name, owner_entity, instance_ordinal)`.

- `name`: proven `BaseModifierInstance.Name [+0x60]` and E3
  `AddModifier.ModifierName`.
- `owner_entity`: proven component `[+0x10]` owner entity; canonical
  `EntityRef(runtime_id)` reused from Batch 05.
- `instance_ordinal`: proven ordered-list append + `GetIndexByModifier`.
- Native object handle / runtime instance id: **UNKNOWN** this round.
- `ModifierConfig` numeric/config id: **UNKNOWN**; runtime config identity is
  the name + config object, not a stable numeric id.
- Canonical code never uses Python `id()`.

## 7. Owner / target / source relationship

- **Owner/target**: AddModifier evaluates `TargetType` config; every target in
  the ordered result list becomes the owner component entity used by
  `TryAddModifierInstance`.
- **Source/caster**: OnTaskBegin reads `TaskContext.get_SourceEntity`
  (`0xE6EEFE0`); `TryAddModifierInstance` receives a source/ability parameter
  chain; instances store `_CasterEntity` / `_SourceEntity` slots.
- **Container**: `AbilityComponent._ModifierList` is an entity component
  list, not an ExecutionContext transient.  The owner chain of §5 is E4.

## 8. Persistent container semantics

- `ORDERED_APPEND` (native tail write + count increment).
- `PRESERVED_NO_DEDUPLICATION` at the accepted append leaf.
- `ModifierContainer` is tuple-backed; never a Python `set`.
- Canonical BattleState representation is
  `modifier_state_by_entity: {"<runtime_id>": [ModifierState...]}` (schema v2).
- No listener-order / expiration-order behavior is claimed beyond append
  order.

## 9. Stack / layer status

- Accepted leaf: duplicate append is preserved.
- `TryAddModifierInstance` contains `GlobalFindModifierInstance`,
  `FindModifierInstance`, `Destroy` and a fresh-allocation path, i.e. a
  destroy/re-add path exists.  The exact duplicate condition is **not**
  recovered.
- `STACK_POLICY = UNKNOWN`; `SEMANTIC_DEPENDENCY_REQUIRED`.  The sandbox does
  not guess "same name buff stacks".

## 10. Duration / lifetime status

- Proven state slots: `current_life [+0x2c4]`, `layer [+0x288]`,
  `max_layer` arithmetic, config fields `LifeTime` / `Count` /
  `LifeStepImmediately` exist in E3.
- Expiration trigger, turn/round duration, refresh semantics: **UNKNOWN**.
- No duration test is written.

## 11. Modifier effect boundary

- Successful mount (persistent append) **does not imply** effect execution.
- Deferred: property stacks, behavior flags, DOT, shield/HP changes, event
  processors, damage hooks.
- The accepted `AddModifierInstance` body performs two post-append virtual
  dispatches; those are recorded
  `POST_APPLY_LIFECYCLE_DEPENDENCY_REQUIRED` and not simulated.

## 12. Event dependency

- Event rows `AbilityAddModifier` / `AbilityPreAddModifier` /
  `LevelAfterAddModifier` exist (E3 names), but event/listener execution is
  deferred.
- Application mutation is separated from notification side effects in both
  artifact and sandbox.

## 13. READ / WRITE set

Artifact top-level fields:

- `persistent_reads`: component owner `[+0x10]`, `_ModifierList [+0x38]`,
  list `[+0x10]/[+0x18]/[+0x1c]`, instance `+0x60/+0x7c/+0x80/+0x88/+0x58/
  +0x48/+0x100/+0x288/+0x2c4/+0x2e0/+0x270/+0xa0/+0x198`.
- `persistent_writes`: list version, items slot, count, and canonical
  `BattleState.modifier_state_by_entity`.
- Transient executor slots are recorded per primitive as
  `action_reads`/`action_writes`; they never enter BattleState.

## 14. Canonical BattleState growth (schema v2)

Only one field was added:

```text
modifier_state_by_entity: dict[str, list[ModifierState dict]]
```

No HP/ATK/DEF/SPD/Energy/Toughness, no full EntityState, no buff/debuff list.
Schema v1 snapshots migrate by defaulting to an empty modifier index.

## 15. Known unknowns

See `unknowns[]` in the artifact.  Highlights:

- full 6592-byte OnTaskBegin control flow beyond the accepted boundary;
- exact duplicate stack/refresh/replace policy;
- duration expiration triggers;
- `State` / `StackingFlag` enum member ordinals;
- typerefs 231567 / 232380 / 608873 canonical names;
- unregistered local resolver helper `0xB429790`;
- no E5 client-side runtime observation.

## 16. Explicitly not this round

Modifier effects, DOT, damage formula, event/listener runtime, turn
expiration, buff UI, Black Swan, legal_actions / step / is_terminal /
Planner, and any stat system.

Machine-readable companions:

- `data/semantics/4.4.54/modifier_application_bridge_07.json`
- `data/raw/4.4.54/modifier_application_discovery_07.json`
- `data/raw/4.4.54/modifier_runtime_bridge_07.json`
- Sandbox report: `data/sandbox/modifier_application_runtime_07_report.json`
