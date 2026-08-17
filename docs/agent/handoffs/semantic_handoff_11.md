# Semantic Handoff 11

## Capability

`GENERIC_PROPERTY_MUTATION_SOURCE0_11_PROOF`: a scoped, persistent generic-property mutation path. For an admitted PropertyEntry with null `+0x40` post-transform context and a non-special property ID, native `ModifyProperty` applies `Set/Add/Mul/Min/Max`, updates stable source slot `0`, rematerializes, and invokes the post-change bridge.

## Proven topology

`M506503 ModifyProperty`
→ `0xE4410D0 ApplyPropertyModifyFunction`
→ `0x19CAF14A0` (null context: no-op)
→ `0x1957559D0 UpdatePropertySourceSlot(entry, 0, candidate)`
→ `entry[+0x78]` materialized persistent result
→ `M506625 _AfterPropertyChanged` call.

The config enum `RPG.GameCore.PropertyModifyFunction` (type 15455) supports the native mapping: `1 Set`, `2 Add`, `3 Mul`, `4 MinSet`, `5 MaxSet`. Native branches/arithmetic, not the enum labels, prove the operations.

## Proven primitives

- `battle.ir.fixedpoint.add`
  - Runtime: native helper, method index none; RVA `0x1D65EF80`; hash `db84c503bdba96493d67342df83dcdb8d90f64591b6464dc8318d609b38eb8a6`.
  - Inputs/output: `left, right → saturating fixed-point sum`.
  - Reads/writes: none persistent. Native fast path adds; range paths saturate.
  - Pseudocode: `return saturating_fixedpoint_add(left, right)`.

- `battle.ir.fixedpoint.subtract`
  - Runtime: native helper, method index none; RVA `0x1D661B60`; hash `39d843245aa77af8308c812b1a8ced6c72029bb43d7521d48da8e73f72756c0e`.
  - Inputs/output: `left, right → saturating fixed-point difference`.
  - Reads/writes: none persistent.
  - Pseudocode: `return saturating_fixedpoint_subtract(left, right)`.

- `battle.ir.fixedpoint.multiply`
  - Runtime: native helper, method index none; RVA `0x1D661A00`; hash `aa213631eaeb53e1a2c4d0037443e59b4e8bcfc5b65a11e5d464c0f360d915c8`.
  - Inputs/output: `left, right → saturating fixed-point product`.
  - Reads/writes: none persistent.
  - Pseudocode: `return saturating_fixedpoint_multiply(left, right)`.

- `battle.ir.property.apply_modify_function`
  - Runtime: native helper, method index none; RVA `0xE4410D0`; hash `aa8775d71b41bb6b9112630c4cba3892cdf6db8a41fbaef9ff604e5f1b337dc3`.
  - Inputs/output: `function_id, old, operand → candidate`.
  - Exact semantics: `1=operand`; `2=old+operand`; `3=old*operand`; `4=min(old, operand)`; `5=max(old, operand)`; out-of-range falls through to `operand`.
  - Reads/writes: no persistent state; deterministic fixed-point arithmetic/comparison.
  - Pseudocode:
    ```text
    switch function_id:
      1: return operand
      2: return fp_add(old, operand)
      3: return fp_mul(old, operand)
      4: return fp_min(old, operand)
      5: return fp_max(old, operand)
      default: return operand
    ```

- `battle.ir.property.modify_source_zero_untransformed`
  - Runtime: `RPG.GameCore.TurnBasedAbilityComponent.ModifyProperty`; method index `506503`; RVA `0xE72DCE0`; hash `dc83a97417b6fd89d9a9c640b7caf916c5d9e1de6bfdd98d6237060c63fdacd9`.
  - Inputs/output: `component, property_id, function_id, operand, context_token → bool changed`.
  - Reads: component `+0xA0` property table; selected entry `+0x78` old materialized value; `+0x40` post-transform context; admission guards.
  - Writes: selected entry source slot `0`, source generation/active state, rebuilt `+0x78`; invokes M506625 with old/new/context.
  - Accepted scope: entry exists/admitted; `entry[+0x40] == null`; `property_id ∉ {10,12,14,16,18,20,22,24,26,28,30,32}`.
  - Pseudocode:
    ```text
    entry = require_mutable_property_entry(component, property_id)
    old = entry.materialized
    candidate = apply_modify_function(function_id, old, operand)
    assert entry.post_transform_context is null
    update_source_slot(entry, 0, candidate)
    after_property_changed(component, property_id, old, entry.materialized, context_token)
    return true
    ```
  - Normal guard rejection returns false without this write. Hard native null/range error paths are not Sandbox behavior.

## Persistent State Requirements

- Reuse Handoff 10 `entity_property_entries` and stable source arrays.
- Reserve source index `0` for this native mutable/base path; never allocate or shift it as a modifier contribution.
- Persist `entry.post_transform_context`; reject non-null contexts for this scoped implementation.

## Existing primitives to reuse

- Handoff 10 `update_source_slot` and immediate materialization.
- Existing fixed-point comparison/runtime contracts.
- Modifier contributions retain their own nonzero stable `source_index` values.

## Application/inverse chain

This is a mutation, not a modifier contribution. The observed inverse is another `ModifyProperty` call with its own function/operand; no generic rollback or source removal is proven for source `0`.

## Mandatory implementation tests

- With null post-transform and a non-special property ID, verify Set/Add/Mul/Min/Max update source `0` and rematerialize immediately.
- Verify modifier-owned source indices remain stable when source `0` changes.
- Verify normal rejection leaves entry arrays and materialized value unchanged.
- Reject non-null post-transform and all listed special property IDs; do not silently take this common path.

## UNKNOWN

- `0x19CAF14A0` behavior for non-null post-transform context.
- Dedicated policies for special property IDs, including CurrentHP.
- Config/action executor that supplies M506503 inputs.
- Event/listener consumers after M506625.

## MUST NOT IMPLEMENT

- Do not use source `0` as a disposable modifier-contribution key.
- Do not bypass PropertyEntry rebuild or make mutation `final_value += x`.
- Do not apply this contract to CurrentHP or another listed special property.
- Do not invent event dispatch from `_AfterPropertyChanged`'s name.

## Next Native Dependency

Close `ModifyProperty`'s CurrentHP branch (`property_id 10`) through `GetDirtyHP` M506511 and the non-null `0x19CAF14A0` transform policy where configured. In parallel, resume `SetHP M508871 → DirectChangeHP M506500 → DirectDamageHP M506499` at its actual HP/damage transition boundary.
