# Full Reconstruction Handoff — 2026-08-25 (v2)

## Current state

- Root: `D:\HSR_Battle_Agent\hsr-battle-agent`.
- Preserve all existing dirty reverse files; this program did not edit them.
- Highest goal: `FULL_4_4_54_SANDBOX_RECONSTRUCTION_FREEZE`.
- DSH production build remains frozen.

## Completed

- `RECON-STATE-REPAIR-001` repaired SSOT status, Effect IR vocabulary,
  detailed free-loadout input, opaque-disabled restrictions and dependency
  order.
- External discovery inspected all four pinned repositories. The
  TurnBasedGameData tree is truncated: positive paths are usable; absences are
  not proof.
- Ten reviewed TurnBasedGameData behavior files are cached and hash-recorded
  in `.external_refs/TurnBasedGameData/manifest.json`.
- `IR-CORE-001-RECURSIVE-LIFT-REPAIR` rebuilt the canonical normalizer (schema
  `external_behavior_corpus/2`). It now lifts: Modifier records' own
  `_CallbackList`, Ability `GlobalModifiers`, singular `Predicate` AST
  mappings, all nested Success/Failed/Fail/TaskList and loop/retarget task
  arrays, TaskListTemplate definitions with resolved invocation links, and
  DynamicValue definitions. No callback/template/DynamicValue definition
  remains raw-only.
- Regenerated corpus: 553 records, 508 entrypoints (404 Modifier
  callbacks), 2 template definitions, 287 DynamicValue definitions, 2295
  recursive semantic nodes (1780 operations, 515 Predicate AST).
- Node statuses: REQUIRES_PACKET 1826, PRESENTATION 430, MODELLED 32,
  OPAQUE 7.
- Current corpus hash:
  `fea0ab0e397012d0418d6f6b709d7ff91b2e51637bf16d3b1ea1c0bcfa7e913a`.
- Current coverage split: 249 behavior-bearing records (92 structural-only
  compiled), 109 `EXECUTABLE_REFERENCE` records / 192 independently closed
  entrypoints, and 304 static-definition-only records. Four complete records
  are source-backed executed plus three explicitly separate operation components;
  Golden-tested remains zero.
- KERNEL-EVENT nested-dispatch packet/tracer timing is aligned and covered
  by a multi-registration test.
- Modifier lifecycle reference now implements pending append ->
  ACTIVATE_ALIVE, and dirty removal returns deregistration/property-cleanup
  keys.
- DynamicValue structural bindings exist for SET/DEFINE_DYNAMIC_VALUE; the
  new `dynamic_value_reference.py` decodes all 1347 corpus PostfixExpr
  programs (ADD/SUB/MUL/DIV/NEG selected model) and provides an immutable
  define/set/read store.
- TargetAlias resolution reference (`target_semantics_reference.py`) covers
  the direct/collection/adjoin/center alias families observed in the corpus
  and rejects special/unknown aliases explicitly.
- Scheduler, damage/survival, predicate, RNG and property-contribution
  references exist with tests: markers/templates/loops/delay,
  normal/Break/SuperBreak/DoT formulas, shield/lock-HP/death transitions,
  Predicate AST evaluation with provider hooks, weighted RandomConfig
  selection, and stable modifier-owned contribution slots.
- `cross_family_interaction_fixture_001.json` composes real corpus predicate
  and formula payloads with the references in one deterministic trace and is
  explicitly `REFERENCE_INTERACTION_NOT_SOURCE_GOLDEN`.
- `source_backed_hot_reference_001.json` executes the real canonical
  `MAvatar_Natasha_00_HOT_HPByMaxHP` OnPhase1 callback with explicit fixture
  state and DynamicHash resolutions; status is
  `SOURCE_BACKED_REFERENCE_NOT_GOLDEN`.
- `source_backed_property_reference_001.json` executes the real canonical
  `MCommon_AttackRatioUp` OnStack StackProperty callback into a stable
  property-contribution slot; status is `SOURCE_BACKED_REFERENCE_NOT_GOLDEN`.
- `toughness_break_reference.py` implements toughness reduction,
  zero-crossing Break transition, Break damage and recovery with tests.
- Strict compiler report rebuilt: 201/249 structural-only records;
  failure clusters are recorded in `behavior_compiler_report_001.json` and
  `behavior_coverage_census_001.json`.
