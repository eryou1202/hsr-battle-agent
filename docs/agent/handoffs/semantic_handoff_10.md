# Semantic Handoff 10

## Capability

Generic Property source-slot lifecycle and materialization framework.

This supersedes Handoff 09's `opaque contribution_key` limit: the tracked key
is a stable `source_index` into the target property entry.  It does **not**
assign gameplay names/formulas to the five native fixed-point reducers.

Source of truth: `data/semantics/4.4.54/generic_property_materialization_10.json`.

## Proven topology

```text
StackProperty task
  -> Modifier.StackProperty (M506199; existing)
  -> AbilityComponent.StackProperty (M506495)
  -> native value/context adapter (0x15C6E450)
  -> AllocatePropertySourceSlot (0x15755890) -> source_index
  -> RebuildMaterializedProperty (0x15755AE0) -> PropertyEntry[+0x78]

refresh: M506497 -> UpdatePropertySourceSlot (0x157559D0) -> rebuild
remove:  M506312 -> M506496 -> RemovePropertySourceSlot (0x15755FD0) -> rebuild
```

## Proven primitives

- `battle.ir.property.component_stack_source`
  - `TurnBasedAbilityComponent.StackProperty`, M506495, `0xE72EB90`, `9950bfd264c81de590eefb175f0a8a9dc05a16a015a05f1eeafeb1008419f2d5`.
  - Fetches the target property entry, adapts the input/context, allocates a source slot, then notifies old/new materialized values.
  - Output is the stable `source_index` returned by `0x15755890`.

- `battle.ir.property.allocate_source_slot`
  - unregistered native helper, method index `null`, `0x15755890`, `878f88784312598329401fd6e35056468e71a66ae67b2b609d88732e22e7bd8d`.
  - Reads source generation/active/value arrays; allocates a source index; writes the source value, active bit, version, last-changed index; rebuilds immediately.

- `battle.ir.property.update_source_slot`
  - unregistered native helper, method index `null`, `0x157559D0`, `1a5105a81b2a52842ed0a55399d4cf288956750914ade1b912c8904e38db5843`.
  - Writes an existing `source_index`, marks it active/versioned, updates last-changed index, then tail-calls rebuild. It does not allocate.

- `battle.ir.property.remove_source_slot`
  - unregistered native helper, method index `null`, `0x15755FD0`, `22db4c710c898117bdb26221fea2b08f4c591973774d3af7a23d4dace634879a`.
  - Clears `active[index]` and `generation[index]`; stale source value remains. No shift/remap occurs. Then rebuilds.

- `battle.ir.property.rebuild_materialized`
  - unregistered native helper, method index `null`, `0x15755AE0`, `b29fc89c8fa98231758ebc90d00a2bab4f8b8b600090024f53dba1d3b4e07449`.
  - Reads kind `+0x58`, active slots and source values; writes materialized runtime numeric to `+0x78`; then applies native post-transform inputs `+0x48/+0x50` and tail hook `+0x40`.

- `battle.ir.property.update_contribution_source`
  - `TurnBasedAbilityComponent.UpdateStackPropertyValue`, M506497, `0xE731D90`, `a51b77289c7b0d36185912f4f937bc31cf5bdd3b2e4355144b5e788e95ffaceb`.
  - Reads old `+0x78`; updates stable source index; rebuilds; calls `_AfterPropertyChanged` with old/new values.

- `battle.ir.property.remove_contribution_source`
  - `TurnBasedAbilityComponent.UnStackProperty`, M506496, `0xE731B80`, `ca1fc3692e7db537807189107832b2ff7aa763f5b494e0d64f8e0b01d1a093b7`.
  - Reads old `+0x78`; disables stable source index; rebuilds; calls `_AfterPropertyChanged` with old/new values.

The materializer's seven native kinds are proven as control flow. Kinds 3–5
are forward active-slot folds, and kinds 6–7 are complementary extrema
reducers. Their fixed-point operator *names* are still UNKNOWN.

## Persistent State Requirements

```text
property_entries[(entity_ref, property_id)] = {
  source_generation: list[int],        # +0x10; zero means disabled
  source_active: list[bool],           # +0x20
  source_value: list[RuntimeNumeric],  # +0x30
  post_hook_context,                   # +0x40 opaque
  post_transform_a, post_transform_b,  # +0x48, +0x50 opaque
  materialization_kind: int,           # +0x58, 1..7
  generation_counter: int,             # +0x5C
  active_source_extent: int,           # +0x60
  last_changed_source: int,            # +0x64
  base_or_fallback: RuntimeNumeric,    # +0x70
  materialized: RuntimeNumeric,        # +0x78
}
```

`ModifierPropertyContribution` must retain `(entity_ref, property_id,
source_index)` in the existing modifier-local record. Source indices are
stable until the entry itself is destroyed.

## Existing primitives to reuse

- DynamicValue evaluator and target selector.
- Modifier `StackProperty` tracking and `_PopStackedProperties` lifecycle.
- `TurnBasedAbilityComponent.GetProperty` returns `PropertyEntry[+0x78]`.
- Existing Modifier Runtime state; do not replace it with direct final-stat maps.

## Application/inverse chain

```text
apply:  evaluate config -> select targets -> allocate source_index -> rebuild -> materialized changes
refresh: same tracked property+component -> update same source_index -> rebuild
remove:  modifier record -> disable same source_index -> rebuild
```

All three paths are deterministic; target and source iteration is forward.

## Mandatory implementation tests

1. Adding one source returns a source index, marks it active, and changes `materialized` only through rebuild.
2. Refresh preserves source index and increments generation; it must not append a second source.
3. Removing a source leaves other source indices unchanged and disables only that source.
4. Add two sources, remove the first, refresh the second: the second key remains valid.
5. Every add/refresh/remove invokes the post-materialization notification boundary once with old/new values.
6. Exercise each materialization kind only through explicitly configured/test-provided reducer semantics; reject an unrecognized kind.

## UNKNOWN

- The value/context adapter at `0x15C6E450` may transform `StackProperty.PropertyValue`; raw DynamicValue is not proven to equal stored source value.
- Gameplay names/formulas for fixed-point materialization kinds 3–7.
- Design-data/runtime construction of property-entry kind/base/post-transform fields.
- The post-materialization hook's listener/event consequence.

## MUST NOT IMPLEMENT

- `final_value += contribution` / `final_value -= contribution` as the Property model.
- Shift/remap keys when a modifier contribution is removed.
- Treat raw `StackProperty.PropertyValue` as a source value without the adapter contract.
- Invent SUM/MUL/MIN/MAX labels for kinds 3–7.
- Bypass `+0x48/+0x50/+0x40` materialization stages.

## Next Native Dependency

`0x15C6E450`, the property value/context adapter reached by M506495, then its
direct dispatcher `0x19B4485C0`. This determines how `StackProperty`
DynamicValue becomes a source-slot runtime value. In parallel, the direct HP
path remains `SetHP` executor M508871 -> `DirectChangeHP` M506500 ->
`DirectDamageHP` M506499.
