# Battle Semantic Target Selector Batch 05

> Final status: **`BATTLE_SEMANTIC = TARGET_SELECTOR_BATCH_05_PROOF`**
> Sandbox status: **`BATTLE_SANDBOX = TARGET_SELECTOR_RUNTIME_05_PROOF`**
> Game version: `4.4.54` (20260731-0529-BetaLive-15953205-OSBETAWin4.4.54-OSCb)
> Evidence level: `E4_STATIC_MACHINE_CODE` (accepted primitives)
> Artifact schema: `battle_semantics_batch/1`

## 1. Scope and real runtime shape (name accuracy)

The client does **not** implement target selection as one named
"TargetSelector" method.  The real recovered shape is a generated evaluator
pipeline:

```text
serialized target config
  TargetFetch* / TargetMap* / TargetFilter* / TargetSort* / TargetSelector /
  TargetCompute / TargetSequence / TargetTake / TargetIndex / TargetShuffle ...
      (all are ctor + 4 serializer methods; no execution methods)
  -> generated concrete TargetEvaluatorImpl`1 class
      (obfuscated 11-letter names; .ctor stores the config at [this+0x10])
  -> Evaluate (fetch/set producers) or Transform (map/filter/sort nodes)
      signature: (TaskContext ctx, target-list list)
  -> TaskContext / AbilityStatic helper
  -> ordered target list
```

The machine-readable bridge
`data/raw/4.4.54/target_config_runtime_bridge_05.json` maps **880 config
families to 197 generated evaluator classes** by exact type-reference match:
the generated `.ctor` parameter type_reference equals the config
`MGMEGEDLMAK` second parameter type_reference.  This is E3 metadata identity
combined with E4 native bodies; it is recorded in the artifact
`selector_chains[]` and is not claimed from names alone.

This batch is therefore correctly named a **Target Selector batch** (the
recovered scope is the target-selection DSL), but the artifact documents the
real implementation layer instead of presenting a fake single selector class.

## 2. Accepted primitives (8, all E4)

| primitive_id | runtime type.method | M | RVA | result |
|---|---|---|---|---|
| `battle.ir.target.context_task_action_target` | `RPG.GameCore.TaskContext.get_TaskActionTarget` | 505847 | `0xE6EEFC0` | `EntityRef` |
| `battle.ir.target.context_owner_entity` | `RPG.GameCore.TaskContext.get_OwnerEntity` | 505843 | `0xE6EED70` | `EntityRef` |
| `battle.ir.target.select_task_action_target` | `NDIJLODKLJB.Evaluate` (= `TargetFetchTaskActionTarget`) | 538090 | `0xBC3F790` | `TargetSet` |
| `battle.ir.target.select_caster` | `KCFPGFDHIEO.Evaluate` (= `TargetFetchCaster`) | 538052 | `0xB4C9D90` | `TargetSet` |
| `battle.ir.target.select_none` | `NAOFIGCCGPF.Evaluate` (= `TargetFetchNone`) | 538056 | `0xBBAE290` | `TargetSet` |
| `battle.ir.target.collapse_single_or_null` | `RPG.GameCore.AbilityStatic.GetTaskSingleTarget` | 504364 | `0xE43E160` | `EntityRef` |
| `battle.ir.target.collapse_required_single_or_null` | `RPG.GameCore.TaskContext.EvaluateSingleTarget` | 505875 | `0xE6D5830` | `EntityRef` |
| `battle.ir.entity.game_entity_runtime_id` | `RPG.GameCore.GameEntity.get_RuntimeID` | 499138 | `0xE61B860` | `int32` |

## 3. Selector chains (machine-readable in the artifact)

### `task_action_target_selector_chain`

```text
RPG.GameCore.TargetFetchTaskActionTarget (type_index 23619,
    MGMEGEDLMAK runtime type_reference 299365)
  -> NDIJLODKLJB (generated evaluator, .ctor type_ref == 299365)
  -> Evaluate (0xBC3F790)
  -> TaskContext [+0x48] read
  -> if non-null: append entity to ordered target list
  -> if null:     append nothing (empty list)
```

### `caster_selector_chain`

```text
RPG.GameCore.TargetFetchCaster (type_index 23603,
    MGMEGEDLMAK runtime type_reference 299308)
  -> KCFPGFDHIEO (generated evaluator, .ctor type_ref == 299308)
  -> Evaluate (0xB4C9D90)
  -> TaskContext.get_CasterEntity (duplicate entry 0x18B429790)
  -> append entity unconditionally (null result appends a null element)
```

### `none_selector_chain`

```text
RPG.GameCore.TargetFetchNone (type_index 23605, runtime type_reference 299314)
  -> NAOFIGCCGPF.Evaluate (0xBBAE290)
  -> clear target list; no TaskContext field is read
