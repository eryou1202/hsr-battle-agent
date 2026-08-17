# Generic Property Runtime 11

Final sandbox status: `BATTLE_SANDBOX = GENERIC_PROPERTY_RUNTIME_11_PROOF`.

Evidence / semantic contracts are not repeated here.  Source of truth:

- Handoff 09: `docs/agent/handoffs/semantic_handoff_09.md`
- Handoff 10: `docs/agent/handoffs/semantic_handoff_10.md`
- Handoff 11: `docs/agent/handoffs/semantic_handoff_11.md`
- Handoff 12 boundary: `docs/agent/handoffs/semantic_handoff_12_partial.md`
- Artifacts:
  - `data/semantics/4.4.54/modifier_property_effect_09.json`
  - `data/semantics/4.4.54/generic_property_materialization_10.json`
  - `data/semantics/4.4.54/generic_property_mutation_11.json`
- Report: `data/sandbox/generic_property_runtime_11_report.json`

## Implemented surface

- `battle_ir/property.py`: `PropertyEntry`, ordered
  `ModifierPropertyContribution`, `PropertyChangeBoundary`, neutral
  `MaterializationKind`, `PropertyModifyFunction`, StackProperty task IR.
- `battle_runtime/property.py`: fixed-point add/subtract/multiply, source-slot
  allocate/update/remove, materialization rebuild, component stack/update/
  unstack, modifier contribution stack/pop, scoped source-0 mutation.
- `battle_sandbox/state.py`: BattleState schema v3 with
  `entity_property_entries` and `modifier_property_contributions`.
- Catalog: Handoff 09/10/11 artifacts are enabled entries and bind all 23
  recovered primitives through the frozen registry.

## PropertyEntry model

Parallel arrays are indexed by stable `source_index`:

- `source_generation`: zero disables the slot.
- `source_active`: participation flag.
- `source_value`: stale values are retained after removal.

Plus `post_hook_context` / `post_transform_a` / `post_transform_b` (opaque),
`materialization_kind`, `generation_counter`, `active_source_extent`,
`last_changed_source`, `base_or_fallback`, and `materialized`.

## Source identity

- Allocation returns a stable index and starts at **1**; source `0` is the
  reserved native mutable/base slot and is never allocated to a modifier
  contribution.
- Refresh updates the same index and never appends a second source.
- Removal clears only active/version state for the exact index; no shift, no
  remap, no stale-value clear.

## Materialization

Implemented exactly where the artifacts prove behavior:

| kind | sandbox behavior |
| --- | --- |
| 1 | source-zero selection |
| 2 | last-changed-source selection |
| 3 | active fold via recovered fixed-point add callee |
| 4 | active fold via recovered fixed-point multiply callee; no-active -> base/fallback |
| 5 | explicit unsupported (callees known, fold formula not exactly recovered) |
| 6/7 | complementary extrema reducers, neutral direction labels |

Unknown kinds and non-null post-transform/post-hook state raise explicit
unsupported errors; there is no guessed addition fallback and no silent
post-stage bypass.

## Modifier contribution lifecycle

Ordered records are keyed by logical `ModifierRef` and store
`(target EntityRef, property_id, source_index)`.  `_PopStackedProperties`
walks own records in forward order, disables each exact source, then removes
the owner key.  Other modifiers with the same target/property are untouched.
Pop is an explicit primitive: generic `Destroy` / `RemoveDirtyModifiers`
do **not** auto-pop an unproven lifecycle route.

## Generic mutation

`modify_source_zero_untransformed` is scoped to:

- entry exists,
- `post_hook_context` is null,
- property_id outside `{10,12,14,16,18,20,22,24,26,28,30,32}`.

`1=Set`, `2=Add`, `3=Mul`, `4=MinSet`, `5=MaxSet`, out-of-range -> Set
fallthrough.  Success writes source slot 0, rebuilds, and emits exactly one
deterministic `_AfterPropertyChanged` boundary trace summary; no event bus is
invented.  Special IDs, especially CurrentHP (10), raise an explicit
unsupported error and cannot reach this path.

## Handoff 12 boundary

`CAPABILITY_STATUS = PARTIAL`.  This session only:

1. keeps PropertyEntry/source-0 as the future HP write boundary, and
2. adds the CurrentHP property-10 generic-path guard regression.

No HP/damage/clamp/dirty/negative policy was implemented.

## Tests

Relevant suites plus unpacker/cross_version all pass; totals are recorded in
the report JSON.