- `EXECUTABLE-BRIDGE-001` now provides a strict generic path from compiled
  canonical IR to immutable `ReferenceBattleState` transitions.  It supports
  conditional/predicate branching, the selected heal formulas, StackProperty,
  and DynamicValue define/set; unknown operations remain hard rejections.
  The current v2 compiler report has 102 `EXECUTABLE_REFERENCE` records and
  181 independently executable entrypoints, with two real source-backed
  records run through that path (Natasha HOT and `MCommon_AttackRatioUp`).
  These are still reference execution, not Golden game traces.
- `DAMAGE-EXECUTION-BRIDGE-001` adds strict standalone normal-HP request
  lowering: explicit attacker stats and target multiplier contexts produce a
  selected formula and shield-before-HP commit. It deliberately rejects
  mixed `StanceValue`/toughness, `SPHitRatio`, direct-value, Break/SuperBreak,
  DoT and inheritance payloads, so no mixed real canonical record was falsely
  promoted.
- `DAMAGE-TOUGHNESS-INTEGRATION-001` then bound the selected HP+`StanceValue`
  transition with explicit per-target toughness/weakness/Break inputs. The
  real Black Swan Skill02 adjoining damage operation runs as a separately
  labeled source-backed component fixture; its complete Skill entrypoint is
  still not executable and it is not Golden.
- `WEAKNESS-STATE-BRIDGE-001` corrects `StackWeakness` from the misleading
  `MODIFY_TOUGHNESS` family to `MODIFY_WEAKNESS(Attach)`. It writes the shared
  entity weakness state and supplies the existing `ByHasStanceWeak` predicate
  hook. The complete `MCommon_WeakType_Fire` OnStack callback now executes as
  a third source-backed record.
- `WEAKNESS-DAMAGE-CONTEXT-INTEGRATION-001` lets a selected StanceValue
  request read that immutable weakness state when its context does not supply
  an explicit boolean. Missing weakness deterministically skips stance; no
  default weakness, target toughness or Break factor is inferred.
- `RESOURCE-EXECUTION-BRIDGE-001` lowers selected `ModifySPNew` AddRatio and
  AddValue payloads to a bounded shared team skill-point holder. The complete
  `MCommon_HOT_SP` callback is a fourth source-backed record; pre-action cost
  and legality remain separate action-level semantics.
- `EXECUTOR-HANDLER-ELIGIBILITY-AUDIT-001` confirms every current executable
  kind has a real executor handler and declared context contract.
  `MODIFIER-DYNAMIC-INITIALIZATION-001` preserves selected AddModifier
  DynamicValues on immutable pending/refresh instances and executes a real
  StageAbility_3001213 ParamEntity listener component.
- `DOT-DAMAGE-EXECUTION-BRIDGE-001` admits only selected explicit
  `AttackType=DOT` / `DamagePercentage` operations through a separate no-crit
  shield-before-HP tick transition. A real Black Swan
  `MAvatar_BlackSwan_00_DOT` OnPhase1 component is source-backed executed;
  its enclosing application/lifecycle callback is deliberately not promoted.
- `MODIFIER-LAYER-DYNAMIC-VALUE-001` admits only the source shape that reads
  `ModifierOwnerEntity`'s explicit current ModifierInstance `Layer`, applies
  a DynamicValue multiplier and writes the result into the selected scope.
  It never uses `Count` as a proxy. A Black Swan DOT OnCustomEvent component
  is source-backed executed under that contract.

## Source state

Behavior source: TurnBasedGameData commit
`b11066beacc4de454b625fafc7ea3dd540c5bbf3`, relation
`CLOSE_4.4.0_TO_4.4.54`. Nanoka 4.4.54 remains the exact static oracle.
External raw files are build-time-only and must not be read by runtime.

## Exact resume point

After the corpus/SSOT repair and the reference packets above, continue with:

1. `DYNAMICVALUE-PROPERTY-MAXHP-READ-001`: lower only
   `SetDynamicValueByProperty` with `ReadTargetType=ModifierOwnerEntity` and
   `Value=MaxHP` against immutable SurvivalState.max_hp. Do not generalize it
   to other stats, aliases or property-contribution materialization.
2. Rebuild `behavior_compiler_report_002.json` and
   `behavior_coverage_census_002.json`, retaining separate full-record,
   component, entrypoint and Golden counts.
3. Choose the following strict family from the measured
   `BOUND_UNEXECUTABLE_PACKET` distribution, not an old primitive todo.

## Mandatory reads

`program_v1.json`, `external_source_expansion_profile_v1.json`,
`effect_ir_contract_v1.json`, `free_scenario_assembly_contract_v1.json`,
`external_behavior_corpus_v1.json`, `coverage_baseline_001.json`,
`behavior_compiler_report_001.json`, `behavior_coverage_census_001.json`, and
`coverage_ledger_v1.json`.