```

## 4. Single-target semantics

- `GetTaskSingleTarget`: allocates a target list, calls
  `TaskContext.EvaluateTarget(ctx, config, list, mask)`, then returns the
  **first** element; empty list returns null.  (`>= 1 -> first`.)
- `TaskContext.EvaluateSingleTarget`: same construction, but requires
  **exactly one** element.  0 or >= 2 results call an error logger, release
  the list and return null.
- `TargetFetchTaskActionTarget`: direct field leaf.
- `TargetFetchCaster`: computed caster entity leaf (native helper is a
  duplicate of `TaskContext.get_CasterEntity`; canonical sandbox materializes
  the result in `ExecutionContext.caster_entity`).

## 5. Entity identity level

- Selector outputs are **entity object pointers** (runtime
  `type_reference 202024`), not ids and not wrappers.
- The stable logical id is `GameEntity.RuntimeID`, signed int32 at native
  offset `+0xD0` (`get_RuntimeID`, M499138, `0xE61B860`, E4).
- Canonical mapping: `EntityRef(runtime_id=int)` with equality/hash by
  `runtime_id` only.  No `id(obj)`, no full entity state model.

## 6. Target list / TargetSet model (proven, not assumed)

Native list layout observed in every accepted evaluator body:

```text
list +0x10 = items array pointer
list +0x18 = count (int32)
list +0x1c = version (int32)
items      = [array + index*8 + 0x20]   (entity pointer or null)
```

Proven properties:

| property | status | native evidence |
|---|---|---|
| order | `ORDERED_APPEND` | append writes `[array + count*8 + 0x20]` then `count++` |
| duplicates | `PRESERVED_NO_DEDUPLICATION` | no contains/check before append in accepted leaves |
| null elements | `ALLOWED_PER_SELECTOR` | caster appends null; task-action-target skips null; none is empty |
| empty | `ALLOWED` | none selector and null-field path return empty lists |
| canonical type | `TargetSet(tuple[EntityRef \| None, ...])` | tuple-backed ordered list; **never** Python `set()` |

`TargetSet` is frozen, clone-friendly, serializable, and supports `None`
elements because the native list can contain null.

## 7. Null / default behavior

| leaf | behavior |
|---|---|
| `TaskContext.get_TaskActionTarget` | null field -> null result |
| `TaskContext.get_OwnerEntity` | null field -> null result |
| `TargetFetchTaskActionTarget` | null field -> **empty list** |
| `TargetFetchCaster` | null caster -> **one null list element** |
| `TargetFetchNone` | always empty |
| `GetTaskSingleTarget` | empty list -> null |
| `EvaluateSingleTarget` | 0 or >=2 -> null (with error log) |
| null TaskContext / list instances | native throws; sandbox keeps explicit input validation |

## 8. Context / state read sets

ExecutionContext additions (all E4-backed, transient single-frame inputs;
**not** BattleState and **not** in logical state hash / snapshot):

- `task_action_target`: TaskContext `+0x48`
- `owner_entity`: TaskContext `+0x70`
- `caster_entity`: canonical materialization of
  `TaskContext.get_CasterEntity`

BattleState additions: **none** (no roster / team / alive state was required
by the accepted single-entity primitives).

## 9. Dependencies / unknowns

- `TaskContext.EvaluateTarget` (0xE6F1530): `SEMANTIC_DEPENDENCY_REQUIRED`.
  Registry dispatcher shape proven; registry construction and per-config
  entries not recovered in this batch.
- `AbilityStatic.RemoveUnselectableEntities` /
  `RemoveForceUnselectableEntities`: ordered filter shape proven, predicate
  internals deferred.
- `TaskContext.get_CasterEntity` duplicate entry provenance:
  byte-pattern-identical duplicate observed; canonicalized in the sandbox.
- type_reference 202024 (entity pointer) has no normalized name resolver yet;
  identity anchored by consumers.
- No E5 client-side runtime observation.
- Multi-target `TargetFetch*/TargetMap*/TargetSort*`, `TargetQuery`,
  `FillTargetEntitiesWithFilter` deferred (see artifact `deferred_candidates`).

## 10. Candidate discovery summary

- `EvaluateTarget`: 544 direct rel32 call sites; `EvaluateSingleTarget`: 424.
- 197 generated evaluator `Evaluate`/`Transform` leaves.
- 10–30 candidates classified in the artifact `candidate_table`; 8 accepted,
  heavy/serialization rows carry explicit skip reasons.

Machine-readable companion:
`data/semantics/4.4.54/target_selector_batch_05.json`.
Runtime report: `data/sandbox/target_selector_runtime_05_report.json`.
