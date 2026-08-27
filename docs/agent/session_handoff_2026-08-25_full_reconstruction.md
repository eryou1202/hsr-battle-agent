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
- Corpus hash:
  `4fac2724182b31cb903fb96e56aa9b1c583b588fbf075615b93277b57c570ff5`.
- Current coverage split: 249 behavior-bearing records (99 structural-only
  compiled), 102 `EXECUTABLE_REFERENCE` records / 181 independently closed
  entrypoints, and 304 static-definition-only records. Two records are
  source-backed executed; Golden-tested remains zero.
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

## Source state

Behavior source: TurnBasedGameData commit
`b11066beacc4de454b625fafc7ea3dd540c5bbf3`, relation
`CLOSE_4.4.0_TO_4.4.54`. Nanoka 4.4.54 remains the exact static oracle.
External raw files are build-time-only and must not be read by runtime.

## Exact resume point

After the corpus/SSOT repair and the reference packets above, continue with:

1. `DAMAGE-TOUGHNESS-INTEGRATION-001`: bind a normal HP request and its
   `StanceValue` component as one explicit target transition using the
   existing toughness/break reference. Require supplied per-target weakness,
   toughness and break inputs; never omit a component to gain coverage.
2. Rebuild `behavior_compiler_report_002.json` and
   `behavior_coverage_census_002.json`; retain separate record, entrypoint,
   source-backed-executable and Golden counts.
3. Continue coverage-driven capture only from already pinned caches, starting
   with LightCone/RelicSet/wider MonsterSkill families after the generic bridge
   can consume their closed operations.

## Mandatory reads

`program_v1.json`, `external_source_expansion_profile_v1.json`,
`effect_ir_contract_v1.json`, `free_scenario_assembly_contract_v1.json`,
`external_behavior_corpus_v1.json`, `coverage_baseline_001.json`,
`behavior_compiler_report_001.json`, `behavior_coverage_census_001.json`, and
`coverage_ledger_v1.json`.
